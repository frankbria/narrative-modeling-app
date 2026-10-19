/**
 * Every page an anonymous visitor can read, in the order the footer lists them (#772).
 *
 * The public nav, the site footer and the sitemap all read this, so a link added
 * here appears on every public page. `nav` marks the marketing pages the header
 * shows; the legal pages are footer-only. `middleware.ts` keeps its own exact-path
 * list (deny by default) and `__tests__/middleware.test.ts` holds the two equal.
 */
export interface PublicLink {
  href: string
  label: string
  nav: boolean
}

export const PUBLIC_LINKS: readonly PublicLink[] = [
  { href: '/how-it-works', label: 'How it works', nav: true },
  { href: '/pricing', label: 'Pricing', nav: true },
  { href: '/security', label: 'Security', nav: true },
  { href: '/legal/terms', label: 'Terms', nav: false },
  { href: '/legal/privacy', label: 'Privacy', nav: false },
]

export const NAV_LINKS: readonly PublicLink[] = PUBLIC_LINKS.filter((link) => link.nav)
