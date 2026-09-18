/**
 * #767 AC3: any metered metric at ≥80% shows one amber warning in the workflow
 * shell with a link to billing; under the threshold, unlimited, or on a failed
 * status fetch, nothing renders.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { UsageWarningBanner, nearingLimits } from '@/components/billing/UsageWarningBanner'
import type { BillingStatus } from '@/lib/services/billing'

jest.mock('@/lib/services/billing', () => ({
  ...jest.requireActual('@/lib/services/billing'),
  BillingService: { getStatus: jest.fn() },
}))

import { BillingService } from '@/lib/services/billing'
const getStatus = BillingService.getStatus as jest.Mock

const status = (usage: Record<string, number>, limits: Record<string, number>, tier = 'free'): BillingStatus =>
  ({
    configured: true,
    tier,
    status: null,
    cancel_at_period_end: false,
    current_period_end: null,
    usage,
    limits,
  }) as BillingStatus

const FREE = { training_runs: 5, predictions: 1000, uploads: 10, ai_calls: 30 }

describe('nearingLimits', () => {
  it('reports metrics at or above 80%, never unlimited ones', () => {
    const result = nearingLimits(
      status({ uploads: 8, predictions: 999999, training_runs: 3 }, { ...FREE, predictions: -1 })
    )
    expect(result).toEqual([{ metric: 'uploads', used: 8, limit: 10, pct: 80 }])
  })
})

describe('UsageWarningBanner', () => {
  it('warns with the backend numbers and links to billing at 80%', async () => {
    getStatus.mockResolvedValue(status({ uploads: 8 }, FREE))
    render(<UsageWarningBanner />)

    const banner = await screen.findByRole('status')
    expect(banner).toHaveTextContent("80% of your Free plan's uploads (8 of 10)")
    expect(screen.getByRole('link', { name: /plan and usage/i })).toHaveAttribute('href', '/settings/billing')
  })

  it('lists every metric that is nearing, past the wall included', async () => {
    getStatus.mockResolvedValue(status({ uploads: 10, ai_calls: 27 }, FREE))
    render(<UsageWarningBanner />)
    const banner = await screen.findByRole('status')
    expect(banner).toHaveTextContent("100% of your Free plan's uploads (10 of 10)")
    expect(banner).toHaveTextContent("90% of your Free plan's AI calls (27 of 30)")
  })

  it('renders nothing under the threshold', async () => {
    getStatus.mockResolvedValue(status({ uploads: 7, training_runs: 3 }, FREE))
    render(<UsageWarningBanner />)
    await waitFor(() => expect(getStatus).toHaveBeenCalled())
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('renders nothing when the status fetch fails', async () => {
    getStatus.mockRejectedValue(new Error('Billing request failed (HTTP 503)'))
    render(<UsageWarningBanner />)
    await waitFor(() => expect(getStatus).toHaveBeenCalled())
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('a malformed status body renders nothing instead of crashing the layout', async () => {
    // CI caught this: an e2e mock answered /billing/status with `{}` and the throw
    // blanked every authenticated page, the stage-guard banner included.
    getStatus.mockResolvedValue({} as BillingStatus)
    render(<UsageWarningBanner />)
    await waitFor(() => expect(getStatus).toHaveBeenCalled())
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('can be dismissed', async () => {
    getStatus.mockResolvedValue(status({ uploads: 9 }, FREE))
    render(<UsageWarningBanner />)
    await screen.findByRole('status')
    fireEvent.click(screen.getByRole('button', { name: /dismiss usage warning/i }))
    expect(screen.queryByRole('status')).toBeNull()
  })
})
