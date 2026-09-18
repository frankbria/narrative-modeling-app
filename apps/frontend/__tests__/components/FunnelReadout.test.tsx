import { render, screen } from '@testing-library/react'
import { FunnelReadout } from '@/components/admin/FunnelReadout'

jest.mock('@/lib/auth-helpers', () => ({ getAuthToken: jest.fn().mockResolvedValue('tok') }))

const FUNNEL = {
  days: 30,
  signups: 4,
  signups_per_day: [{ date: '2026-08-29', count: 2 }],
  activation: { cohort: 3, activated: 1, rate: 1 / 3 },
  quota_denials_by_metric: { uploads: 2 },
  checkout_started: 2,
  checkout_completed: 1,
  subscriptions_cancelled: 0,
}

function respond(status: number, body: unknown) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status < 400,
    status,
    json: async () => body,
  }) as unknown as typeof fetch
}

describe('FunnelReadout', () => {
  it('shows the funnel as numbers from the admin endpoint', async () => {
    respond(200, FUNNEL)
    render(<FunnelReadout />)

    expect(await screen.findByText('1 / 3 (33%)')).toBeInTheDocument()
    expect(screen.getByText('402s: uploads').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('2026-08-29: 2')).toBeInTheDocument()
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0]
    expect(url).toMatch(/\/admin\/funnel\?days=30$/)
    expect(init.headers).toEqual({ Authorization: 'Bearer tok' })
  })

  it('shows a dash, not NaN, when no cohort is old enough to judge', async () => {
    respond(200, { ...FUNNEL, activation: { cohort: 0, activated: 0, rate: null } })
    render(<FunnelReadout />)

    expect(await screen.findByText('—')).toBeInTheDocument()
  })

  it('surfaces a failure instead of empty numbers', async () => {
    respond(404, { detail: 'Not Found' })
    render(<FunnelReadout />)

    expect(await screen.findByText('Not Found')).toBeInTheDocument()
  })
})
