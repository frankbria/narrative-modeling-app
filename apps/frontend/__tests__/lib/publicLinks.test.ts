/**
 * The one list of public pages (#772 AC5). The nav, the footer and the sitemap
 * all read it, so a link added once appears everywhere; middleware keeps its own
 * explicit exact-path list (deny by default), and this test holds the two equal.
 */
import { existsSync } from 'fs'
import { join } from 'path'
import { NAV_LINKS, PUBLIC_LINKS } from '@/lib/publicLinks'

const APP = join(__dirname, '../../app')

describe('PUBLIC_LINKS', () => {
  it('lists the how-it-works, pricing, security, terms and privacy pages', () => {
    expect(PUBLIC_LINKS.map((link) => link.href)).toEqual([
      '/how-it-works',
      '/pricing',
      '/security',
      '/legal/terms',
      '/legal/privacy',
    ])
  })

  it('points every link at a page that exists', () => {
    for (const { href } of PUBLIC_LINKS) {
      expect(existsSync(join(APP, href, 'page.tsx'))).toBe(true)
    }
  })

  it('puts the three marketing pages in the nav and leaves the legal pages to the footer', () => {
    expect(NAV_LINKS.map((link) => link.href)).toEqual(['/how-it-works', '/pricing', '/security'])
  })
})
