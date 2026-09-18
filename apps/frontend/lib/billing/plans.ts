/**
 * The plan tiers as published to customers (issue #475).
 *
 * `plans.json` is the single source for every price and limit shown on the
 * public /pricing page, the landing page (#766) and the billing settings page.
 * It is a copy of the product decision in `docs/architecture/ADR-003` and of
 * `apps/backend/app/billing/plans.py`, held equal by
 * `apps/backend/tests/test_billing/test_pricing_source_matches_plans.py` —
 * a limit advertised here that enforcement does not implement fails the backend
 * suite. Change the ADR, `plans.py` and `plans.json` together.
 *
 * Kept static rather than fetched: a marketing page must render with no backend
 * up (the Docker image builds without one), and a public `GET /billing/plans`
 * would be the first unauthenticated route in an authenticated router.
 */
import data from './plans.json'

export type PlanTier = 'free' | 'pro' | 'enterprise'

/** `-1` means no ceiling — the sentinel `plans.py` and `/billing/status` use. */
export const UNLIMITED = -1

export const METRIC_LABELS = {
  training_runs: 'Training runs',
  predictions: 'Predictions',
  uploads: 'Uploads',
  ai_calls: 'AI calls',
} as const

export type Metric = keyof typeof METRIC_LABELS

export interface Plan {
  tier: PlanTier
  name: string
  /** `null` is sales-led: no published price (ADR-003 AC3). */
  price_usd_per_month: number | null
  limits: Record<Metric, number>
}

export const PLANS: readonly Plan[] = data.tiers as Plan[]

/** The window a limit counts against, for the copy ("per calendar month"). */
export const PERIOD: string = data.period

export function planFor(tier: PlanTier): Plan {
  const plan = PLANS.find((p) => p.tier === tier)
  if (!plan) throw new Error(`plans.json has no tier "${tier}"`)
  return plan
}

export function priceLabel(plan: Plan): string {
  if (plan.price_usd_per_month === null) return 'Custom pricing'
  return plan.price_usd_per_month === 0 ? '$0' : `$${plan.price_usd_per_month} / month`
}

export function limitLabel(limit: number): string {
  return limit === UNLIMITED ? 'Unlimited' : limit.toLocaleString('en-US')
}

/**
 * A metric in plain words for a sentence: "training runs", "AI calls". Only a
 * leading capitalised word is lowercased, so an acronym label keeps its case.
 */
export function metricWords(metric: string): string {
  const label = (METRIC_LABELS as Record<string, string>)[metric] ?? metric.replace(/_/g, ' ')
  return label.replace(/^[A-Z][a-z]/, (m) => m.toLowerCase())
}
