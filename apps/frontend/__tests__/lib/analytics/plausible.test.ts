/**
 * What a counted visit sends to Plausible (#769 AC5). The Privacy Policy's cookie
 * section and the Plausible row in SUB_PROCESSORS describe exactly this payload.
 */
import { CAMPAIGN_PARAMETERS, COUNTED_PATHS, PLAUSIBLE_EVENT_URL, pageviewEvent, sendPageview } from '@/lib/analytics/plausible'
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

  it('sends the referring site as its origin alone, never a path or query string', () => {
    const from = (referrer: string) =>
      pageviewEvent('sheetpredict.app', 'https://www.sheetpredict.app', '/', referrer).referrer
    expect(from('https://news.example/item/42?id=7&token=secret#comments')).toBe('https://news.example')
    // A sibling host of ours is an outside origin, so its path must not travel either.
    expect(from('https://dev.sheetpredict.app/model/65f0c0ffee')).toBe('https://dev.sheetpredict.app')
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
    expect(pageviewEvent('d', 'https://a.example', '/', 'about:blank')).not.toHaveProperty('referrer')
  })
})

describe('campaign parameters', () => {
  const counted = (search: string) =>
    pageviewEvent('sheetpredict.app', 'https://www.sheetpredict.app', '/pricing', '', search).url

  it('are the ones Plausible reads for its source and campaign reports, and no others', () => {
    expect(CAMPAIGN_PARAMETERS).toEqual(['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'ref'])
  })

  it('reach Plausible in the page address, in the allowlist order', () => {
    expect(counted('?utm_campaign=launch&utm_source=newsletter&utm_medium=email&utm_term=forecast&utm_content=hero&ref=producthunt')).toBe(
      'https://www.sheetpredict.app/pricing?utm_source=newsletter&utm_medium=email&utm_campaign=launch&utm_content=hero&utm_term=forecast&ref=producthunt',
    )
  })

  it('leave everything else in the query string behind', () => {
    expect(counted('?email=ana%40example.com&utm_source=newsletter&callbackUrl=%2Fmodel%2F65f0c0ffee&token=secret')).toBe(
      'https://www.sheetpredict.app/pricing?utm_source=newsletter',
    )
  })

  it.each(['', '?', '?email=ana%40example.com', '?utm_source=', '?UTM_SOURCE=newsletter'])(
    'leave the address bare when none is given: %p',
    (search) => {
      expect(counted(search)).toBe('https://www.sheetpredict.app/pricing')
    },
  )

  it('leave out a tag whose value could be an email address', () => {
    expect(counted('?utm_source=newsletter&utm_content=ana%40example.com&ref=a@b')).toBe(
      'https://www.sheetpredict.app/pricing?utm_source=newsletter',
    )
  })

  it('send a long value whole: no length cap, so the policy\'s "as the link wrote them" holds (#1227)', () => {
    const longCampaign = 'spring-launch-'.repeat(40)
    expect(counted(`?utm_campaign=${longCampaign}`)).toBe(`https://www.sheetpredict.app/pricing?utm_campaign=${longCampaign}`)
  })

  it('keep the first value of a repeated parameter and encode it again', () => {
    expect(counted('?utm_campaign=spring%20sale&utm_campaign=other')).toBe(
      'https://www.sheetpredict.app/pricing?utm_campaign=spring+sale',
    )
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
