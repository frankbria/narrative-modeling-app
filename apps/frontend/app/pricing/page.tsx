import type { Metadata } from 'next'
import Link from 'next/link'
import { COMPANY } from '@/lib/legal/company'
import {
  METRIC_LABELS,
  PERIOD,
  PLANS,
  limitLabel,
  priceLabel,
  type Metric,
  type Plan,
} from '@/lib/billing/plans'

/**
 * Public pricing page (issue #475).
 *
 * Reachable without an account (an exact-path exemption in middleware.ts), so a
 * prospective customer sees the price and the limits before entering payment
 * details. Every number comes from `lib/billing/plans.json`, which the backend
 * suite holds equal to `plans.py` — this page states nothing enforcement does
 * not implement. ENTERPRISE is sales-led (ADR-003 AC3): a contact link, never a
 * price.
 */

export const metadata: Metadata = {
  title: `Pricing | ${COMPANY.serviceName}`,
  description: `Plans and limits for the hosted ${COMPANY.serviceName} service: what each tier costs, what it includes, and what happens at a limit.`,
}

const METRICS = Object.keys(METRIC_LABELS) as Metric[]

function TierCard({ plan }: { plan: Plan }) {
  const headingId = `plan-${plan.tier}`
  return (
    <section
      aria-labelledby={headingId}
      className={`flex flex-col rounded-lg border bg-card p-6 text-card-foreground shadow-sm ${
        plan.tier === 'pro' ? 'border-primary' : 'border-border'
      }`}
    >
      <h2 id={headingId} className="text-lg font-semibold">
        {plan.name}
      </h2>
      <p className="mt-2 text-2xl font-bold">{priceLabel(plan)}</p>
      <ul className="mt-6 flex-1 space-y-2 text-sm">
        {METRICS.map((metric) => (
          <li key={metric} className="flex items-baseline justify-between gap-4">
            <span className="text-muted-foreground">{METRIC_LABELS[metric]}</span>
            <span className="font-medium tabular-nums">{limitLabel(plan.limits[metric])}</span>
          </li>
        ))}
      </ul>
      <TierAction plan={plan} />
    </section>
  )
}

function TierAction({ plan }: { plan: Plan }) {
  const cta =
    'mt-6 inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring'
  if (plan.tier === 'enterprise') {
    return (
      <a
        href={`mailto:${COMPANY.supportEmail}?subject=Enterprise%20plan`}
        className={`${cta} border border-border bg-background hover:bg-muted`}
      >
        Contact us
      </a>
    )
  }
  if (plan.tier === 'pro') {
    return (
      <Link
        href={`/auth/signin?callbackUrl=${encodeURIComponent('/settings/billing')}`}
        className={`${cta} bg-primary text-primary-foreground hover:bg-primary/90`}
      >
        Upgrade to Pro
      </Link>
    )
  }
  return (
    <Link href="/auth/signin" className={`${cta} border border-border bg-background hover:bg-muted`}>
      Get started
    </Link>
  )
}

export default function PricingPage() {
  return (
    <div className="w-full max-w-5xl mx-auto px-6 pt-10 pb-20 text-foreground">
      <h1 className="text-3xl font-bold">Pricing</h1>
      <p className="mt-2 max-w-3xl text-muted-foreground">
        Every plan runs the same product: upload a dataset, get it summarised, engineer features
        and train, evaluate and deploy a model without writing code. The tiers differ only in how
        much of each you can do per {PERIOD}.
      </p>

      <div className="mt-8 grid gap-6 md:grid-cols-3">
        {PLANS.map((plan) => (
          <TierCard key={plan.tier} plan={plan} />
        ))}
      </div>

      <section id="limits" className="mt-12 max-w-3xl space-y-3">
        <h2 className="text-xl font-semibold">What happens when you reach a limit</h2>
        <p className="text-muted-foreground">
          When you reach a limit, further requests of that kind are refused with an HTTP 402
          response until the limit resets. Nothing is queued, and nothing is billed as overage: you
          are never charged more than your plan&apos;s price. Limits reset on the first day of each{' '}
          {PERIOD} (UTC).
        </p>
        <p className="text-muted-foreground">
          The response says which limit was reached, how much of it was used, when it resets and
          whether a higher tier would lift it. An unlimited item has no ceiling on that plan; AI
          calls are capped on every plan, Enterprise included, because that is the ceiling on the
          model bill.
        </p>
      </section>

      <p className="mt-8 max-w-3xl text-sm text-muted-foreground">
        Subscriptions renew monthly until cancelled, with a {COMPANY.refundWindowDays}-day
        money-back window on your first paid charge. See the{' '}
        <Link href="/legal/terms#refunds" className="text-primary hover:underline">
          refund policy
        </Link>{' '}
        and the{' '}
        <Link href="/legal/terms" className="text-primary hover:underline">
          Terms of Service
        </Link>
        .
      </p>
    </div>
  )
}
