import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import BillingSettingsPage from '@/app/settings/billing/page'
import { UNLIMITED } from '@/lib/services/billing'

/**
 * Plan & usage page (#365).
 *
 * The states worth pinning are the ones a user actually lands in:
 *
 * - Stripe not configured — which is what the free invite-only beta runs on, and
 *   is NOT an error. Showing an upgrade button that cannot work would be worse.
 * - unlimited (-1) — must render as "unlimited", not as a 0-width bar or "-1".
 * - an entitled plan — offers "Manage", not "Upgrade".
 */
jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('tok'),
}))

const status = (overrides = {}) => ({
  configured: true,
  tier: 'free' as const,
  status: null,
  cancel_at_period_end: false,
  current_period_end: null,
  usage: { training_runs: 2, predictions: 50, uploads: 1 },
  limits: { training_runs: 10, predictions: 1000, uploads: 20 },
  ...overrides,
})

const mockStatus = (body: object) => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: jest.fn().mockResolvedValue(body),
  })
}

describe('Plan & usage', () => {
  it('renders the tier and the metered usage', async () => {
    mockStatus(status())

    render(<BillingSettingsPage />)

    await waitFor(() => expect(screen.getByText('Free')).toBeInTheDocument())
    expect(screen.getByText(/Training runs/)).toBeInTheDocument()
    expect(screen.getByText(/2 \/ 10/)).toBeInTheDocument()
  })

  it('says paid plans are off rather than offering a dead button', async () => {
    // The free invite-only beta configuration. Not an error state.
    mockStatus(status({ configured: false }))

    render(<BillingSettingsPage />)

    await waitFor(() =>
      expect(screen.getByText(/not enabled on this deployment/i)).toBeInTheDocument()
    )
    expect(screen.queryByRole('button', { name: /upgrade/i })).not.toBeInTheDocument()
  })

  it('offers an upgrade on the free tier when billing is configured', async () => {
    mockStatus(status())

    render(<BillingSettingsPage />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /upgrade to pro/i })).toBeInTheDocument()
    )
  })

  it('offers management, not an upgrade, on a paid tier', async () => {
    mockStatus(status({ tier: 'pro', status: 'active' }))

    render(<BillingSettingsPage />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /manage subscription/i })).toBeInTheDocument()
    )
    expect(screen.queryByRole('button', { name: /upgrade/i })).not.toBeInTheDocument()
  })

  it('renders an unlimited quota as unlimited, not as -1', async () => {
    mockStatus(
      status({
        tier: 'enterprise',
        status: 'active',
        limits: { training_runs: UNLIMITED, predictions: UNLIMITED, uploads: UNLIMITED },
      })
    )

    render(<BillingSettingsPage />)

    await waitFor(() => expect(screen.getAllByText(/unlimited/i).length).toBeGreaterThan(0))
    expect(screen.queryByText(/-1/)).not.toBeInTheDocument()
    // No bar to draw when there is no ceiling.
    expect(screen.queryAllByRole('progressbar')).toHaveLength(0)
  })

  it('surfaces a failure instead of rendering an empty plan', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: jest.fn().mockResolvedValue({}),
    })

    render(<BillingSettingsPage />)

    await waitFor(() =>
      expect(screen.getByText(/failed to load billing status/i)).toBeInTheDocument()
    )
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('reports a checkout failure rather than leaving the button spinning', async () => {
    mockStatus(status())

    render(<BillingSettingsPage />)
    await waitFor(() => screen.getByRole('button', { name: /upgrade to pro/i }))

    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: jest.fn().mockResolvedValue({}),
    })

    fireEvent.click(screen.getByRole('button', { name: /upgrade to pro/i }))

    await waitFor(() => expect(screen.getByText(/HTTP 503/)).toBeInTheDocument())
    // Back to actionable, not stuck on "Redirecting…".
    expect(screen.getByRole('button', { name: /upgrade to pro/i })).toBeEnabled()
  })
})
