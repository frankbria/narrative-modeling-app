/**
 * Billing API client (#365).
 *
 * `API_BASE_URL` already carries the `/api/v1` prefix — appending it again is the
 * bug #406 fixed across three modules, and `__tests__/lib/apiUrlConstruction.test.ts`
 * now scans the whole repo for it.
 */
import { API_BASE_URL } from '@/lib/config'
import { getAuthToken } from '@/lib/auth-helpers'

export type PlanTier = 'free' | 'pro' | 'enterprise'

/** `-1` means no ceiling. Passed through rather than omitted so the UI can tell
 *  "unlimited" from "not reported". */
export const UNLIMITED = -1

export interface BillingStatus {
  configured: boolean
  tier: PlanTier
  status: string | null
  cancel_at_period_end: boolean
  current_period_end: string | null
  usage: Record<string, number>
  limits: Record<string, number>
}

async function authorizedFetch(path: string, init?: RequestInit) {
  const token = await getAuthToken()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    // Carry the status: 503 means "billing is off on this deployment", which the
    // UI presents differently from a genuine failure.
    throw new Error(`Billing request failed (HTTP ${response.status})`)
  }
  return response.json()
}

export const BillingService = {
  getStatus: (): Promise<BillingStatus> => authorizedFetch('/billing/status'),

  startCheckout: (tier: PlanTier): Promise<{ url: string }> =>
    authorizedFetch('/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({
        tier,
        // Absolute, because Stripe redirects the browser back here itself.
        success_url: `${window.location.origin}/settings/billing?checkout=success`,
        cancel_url: `${window.location.origin}/settings/billing?checkout=cancelled`,
      }),
    }),

  openPortal: (): Promise<{ url: string }> =>
    authorizedFetch('/billing/portal', {
      method: 'POST',
      body: JSON.stringify({
        return_url: `${window.location.origin}/settings/billing`,
      }),
    }),
}
