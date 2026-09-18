/**
 * Checkout confirmation on the billing page (#767 AC4).
 *
 * Stripe sends the browser back to /settings/billing?checkout=success|cancelled.
 * On success the page must say so and poll /billing/status (bounded) until the
 * webhook has moved the tier, then clear the param; on cancel it says so and
 * keeps the Upgrade button.
 */
import React from 'react'
import { render, screen, waitFor, act } from '@testing-library/react'
import '@testing-library/jest-dom'
import BillingSettingsPage from '@/app/settings/billing/page'
import { CHECKOUT_POLL_MS, CHECKOUT_POLL_MAX } from '@/lib/services/billing'

jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('tok'),
}))

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'mock-user-id', email: 'test@example.com' } },
    status: 'authenticated',
  }),
}))

const ROUTER = (global as unknown as { __NEXT_ROUTER_MOCKS__: { replace: jest.Mock } }).__NEXT_ROUTER_MOCKS__

let search = ''
jest.mock('next/navigation', () => ({
  useRouter: () => ROUTER,
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(search),
}))

const status = (tier: 'free' | 'pro') => ({
  configured: true,
  tier,
  status: tier === 'pro' ? 'active' : null,
  cancel_at_period_end: false,
  current_period_end: null,
  usage: { uploads: 1 },
  limits: { uploads: 20 },
})

/** Each call to /billing/status answers the next body in the list (last one repeats). */
const mockStatusSequence = (bodies: object[]) => {
  let i = 0
  global.fetch = jest.fn().mockImplementation(async () => {
    const body = bodies[Math.min(i, bodies.length - 1)]
    i += 1
    return { ok: true, status: 200, json: async () => body }
  })
}

const tick = async () => {
  await act(async () => {
    jest.advanceTimersByTime(CHECKOUT_POLL_MS)
  })
}

describe('checkout confirmation', () => {
  beforeEach(() => {
    jest.useFakeTimers()
  })
  afterEach(() => {
    jest.useRealTimers()
    search = ''
  })

  it('success: announces the payment, polls until the tier moves, then shows the plan as active and clears the param', async () => {
    search = 'checkout=success'
    mockStatusSequence([status('free'), status('free'), status('pro')])
    render(<BillingSettingsPage />)

    expect(await screen.findByTestId('checkout-notice')).toHaveTextContent(/activating your plan/i)
    expect(ROUTER.replace).toHaveBeenCalledWith('/settings/billing')

    await tick() // poll 1 → still free
    await tick() // poll 2 → pro
    await waitFor(() => expect(screen.getByTestId('checkout-notice')).toHaveTextContent(/Pro plan is active/))
    // The reload after activation renders the paid-tier controls.
    expect(await screen.findByRole('button', { name: /manage subscription/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /upgrade to pro/i })).toBeNull()
  })

  it('success: once the tier moves, the confirmation stays even if the status endpoint then fails', async () => {
    // The page used to reload() after detecting the change, which dropped it back
    // to "Loading billing…" and, on a failed refetch, to "Billing unavailable".
    search = 'checkout=success'
    let calls = 0
    global.fetch = jest.fn().mockImplementation(async () => {
      calls += 1
      if (calls <= 2) {
        return { ok: true, status: 200, json: async () => (calls === 1 ? status('free') : status('pro')) }
      }
      return { ok: false, status: 503, json: async () => ({}) }
    })
    render(<BillingSettingsPage />)
    await screen.findByTestId('checkout-notice')

    await tick() // poll → pro
    await waitFor(() => expect(screen.getByTestId('checkout-notice')).toHaveTextContent(/Pro plan is active/))
    await tick()
    await tick()
    expect(screen.getByTestId('checkout-notice')).toHaveTextContent(/Pro plan is active/)
    expect(screen.queryByText(/failed to load billing status/i)).toBeNull()
    expect(screen.queryByText(/loading billing/i)).toBeNull()
  })

  it('success but the webhook never lands: stops polling at the bound and tells the user to refresh', async () => {
    search = 'checkout=success'
    mockStatusSequence([status('free')])
    render(<BillingSettingsPage />)
    await screen.findByTestId('checkout-notice')
    const callsBeforePolling = (global.fetch as jest.Mock).mock.calls.length

    for (let i = 0; i < CHECKOUT_POLL_MAX; i += 1) await tick()
    await waitFor(() =>
      expect(screen.getByTestId('checkout-notice')).toHaveTextContent(/can take a minute/i)
    )
    const callsAtBound = (global.fetch as jest.Mock).mock.calls.length
    expect(callsAtBound - callsBeforePolling).toBe(CHECKOUT_POLL_MAX)

    await tick()
    await tick()
    expect((global.fetch as jest.Mock).mock.calls.length).toBe(callsAtBound)
  })

  it('success when the status already reports the paid tier: no polling, just the confirmation', async () => {
    search = 'checkout=success'
    mockStatusSequence([status('pro')])
    render(<BillingSettingsPage />)
    expect(await screen.findByTestId('checkout-notice')).toHaveTextContent(/Pro plan is active/)
    const calls = (global.fetch as jest.Mock).mock.calls.length
    await tick()
    expect((global.fetch as jest.Mock).mock.calls.length).toBe(calls)
  })

  it('cancelled: says so, keeps the Upgrade button, and does not poll', async () => {
    search = 'checkout=cancelled'
    mockStatusSequence([status('free')])
    render(<BillingSettingsPage />)

    expect(await screen.findByTestId('checkout-notice')).toHaveTextContent(/cancelled.*not been charged/i)
    expect(screen.getByRole('button', { name: /upgrade to pro/i })).toBeInTheDocument()
    expect(ROUTER.replace).toHaveBeenCalledWith('/settings/billing')
    const calls = (global.fetch as jest.Mock).mock.calls.length
    await tick()
    expect((global.fetch as jest.Mock).mock.calls.length).toBe(calls)
  })

  it('no param: no notice, nothing cleared', async () => {
    mockStatusSequence([status('free')])
    render(<BillingSettingsPage />)
    await screen.findByRole('button', { name: /upgrade to pro/i })
    expect(screen.queryByTestId('checkout-notice')).toBeNull()
    expect(ROUTER.replace).not.toHaveBeenCalled()
  })
})
