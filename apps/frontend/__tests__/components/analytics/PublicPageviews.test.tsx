/**
 * Visits are counted on the public marketing pages only, and only for a signed-out
 * visitor (#769 AC5): nothing inside the app ever reaches Plausible.
 */
import { render, waitFor } from '@testing-library/react'
import { PublicPageviews } from '@/components/analytics/PublicPageviews'

let pathname = '/'
let status: 'authenticated' | 'unauthenticated' | 'loading' = 'unauthenticated'

jest.mock('next/navigation', () => ({ usePathname: () => pathname }))
jest.mock('next-auth/react', () => ({ useSession: () => ({ data: null, status }) }))

const fetchMock = () => global.fetch as jest.Mock
const sentBodies = () => fetchMock().mock.calls.map(([, init]) => JSON.parse(init.body))

beforeEach(() => {
  pathname = '/'
  status = 'unauthenticated'
  fetchMock().mockResolvedValue({ status: 202 })
})

describe('PublicPageviews', () => {
  it('counts a signed-out visit to a marketing page', async () => {
    pathname = '/pricing'
    render(<PublicPageviews domain="sheetpredict.app" />)
    await waitFor(() => expect(fetchMock()).toHaveBeenCalledTimes(1))
    expect(sentBodies()).toEqual([
      { name: 'pageview', domain: 'sheetpredict.app', url: `${window.location.origin}/pricing` },
    ])
  })

  it('counts each marketing page the visitor moves to, once', async () => {
    const { rerender } = render(<PublicPageviews domain="sheetpredict.app" />)
    rerender(<PublicPageviews domain="sheetpredict.app" />)
    pathname = '/security'
    rerender(<PublicPageviews domain="sheetpredict.app" />)
    await waitFor(() => expect(fetchMock()).toHaveBeenCalledTimes(2))
    expect(sentBodies().map((body) => body.url)).toEqual([
      `${window.location.origin}/`,
      `${window.location.origin}/security`,
    ])
  })

  it.each(['authenticated', 'loading'] as const)('sends nothing while the session is %s', (sessionStatus) => {
    status = sessionStatus
    pathname = '/pricing'
    render(<PublicPageviews domain="sheetpredict.app" />)
    expect(fetchMock()).not.toHaveBeenCalled()
  })

  it.each(['/dashboard', '/auth/signin', '/legal/privacy', '/model/65f0c0ffee', '/pricing/extra'])(
    'sends nothing from %s',
    (path) => {
      pathname = path
      render(<PublicPageviews domain="sheetpredict.app" />)
      expect(fetchMock()).not.toHaveBeenCalled()
    },
  )

  it('sends nothing where no Plausible site is configured', () => {
    render(<PublicPageviews domain="" />)
    expect(fetchMock()).not.toHaveBeenCalled()
  })

  it('renders nothing', () => {
    const { container } = render(<PublicPageviews domain="sheetpredict.app" />)
    expect(container).toBeEmptyDOMElement()
  })
})
