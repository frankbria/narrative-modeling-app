/**
 * @jest-environment node
 *
 * robots.txt and sitemap.xml for the public surface (#766). The same image runs
 * on dev. and www., so what they say is decided per request from the runtime
 * environment, and anything but an explicit production hides the site.
 */
import { readdirSync } from 'fs'
import { join } from 'path'
import robots from '@/app/robots'
import sitemap from '@/app/sitemap'

const ORIGINAL = { ...process.env }
afterEach(() => {
  process.env = { ...ORIGINAL }
})

function rulesOf(result: ReturnType<typeof robots>) {
  return [result.rules].flat()
}

describe('robots.txt', () => {
  it.each([undefined, 'staging', 'development'])('disallows everything when ENVIRONMENT is %p', (value) => {
    if (value === undefined) delete process.env.ENVIRONMENT
    else process.env.ENVIRONMENT = value
    const result = robots()
    expect(rulesOf(result)).toEqual([{ userAgent: '*', disallow: '/' }])
    expect(result.sitemap).toBeUndefined()
  })

  it('in production allows the public pages, disallows the app and names the sitemap', () => {
    process.env.ENVIRONMENT = 'production'
    process.env.NEXTAUTH_URL = 'https://www.sheetpredict.app'
    const result = robots()
    const [rule] = rulesOf(result)
    expect(rule.allow).toEqual(['/$', '/pricing$', '/legal/'])
    expect(rule.disallow).toBe('/')
    expect(result.sitemap).toBe('https://www.sheetpredict.app/sitemap.xml')
  })
})

describe('sitemap.xml', () => {
  it('lists the landing page, pricing and every legal page on the runtime host', () => {
    process.env.NEXTAUTH_URL = 'https://dev.sheetpredict.app'
    const legal = readdirSync(join(__dirname, '../../app/legal'), { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .map((e) => `https://dev.sheetpredict.app/legal/${e.name}`)
    expect(legal.length).toBeGreaterThan(0)
    expect(sitemap().map((entry) => entry.url).sort()).toEqual(
      ['https://dev.sheetpredict.app/', 'https://dev.sheetpredict.app/pricing', ...legal].sort(),
    )
  })

  it('follows the host when the same image runs elsewhere', () => {
    process.env.NEXTAUTH_URL = 'https://www.sheetpredict.app'
    expect(sitemap().every((entry) => entry.url.startsWith('https://www.sheetpredict.app/'))).toBe(true)
  })
})
