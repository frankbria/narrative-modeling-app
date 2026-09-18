/**
 * #767 AC1: one error type carries the HTTP status and the parsed body, and a
 * 402 with the backend's `quota_exceeded` detail becomes a QuotaExceededError
 * that also opens the single PlanLimitDialog (via the planLimit store).
 */
import { ApiError, QuotaExceededError, QUOTA_DETAIL_FIELDS, apiError } from '@/lib/services/apiError'
import { planLimit } from '@/lib/billing/planLimit'

const jsonResponse = (status: number, body: unknown, statusText = ''): Response =>
  ({
    ok: false,
    status,
    statusText,
    json: async () => body,
    text: async () => JSON.stringify(body),
  }) as unknown as Response

const fullDetail = {
  error: 'quota_exceeded',
  metric: 'uploads',
  limit: 10,
  used: 10,
  tier: 'free',
  resets_at: '2026-10-01T00:00:00+00:00',
  message: 'You have used all 10 uploads included in the free plan this month.',
  upgrade_available: true,
}

beforeEach(() => planLimit.dismiss())

describe('apiError', () => {
  it('turns a full 402 quota body into a QuotaExceededError carrying the backend numbers', async () => {
    const err = await apiError(jsonResponse(402, { detail: fullDetail }), 'fallback')

    expect(err).toBeInstanceOf(QuotaExceededError)
    expect(err).toBeInstanceOf(ApiError)
    const quota = err as QuotaExceededError
    expect(quota.status).toBe(402)
    expect(quota.metric).toBe('uploads')
    expect(quota.limit).toBe(10)
    expect(quota.used).toBe(10)
    expect(quota.tier).toBe('free')
    expect(quota.resets_at).toBe('2026-10-01T00:00:00+00:00')
    expect(quota.upgrade_available).toBe(true)
    // The message is the backend's sentence, so existing inline error text stays useful.
    expect(quota.message).toBe(fullDetail.message)
  })

  it('opens the plan-limit dialog store for a quota error', async () => {
    const err = await apiError(jsonResponse(402, { detail: fullDetail }), 'fallback')
    expect(planLimit.get()).toBe(err)
  })

  it('tolerates the thin {error, metric} variant', async () => {
    const err = (await apiError(
      jsonResponse(402, { detail: { error: 'quota_exceeded', metric: 'predictions' } }),
      'Prediction failed'
    )) as QuotaExceededError

    expect(err).toBeInstanceOf(QuotaExceededError)
    expect(err.metric).toBe('predictions')
    expect(err.limit).toBeNull()
    expect(err.used).toBeNull()
    expect(err.tier).toBeNull()
    expect(err.resets_at).toBeNull()
    expect(err.upgrade_available).toBe(false)
    expect(err.message).toBe('Prediction failed')
    expect(planLimit.get()).toBe(err)
  })

  it('a 402 without the quota marker is a plain ApiError and does not open the dialog', async () => {
    const err = await apiError(jsonResponse(402, { detail: 'Payment required' }), 'fallback')
    expect(err).toBeInstanceOf(ApiError)
    expect(err).not.toBeInstanceOf(QuotaExceededError)
    expect(err.message).toBe('Payment required')
    expect(planLimit.get()).toBeNull()
  })

  it('carries status and detail for a non-402, using the string detail as the message', async () => {
    const err = await apiError(jsonResponse(404, { detail: 'Model not found' }), 'Failed to fetch model')
    expect(err.status).toBe(404)
    expect(err.detail).toBe('Model not found')
    expect(err.message).toBe('Model not found')
    expect(planLimit.get()).toBeNull()
  })

  it('falls back to the caller message when the body is not JSON', async () => {
    const response = {
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => {
        throw new Error('not json')
      },
      text: async () => '<html>',
    } as unknown as Response
    const err = await apiError(response, 'Upload failed')
    expect(err.status).toBe(500)
    expect(err.message).toBe('Upload failed')
    expect(err.detail).toBeUndefined()
  })

  it('falls back when detail is an object without a message (e.g. a 422 validation body)', async () => {
    const err = await apiError(jsonResponse(422, { detail: [{ loc: ['body'], msg: 'bad' }] }), 'Invalid request')
    expect(err.status).toBe(422)
    expect(err.message).toBe('Invalid request')
  })

  it('pins the field names the contract test on the backend checks against enforcement.py', () => {
    expect([...QUOTA_DETAIL_FIELDS]).toEqual([
      'error',
      'metric',
      'limit',
      'used',
      'tier',
      'resets_at',
      'message',
      'upgrade_available',
    ])
  })
})

describe('planLimit store', () => {
  it('notifies subscribers on show and dismiss', async () => {
    const seen: Array<QuotaExceededError | null> = []
    const unsubscribe = planLimit.subscribe(() => seen.push(planLimit.get()))

    const err = (await apiError(jsonResponse(402, { detail: fullDetail }), 'x')) as QuotaExceededError
    planLimit.dismiss()
    unsubscribe()
    planLimit.show(err)

    expect(seen).toEqual([err, null])
  })
})
