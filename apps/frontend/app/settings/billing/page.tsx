'use client'

import { useAsyncData } from '@/lib/hooks/useAsyncData'
import { useSession } from 'next-auth/react'
import {
  BillingService,
  CHECKOUT_POLL_MAX,
  CHECKOUT_POLL_MS,
  UNLIMITED,
  type BillingStatus,
  type PlanTier,
} from '@/lib/services/billing'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { COMPANY } from '@/lib/legal/company'
import { METRIC_LABELS as PLAN_METRIC_LABELS, planFor, priceLabel } from '@/lib/billing/plans'

const METRIC_LABELS: Record<string, string> = PLAN_METRIC_LABELS

type CheckoutOutcome = 'success' | 'cancelled' | null

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

function BillingSettings() {
  const { data: session, status: sessionStatus } = useSession()
  const userId = session?.user?.id
  const [redirecting, setRedirecting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const router = useRouter()
  const searchParams = useSearchParams()
  // Stripe sends the browser back with ?checkout=success|cancelled (#767 AC4).
  // Read once into state, then clear the URL so a reload does not re-announce it.
  const [checkout] = useState<CheckoutOutcome>(() => {
    const value = searchParams.get('checkout')
    return value === 'success' || value === 'cancelled' ? value : null
  })
  const [activated, setActivated] = useState(false)
  const [pollTimedOut, setPollTimedOut] = useState(false)

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

  useEffect(() => {
    if (searchParams.get('checkout')) router.replace('/settings/billing')
  }, [searchParams, router])

  // The status endpoint still says FREE until the Stripe webhook lands, so the
  // highest-intent moment in the product used to render an unchanged page. Poll
  // (bounded) until the tier moves, then reload; past the bound, say so.
  const initialTier = status?.tier
  useEffect(() => {
    if (checkout !== 'success' || !initialTier || initialTier !== 'free' || activated || pollTimedOut) return
    let attempts = 0
    const timer = setInterval(async () => {
      attempts += 1
      try {
        const latest = await BillingService.getStatus()
        if (latest.tier !== initialTier) {
          clearInterval(timer)
          setActivated(true)
          reload()
          return
        }
      } catch {
        // Transient; the next tick retries until the bound.
      }
      if (attempts >= CHECKOUT_POLL_MAX) {
        clearInterval(timer)
        setPollTimedOut(true)
      }
    }, CHECKOUT_POLL_MS)
    return () => clearInterval(timer)
  }, [checkout, initialTier, activated, pollTimedOut, reload])

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

  // While the session resolves, `enabled` is false — so `loading` is false and
  // `status` is undefined, and the error branch below would claim billing is
  // unavailable on every single page load until auth settles. The session state is
  // part of "still loading", not part of "failed".
  if (sessionStatus === 'loading' || loading) {
    return <p className="p-8 text-muted-foreground">Loading billing…</p>
  }

  if (sessionStatus === 'unauthenticated') {
    return (
      <p className="p-8 text-muted-foreground">Sign in to view your plan.</p>
    )
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

      {checkout === 'success' && (
        <Alert data-testid="checkout-notice">
          <AlertDescription>
            {status.tier !== 'free' || activated
              ? `Payment received — your ${tierLabel[status.tier]} plan is active.`
              : pollTimedOut
                ? 'Payment received. Activating your plan can take a minute — refresh this page to see it.'
                : 'Payment received — activating your plan…'}
          </AlertDescription>
        </Alert>
      )}
      {checkout === 'cancelled' && (
        <Alert data-testid="checkout-notice">
          <AlertDescription>
            Checkout was cancelled. You have not been charged and are still on the{' '}
            {tierLabel[status.tier]} plan.
          </AlertDescription>
        </Alert>
      )}

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
        <div className="space-y-2">
          {/* The price is on the button that starts the charge (#475 AC3), from
              the same source the public pricing page renders. */}
          <Button disabled={redirecting} onClick={() => go(() => BillingService.startCheckout('pro'))}>
            {redirecting ? 'Redirecting…' : `Upgrade to Pro · ${priceLabel(planFor('pro'))}`}
          </Button>
          {/* The terms the charge is made under, at the point of the charge (#473). */}
          <p className="text-xs text-muted-foreground">
            <Link href="/pricing" className="text-primary hover:underline">
              Compare plans
            </Link>
            . Subscriptions renew monthly until cancelled. By upgrading you agree to our{' '}
            <Link href="/legal/terms" className="text-primary hover:underline">
              Terms of Service
            </Link>{' '}
            and{' '}
            <Link href="/legal/terms#refunds" className="text-primary hover:underline">
              refund policy
            </Link>
            .
          </p>
        </div>
      ) : (
        <Button
          variant="outline"
          disabled={redirecting}
          onClick={() => go(() => BillingService.openPortal())}
        >
          {redirecting ? 'Redirecting…' : 'Manage subscription'}
        </Button>
      )}

      {/* ENTERPRISE is sales-led (#474 AC3): a contact link, never a dead tier. */}
      {status.configured && status.tier !== 'enterprise' && (
        <p className="text-sm text-muted-foreground">
          Need unlimited training, predictions and uploads?{' '}
          <a
            href={`mailto:${COMPANY.supportEmail}?subject=Enterprise%20plan`}
            className="text-primary hover:underline"
          >
            Contact us
          </a>{' '}
          about Enterprise.
        </p>
      )}
    </div>
  )
}

// useSearchParams needs a Suspense boundary above it or the prerender bails out.
export default function BillingSettingsPage() {
  return (
    <Suspense fallback={<p className="p-8 text-muted-foreground">Loading billing…</p>}>
      <BillingSettings />
    </Suspense>
  )
}
