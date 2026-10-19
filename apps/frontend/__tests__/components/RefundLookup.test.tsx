import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RefundLookup } from '@/components/admin/RefundLookup'

jest.mock('@/lib/auth-helpers', () => ({ getAuthToken: jest.fn().mockResolvedValue('tok') }))

function respond(status: number, body: unknown) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status < 400,
    status,
    json: async () => body,
  }) as unknown as typeof fetch
}

async function lookUp(userId: string) {
  render(<RefundLookup />)
  await userEvent.type(screen.getByLabelText('User id'), userId)
  await userEvent.click(screen.getByRole('button', { name: 'Look up' }))
}

describe('RefundLookup', () => {
  it('shows the three refund-window fields for the user id entered', async () => {
    respond(200, {
      refund_eligible: true,
      refund_window_ends_at: '2026-10-30T12:00:00+00:00',
      first_paid_at: '2026-10-16T12:00:00+00:00',
    })
    await lookUp('tenant 1')

    expect(await screen.findByText('Eligible')).toBeInTheDocument()
    expect(screen.getByText('Refund window ends').nextSibling).toHaveTextContent('2026-10-30')
    expect(screen.getByText('First paid').nextSibling).toHaveTextContent('2026-10-16')
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0]
    expect(url).toMatch(/\/admin\/billing\/tenant%201\/refund$/)
    expect(init.headers).toEqual({ Authorization: 'Bearer tok' })
  })

  it('shows dashes, not a date, for a subscription that never paid', async () => {
    respond(200, { refund_eligible: false, refund_window_ends_at: null, first_paid_at: null })
    await lookUp('tenant-1')

    expect(await screen.findByText('Not eligible')).toBeInTheDocument()
    expect(screen.getByText('First paid').nextSibling).toHaveTextContent('—')
  })

  it('says so when the user has no subscription', async () => {
    respond(404, { detail: 'no subscription for that user' })
    await lookUp('nobody')

    expect(await screen.findByText('no subscription for that user')).toBeInTheDocument()
    expect(screen.queryByText('Eligible')).not.toBeInTheDocument()
  })

  it('has no refund button', () => {
    render(<RefundLookup />)
    expect(screen.queryByRole('button', { name: /refund/i })).not.toBeInTheDocument()
  })
})
