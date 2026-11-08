import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ReviewPage from '@/app/review/page'

jest.mock('@/lib/auth-helpers', () => ({ getAuthToken: jest.fn().mockResolvedValue('tok') }))

const reply = (status: number, body: unknown) =>
  (global.fetch as jest.Mock).mockResolvedValue({ ok: status < 400, status, json: async () => body })

const ROW = {
  dataset_id: 'd1', filename: 'sales.csv', num_rows: 120, num_columns: 4, created_at: '2026-11-01T00:00:00Z',
}

describe('/review (#1167)', () => {
  it('lists the datasets and opens the chosen one in Explore', async () => {
    reply(200, { datasets: [ROW] })
    render(<ReviewPage />)
    fireEvent.click(await screen.findByRole('button', { name: /sales\.csv/ }))
    expect((global as unknown as { __NEXT_ROUTER_MOCKS__: { push: jest.Mock } }).__NEXT_ROUTER_MOCKS__.push).toHaveBeenCalledWith('/explore/d1')
    expect(String((global.fetch as jest.Mock).mock.calls[0][0])).toContain('/datasets?page=1')
  })

  it('sends a user with no datasets to Load Data', async () => {
    reply(200, { datasets: [] })
    render(<ReviewPage />)
    expect(await screen.findByRole('link', { name: 'Load Data' })).toHaveAttribute('href', '/upload')
  })

  it('says one plain sentence when the list cannot load, never the JSON body', async () => {
    reply(422, { detail: [{ type: 'value_error', msg: 'bad' }] })
    render(<ReviewPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('We could not load your datasets.')
    expect(screen.queryByText(/value_error/)).toBeNull()
    reply(200, { datasets: [ROW] })
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(screen.getByText('sales.csv')).toBeInTheDocument())
  })
})
