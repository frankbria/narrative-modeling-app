'use client'

/**
 * The one plan-limit dialog (#767 AC2). Mounted once in the authenticated root
 * layout; opens whenever `apiError()` parses a `quota_exceeded` 402 anywhere
 * (upload, training, prediction, every ai_calls surface) and says, in plain
 * words, which limit was hit, how much of it was used, when it resets, and the
 * one action that lifts it: Upgrade (FREE), Contact us (PRO), or nothing
 * (ENTERPRISE — only ai_calls is finite there, and it is the model-bill backstop).
 */
import Link from 'next/link'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { planLimit, usePlanLimit } from '@/lib/billing/planLimit'
import { metricWords, planFor, priceLabel, tierName } from '@/lib/billing/plans'
import { COMPANY } from '@/lib/legal/company'

export function resetDate(iso: string | null): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
}

export function PlanLimitDialog() {
  const error = usePlanLimit()
  if (!error) return null

  const words = metricWords(error.metric)
  const tier = error.tier ? tierName(error.tier) : null
  const resets = resetDate(error.resets_at)
  const counted = error.limit !== null && error.used !== null

  return (
    <Dialog open onOpenChange={(open) => !open && planLimit.dismiss()}>
      <DialogContent data-testid="plan-limit-dialog">
        <DialogHeader>
          <DialogTitle>
            {tier ? `You have reached the ${tier} plan's ${words} limit` : `You have reached your ${words} limit`}
          </DialogTitle>
          <DialogDescription asChild>
            <div className="space-y-1 text-sm text-muted-foreground">
              {counted && (
                <p>
                  <span data-testid="plan-limit-usage">
                    {error.used!.toLocaleString()} of {error.limit!.toLocaleString()}
                  </span>{' '}
                  {words} used{error.resets_at ? ' this period' : ''}.
                </p>
              )}
              {resets && <p>Your limit resets on {resets}.</p>}
              {error.tier === 'enterprise' && (
                <p>You are on the highest plan. AI calls are capped on every plan as the ceiling on the model bill.</p>
              )}
            </div>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={planLimit.dismiss}>
            Not now
          </Button>
          {error.upgrade_available && error.tier !== 'enterprise' ? (
            <Button asChild>
              <Link href="/settings/billing" onClick={planLimit.dismiss}>
                Upgrade to Pro · {priceLabel(planFor('pro'))}
              </Link>
            </Button>
          ) : error.tier !== 'enterprise' ? (
            <Button asChild>
              <a href={`mailto:${COMPANY.supportEmail}?subject=Enterprise%20plan`} onClick={planLimit.dismiss}>
                Contact us about Enterprise
              </a>
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default PlanLimitDialog
