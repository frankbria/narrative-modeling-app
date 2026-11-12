/**
 * What a counted visit sends to Plausible (#769 AC5). The Privacy Policy's cookie
 * section and the Plausible row in SUB_PROCESSORS describe exactly this payload.
 */
import { COUNTED_PATHS, PLAUSIBLE_EVENT_URL, pageviewEvent, sendPageview } from '@/lib/analytics/plausible'
import { NAV_LINKS } from '@/lib/publicLinks'

const fetchMock = () => global.fetch as jest.Mock

describe('COUNTED_PATHS', () => {
  it('is the landing page plus the marketing pages the public nav shows', () => {
    expect(COUNTED_PATHS).toEqual(['/', ...NAV_LINKS.map((link) => link.href)])
    expect(COUNTED_PATHS).toEqual(['/', '/how-it-works', '/pricing', '/security'])
  })
})

describe('pageviewEvent', () => {
  it('names the site and the page', () => {
    expect(pageviewEvent('sheetpredict.app', 'https://www.sheetpredict.app', '/pricing', '')).toEqual({
      name: 'pageview',
      domain: 'sheetpredict.app',
      url: 'https://www.sheetpredict.app/pricing',
    })
  })

  it('sends an outside referrer without its query string or fragment', () => {
    const event = pageviewEvent(
      'sheetpredict.app',
      'https://www.sheetpredict.app',
      '/',
      'https://news.example/item/42?id=7&token=secret#comments',
    )
    expect(event.referrer).toBe('https://news.example/item/42')
  })

  it.each([
    'https://www.sheetpredict.app/model/65f0c0ffee',
    'https://www.sheetpredict.app/auth/signin?callbackUrl=%2Fmodel%2F65f0c0ffee',
    'https://www.sheetpredict.app/pricing',
  ])('never sends one of our own pages as the referrer: %s', (ownPage) => {
    expect(pageviewEvent('sheetpredict.app', 'https://www.sheetpredict.app', '/', ownPage)).not.toHaveProperty('referrer')
  })

  it('leaves out a referrer the browser did not give or that is not an address', () => {
    expect(pageviewEvent('d', 'https://a.example', '/', '')).not.toHaveProperty('referrer')
    expect(pageviewEvent('d', 'https://a.example', '/', 'not an address')).not.toHaveProperty('referrer')
  })
})

describe('sendPageview', () => {
  const event = pageviewEvent('sheetpredict.app', 'https://www.sheetpredict.app', '/', '')

  it('posts the event to the Events API as a simple request that carries no cookie', async () => {
    fetchMock().mockResolvedValue({ status: 202 })
    await sendPageview(event)
    expect(fetchMock()).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock().mock.calls[0]
    expect(url).toBe('https://plausible.io/api/event')
    expect(url).toBe(PLAUSIBLE_EVENT_URL)
    expect(init).toEqual({
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: JSON.stringify(event),
      keepalive: true,
      credentials: 'omit',
    })
  })

  it('never fails the page when the request is blocked', async () => {
    fetchMock().mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(sendPageview(event)).resolves.toBeUndefined()
  })
})
