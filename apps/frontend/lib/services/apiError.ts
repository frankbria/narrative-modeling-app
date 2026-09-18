/**
 * One error type for every backend call (#767 AC1).
 *
 * Every service used to hand-roll `throw new Error(detail || '…')`, which drops
 * the HTTP status and the parsed body — so a plan-limit 402 (which carries
 * metric/limit/used/resets_at/upgrade_available) rendered as a bare "HTTP 402".
 * `apiError(response, fallback)` keeps the old message behaviour (the backend's
 * `detail` string or message, else the caller's fallback) and adds the status and
 * body; a `quota_exceeded` 402 becomes a `QuotaExceededError` and opens the
 * PlanLimitDialog through the `planLimit` store.
 */
import type { PlanTier } from '@/lib/billing/plans'
import { planLimit } from '@/lib/billing/planLimit'

/**
 * The keys of the backend's 402 `detail` (`app/billing/enforcement.py::reserve`).
 * `tests/test_api/test_quota_enforcement.py` parses this list out of this file and
 * fails if the two drift (the schema ↔ type mirror rule).
 */
export const QUOTA_DETAIL_FIELDS = [
  'error',
  'metric',
  'limit',
  'used',
  'tier',
  'resets_at',
  'message',
  'upgrade_available',
] as const

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/**
 * A metered route refused the request. Every field but `metric` is nullable: the
 * backend's `reserve_records` test seam emits only `{error, metric}`.
 */
export class QuotaExceededError extends ApiError {
  readonly metric: string
  readonly limit: number | null
  readonly used: number | null
  readonly tier: PlanTier | null
  readonly resets_at: string | null
  readonly upgrade_available: boolean

  constructor(detail: Record<string, unknown>, fallback: string) {
    super(402, detail, typeof detail.message === 'string' ? detail.message : fallback)
    this.name = 'QuotaExceededError'
    this.metric = String(detail.metric)
    this.limit = typeof detail.limit === 'number' ? detail.limit : null
    this.used = typeof detail.used === 'number' ? detail.used : null
    this.tier = typeof detail.tier === 'string' ? (detail.tier as PlanTier) : null
    this.resets_at = typeof detail.resets_at === 'string' ? detail.resets_at : null
    this.upgrade_available = detail.upgrade_available === true
  }
}

const isQuotaDetail = (detail: unknown): detail is Record<string, unknown> =>
  typeof detail === 'object' &&
  detail !== null &&
  (detail as Record<string, unknown>).error === 'quota_exceeded' &&
  typeof (detail as Record<string, unknown>).metric === 'string'

/**
 * Build the error for a non-OK response. Callers `throw await apiError(response, '…')`.
 */
export async function apiError(response: Response, fallback: string): Promise<ApiError> {
  const body = (await response.json().catch(() => undefined)) as { detail?: unknown } | undefined
  const detail = body?.detail

  if (response.status === 402 && isQuotaDetail(detail)) {
    const quota = new QuotaExceededError(detail, fallback)
    planLimit.show(quota)
    return quota
  }

  return new ApiError(response.status, detail, typeof detail === 'string' ? detail : fallback)
}
