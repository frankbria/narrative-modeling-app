'use client'

/**
 * "Approaching a limit" warning in the workflow shell (#767 AC3). The billing
 * page already turns a usage bar amber at 80%; this surfaces the same signal on
 * every authenticated page, once per mount, with a link to the one page that
 * can lift it. Silent on any failure — a billing outage must not decorate every
 * page with an error.
 */
import Link from 'next/link'
import { useSession } from 'next-auth/react'
import { useState } from 'react'
import { AlertCircle, X } from 'lucide-react'
import { useAsyncData } from '@/lib/hooks/useAsyncData'
import { BillingService, type BillingStatus } from '@/lib/services/billing'
import { metricWords, tierName } from '@/lib/billing/plans'

/** Same threshold as the billing page's amber bar. */
export const WARNING_THRESHOLD = 0.8

export interface NearingMetric {
  metric: string
  used: number
  limit: number
  pct: number
}

/**
 * Metered metrics at or past the threshold; unlimited (-1) never qualifies.
 *
 * Tolerates a malformed body: this renders in the root layout, so a throw here
 * blanks every authenticated page, not just the banner.
 */
export function nearingLimits(status: BillingStatus): NearingMetric[] {
  return Object.entries(status.limits ?? {})
    .filter(([, limit]) => typeof limit === 'number' && limit > 0)
    .map(([metric, limit]) => {
      const used = status.usage?.[metric] ?? 0
      return { metric, used, limit, pct: Math.min(100, Math.round((used / limit) * 100)) }
    })
    .filter(({ used, limit }) => used / limit >= WARNING_THRESHOLD)
}

export function UsageWarningBanner() {
  const { data: session } = useSession()
  const userId = session?.user?.id
  const [dismissed, setDismissed] = useState(false)
  // `userId`, not `session` — the session object has a new identity every render (#402).
  const { data: status } = useAsyncData<BillingStatus>(() => BillingService.getStatus(), [userId], {
    enabled: !!userId,
  })

  if (dismissed || !status) return null
  const nearing = nearingLimits(status)
  if (nearing.length === 0) return null

  const tier = tierName(status.tier)
  const items = nearing.map(({ metric, used, limit, pct }) => {
    return `${pct}% of your ${tier} plan's ${metricWords(metric)} (${used.toLocaleString()} of ${limit.toLocaleString()})`
  })

  return (
    <div role="status" data-testid="usage-warning-banner" className="mx-auto max-w-5xl mt-3 px-4">
      <div className="flex items-start gap-3 rounded-lg border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 text-sm text-amber-800 dark:text-amber-200">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
        <p className="flex-1">
          You have used {items.join(' and ')}.{' '}
          <Link href="/settings/billing" className="font-medium underline">
            See your plan and usage
          </Link>
        </p>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss usage warning"
          className="shrink-0 text-amber-600 hover:text-amber-900"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

export default UsageWarningBanner
