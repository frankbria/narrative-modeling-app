/**
 * #767 AC2: the single PlanLimitDialog renders the backend's numbers and the
 * one action that lifts the limit for the caller's tier.
 */
import { render, screen, fireEvent, act } from '@testing-library/react'
import { PlanLimitDialog } from '@/components/billing/PlanLimitDialog'
import { planLimit } from '@/lib/billing/planLimit'
import { QuotaExceededError } from '@/lib/services/apiError'
import { planFor, priceLabel } from '@/lib/billing/plans'
import { COMPANY } from '@/lib/legal/company'

const detail = (overrides: Record<string, unknown> = {}) => ({
  error: 'quota_exceeded',
  metric: 'training_runs',
  limit: 5,
  used: 5,
  tier: 'free',
  resets_at: '2026-10-01T00:00:00+00:00',
  message: 'You have used all 5 training runs included in the free plan this month.',
  upgrade_available: true,
  ...overrides,
})

const show = (overrides: Record<string, unknown> = {}) =>
  act(() => planLimit.show(new QuotaExceededError(detail(overrides), 'fallback')))

beforeEach(() => act(() => planLimit.dismiss()))

describe('PlanLimitDialog', () => {
  it('renders nothing while no limit has been hit', () => {
    render(<PlanLimitDialog />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('FREE: names the metric, shows used/limit and the reset date, and links Upgrade to billing with the price', () => {
    render(<PlanLimitDialog />)
    show()

    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent("You have reached the Free plan's training runs limit")
    expect(screen.getByTestId('plan-limit-usage')).toHaveTextContent('5 of 5')
    expect(dialog).toHaveTextContent(/resets on .*2026/)

    const upgrade = screen.getByRole('link', { name: /upgrade to pro/i })
    expect(upgrade).toHaveAttribute('href', '/settings/billing')
    expect(upgrade).toHaveTextContent(priceLabel(planFor('pro')))
    expect(screen.queryByRole('link', { name: /contact us/i })).toBeNull()
  })

  it('PRO: offers the Enterprise contact link instead of an upgrade', () => {
    render(<PlanLimitDialog />)
    show({ tier: 'pro', limit: 100, used: 100, upgrade_available: false })

    expect(screen.getByRole('dialog')).toHaveTextContent("Pro plan's training runs limit")
    expect(screen.getByTestId('plan-limit-usage')).toHaveTextContent('100 of 100')
    const contact = screen.getByRole('link', { name: /contact us/i })
    expect(contact.getAttribute('href')).toBe(`mailto:${COMPANY.supportEmail}?subject=Enterprise%20plan`)
    expect(screen.queryByRole('link', { name: /upgrade/i })).toBeNull()
  })

  it('ENTERPRISE: says it is the highest plan and offers no action but the reset', () => {
    render(<PlanLimitDialog />)
    show({ tier: 'enterprise', metric: 'ai_calls', limit: 5000, used: 5000, upgrade_available: false })

    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('highest plan')
    expect(dialog).toHaveTextContent('5,000 of 5,000')
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('tolerates the thin variant: opens without numbers, still dismissable', () => {
    render(<PlanLimitDialog />)
    act(() =>
      planLimit.show(new QuotaExceededError({ error: 'quota_exceeded', metric: 'predictions' }, 'Prediction failed'))
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('You have reached your predictions limit')
    expect(screen.queryByTestId('plan-limit-usage')).toBeNull()
    expect(dialog).not.toHaveTextContent('resets on')
  })

  it('"Not now" clears the store and closes the dialog', () => {
    render(<PlanLimitDialog />)
    show()
    fireEvent.click(screen.getByRole('button', { name: /not now/i }))
    expect(planLimit.get()).toBeNull()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('following the Upgrade link clears the store so the dialog does not reopen on the billing page', () => {
    render(<PlanLimitDialog />)
    show()
    fireEvent.click(screen.getByRole('link', { name: /upgrade to pro/i }))
    expect(planLimit.get()).toBeNull()
  })
})
