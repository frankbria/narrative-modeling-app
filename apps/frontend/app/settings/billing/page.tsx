'use client'

import { useAsyncData } from '@/lib/hooks/useAsyncData'
import { useSession } from 'next-auth/react'
import {
  BillingService,
  UNLIMITED,
  type BillingStatus,
  type PlanTier,
} from '@/lib/services/billing'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useState } from 'react'

const METRIC_LABELS: Record<string, string> = {
  training_runs: 'Training runs',
  predictions: 'Predictions',
  uploads: 'Uploads',
}

/** A metered row. `-1` is unlimited, which has no bar to draw. */
function UsageRow({
  metric,
  used,
  limit,
}: {
  metric: string
  used: number
  limit: number
}) {
  const unlimited = limit === UNLIMITED
  const pct = unlimited ? 0 : Math.min(100, Math.round((used / Math.max(limit, 1)) * 100))
  // Amber before the wall rather than at it, so the upgrade prompt arrives while
  // there is still quota left to work with.
  const nearing = !unlimited && pct >= 80

  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-foreground">{METRIC_LABELS[metric] ?? metric}</span>
        <span className="text-muted-foreground">
          {used.toLocaleString()} {unlimited ? '' : `/ ${limit.toLocaleString()}`}
          {unlimited && <span className="ml-1">· unlimited</span>}
        </span>
      </div>
      {!unlimited && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full transition-all ${
              nearing ? 'bg-amber-500' : 'bg-blue-600'
            }`}
            style={{ width: `${pct}%` }}
            role="progressbar"
            aria-valuenow={used}
            aria-valuemin={0}
            aria-valuemax={limit}
            aria-label={`${METRIC_LABELS[metric] ?? metric} usage`}
          />
        </div>
      )}
    </div>
  )
}

export default function BillingSettingsPage() {
  const { data: session } = useSession()
  const userId = session?.user?.id
  const [redirecting, setRedirecting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const {
    data: status,
    loading,
    error,
    reload,
  } = useAsyncData<BillingStatus>(
    () => BillingService.getStatus(),
    // `userId`, not `session` — the session object has a new identity every render
    // and would refetch forever (#402).
    [userId],
    { enabled: !!userId, errorMessage: 'Failed to load billing status' }
  )

  const go = async (start: () => Promise<{ url: string }>) => {
    setActionError(null)
    setRedirecting(true)
    try {
      const { url } = await start()
      window.location.href = url
    } catch (e) {
      setRedirecting(false)
      setActionError(e instanceof Error ? e.message : 'Something went wrong')
    }
  }

  if (loading) {
    return <p className="p-8 text-muted-foreground">Loading billing…</p>
  }

  if (error || !status) {
    return (
      <div className="p-8">
        <Alert variant="destructive">
          <AlertDescription>{error ?? 'Billing unavailable'}</AlertDescription>
        </Alert>
        <Button className="mt-4" variant="outline" onClick={reload}>
          Try again
        </Button>
      </div>
    )
  }

  const tierLabel: Record<PlanTier, string> = {
    free: 'Free',
    pro: 'Pro',
    enterprise: 'Enterprise',
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Plan &amp; usage</h1>
        <p className="text-muted-foreground">
          What you are on, and how much of it you have used this period.
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{tierLabel[status.tier]}</CardTitle>
              <CardDescription>
                {status.cancel_at_period_end
                  ? 'Cancels at the end of the current period'
                  : status.current_period_end
                    ? `Renews ${new Date(status.current_period_end).toLocaleDateString()}`
                    : 'No paid subscription'}
              </CardDescription>
            </div>
            {status.status && <Badge variant="outline">{status.status}</Badge>}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {Object.keys(status.limits).map((metric) => (
            <UsageRow
              key={metric}
              metric={metric}
              used={status.usage[metric] ?? 0}
              limit={status.limits[metric]}
            />
          ))}
        </CardContent>
      </Card>

      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      {!status.configured ? (
        // Not an error state. The free invite-only beta runs exactly like this,
        // and saying so is better than showing a button that cannot work.
        <Alert>
          <AlertDescription>
            Paid plans are not enabled on this deployment. You are on the Free tier
            with the limits shown above.
          </AlertDescription>
        </Alert>
      ) : status.tier === 'free' ? (
        <Button disabled={redirecting} onClick={() => go(() => BillingService.startCheckout('pro'))}>
          {redirecting ? 'Redirecting…' : 'Upgrade to Pro'}
        </Button>
      ) : (
        <Button
          variant="outline"
          disabled={redirecting}
          onClick={() => go(() => BillingService.openPortal())}
        >
          {redirecting ? 'Redirecting…' : 'Manage subscription'}
        </Button>
      )}
    </div>
  )
}
