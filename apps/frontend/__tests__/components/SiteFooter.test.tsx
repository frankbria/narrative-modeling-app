import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { SiteFooter } from '@/components/SiteFooter'

describe('SiteFooter', () => {
  it('renders a visible link to the corresponding source (AGPL-3.0 §13)', () => {
    render(<SiteFooter />)
    const link = screen.getByRole('link', { name: /source/i })
    expect(link).toHaveAttribute(
      'href',
      'https://github.com/frankbria/narrative-modeling-app'
    )
    expect(link).toHaveTextContent(/AGPL-3\.0/i)
    // External link opened safely.
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })

  it('links to the Terms and Privacy Policy site-wide (issue #473 AC5)', () => {
    render(<SiteFooter />)
    expect(screen.getByRole('link', { name: /^terms$/i })).toHaveAttribute('href', '/legal/terms')
    expect(screen.getByRole('link', { name: /^privacy$/i })).toHaveAttribute('href', '/legal/privacy')
  })

  // It is the page's only contentinfo, so it needs no accessible name — the role
  // alone is what makes the legal links reachable via landmark navigation.
  it('is a contentinfo landmark', () => {
    render(<SiteFooter />)
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
  })

  // Sidebar is `fixed left-0 w-64 z-30 justify-between`, so its API Keys / Admin
  // / theme controls occupy this same corner when signed in. Without the offset
  // this strip covers them and swallows their clicks — the layout must pass the
  // session through, and the strip must stay under the sidebar on z.
  it('clears the sidebar when one is rendered, and never stacks above it', () => {
    const { rerender } = render(<SiteFooter withSidebar />)
    expect(screen.getByRole('contentinfo')).toHaveClass('lg:left-[17rem]')

    rerender(<SiteFooter />)
    expect(screen.getByRole('contentinfo')).not.toHaveClass('lg:left-[17rem]')
    expect(screen.getByRole('contentinfo')).toHaveClass('z-20')
  })
})
