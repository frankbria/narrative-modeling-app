import { render, screen, within } from '@testing-library/react'
import '@testing-library/jest-dom'
import { PublicNav } from '@/components/PublicNav'
import { SiteFooter } from '@/components/SiteFooter'
import { COMPANY } from '@/lib/legal/company'
import { NAV_LINKS, PUBLIC_LINKS } from '@/lib/publicLinks'

describe('PublicNav', () => {
  it('names the product, linking home, and lists every nav link from the shared list', () => {
    render(<PublicNav />)
    const nav = screen.getByRole('navigation', { name: /public/i })
    expect(within(nav).getByRole('link', { name: COMPANY.serviceName })).toHaveAttribute('href', '/')
    for (const { href, label } of NAV_LINKS) {
      expect(within(nav).getByRole('link', { name: label })).toHaveAttribute('href', href)
    }
  })
})

describe('SiteFooter links (#772 AC5)', () => {
  it('shows every public page from the shared list, in its order', () => {
    render(<SiteFooter />)
    const footer = screen.getByRole('contentinfo')
    const hrefs = within(footer)
      .getAllByRole('link')
      .map((link) => link.getAttribute('href'))
    expect(hrefs).toEqual([
      'https://github.com/frankbria/narrative-modeling-app',
      ...PUBLIC_LINKS.map((link) => link.href),
    ])
  })

  it('names the two new pages', () => {
    render(<SiteFooter />)
    expect(screen.getByRole('link', { name: 'Security' })).toHaveAttribute('href', '/security')
    expect(screen.getByRole('link', { name: 'How it works' })).toHaveAttribute('href', '/how-it-works')
  })
})
