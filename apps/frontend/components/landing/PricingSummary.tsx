import Link from 'next/link'
import { PERIOD, PLANS, limitLabel, priceLabel } from '@/lib/billing/plans'

export function PricingSummary() {
  const plans = PLANS
  return (
    <section aria-labelledby="pricing-heading" className="space-y-4">
      <h2 id="pricing-heading" className="text-2xl font-semibold text-foreground">
        Pricing
      </h2>
      <ul className="grid gap-4 md:grid-cols-3">
        {plans.map((plan) => (
          <li key={plan.tier} className="rounded-lg border border-border bg-card p-5 text-card-foreground shadow-sm">
            <h3 className="font-semibold">{plan.name}</h3>
            <p className="mt-1 text-2xl font-bold">{priceLabel(plan)}</p>
            <p className="mt-2 text-sm text-muted-foreground">
              {`${limitLabel(plan.limits.training_runs)} training runs per ${PERIOD}`}
            </p>
          </li>
        ))}
      </ul>
      <Link href="/pricing" className="text-sm text-primary hover:underline">
        Full pricing and limits
      </Link>
    </section>
  )
}
