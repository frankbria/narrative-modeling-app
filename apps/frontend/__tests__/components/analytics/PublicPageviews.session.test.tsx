/**
 * The same component under next-auth's real SessionProvider, as app/layout.tsx
 * mounts it: the server's answer (`session={null}` or a session) decides whether a
 * visit is counted, with no client round trip (#769 AC5).
 */
import { render, waitFor } from '@testing-library/react'
import type { Session } from 'next-auth'
import { PublicPageviews } from '@/components/analytics/PublicPageviews'

jest.mock('next-auth/react', () => jest.requireActual('next-auth/react'))
jest.mock('next/navigation', () => ({ usePathname: () => '/pricing' }))

const { SessionProvider } = jest.requireActual<typeof import('next-auth/react')>('next-auth/react')
const fetchMock = () => global.fetch as jest.Mock
const plausibleCalls = () => fetchMock().mock.calls.filter(([url]) => String(url).startsWith('https://plausible.io/'))

const signedIn: Session = {
  user: { id: '65f0c0ffee65f0c0ffee65f0', email: 'someone@example.com' },
  expires: '2999-01-01T00:00:00.000Z',
}

beforeEach(() => {
  fetchMock().mockResolvedValue({ ok: true, status: 202, json: async () => ({}) })
})

describe('PublicPageviews under the real SessionProvider', () => {
  it('counts the visit when the server found no session', async () => {
    render(
      <SessionProvider session={null}>
        <PublicPageviews domain="sheetpredict.app" />
      </SessionProvider>,
    )
    await waitFor(() => expect(plausibleCalls()).toHaveLength(1))
  })

  it('sends nothing when the server found a session', async () => {
    render(
      <SessionProvider session={signedIn}>
        <PublicPageviews domain="sheetpredict.app" />
      </SessionProvider>,
    )
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(plausibleCalls()).toHaveLength(0)
  })
})
