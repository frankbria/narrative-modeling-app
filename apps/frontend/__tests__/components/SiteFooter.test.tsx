import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { SiteFooter } from '@/components/SiteFooter'

describe('SiteFooter', () => {
  it('renders a visible link to the source code, naming the licence', () => {
    render(<SiteFooter />)
    const link = screen.getByRole('link', { name: /source/i })
    expect(link).toHaveAttribute(
      'href',
      'https://github.com/frankbria/narrative-modeling-app'
    )
    expect(link).toHaveTextContent(/Apache-2\.0/i)
    // External link opened safely.
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })

  it('links to the Terms and Privacy Policy site-wide (issue #473 AC5)', () => {
    render(<SiteFooter />)
    expect(screen.getByRole('link', { name: /^terms$/i })).toHaveAttribute('href', '/legal/terms')
    expect(screen.getByRole('link', { name: /^privacy$/i })).toHaveAttribute('href', '/legal/privacy')
  })

  it('links to the public pricing page alongside the legal pages (issue #475 AC5)', () => {
    render(<SiteFooter />)
    expect(screen.getByRole('link', { name: /^pricing$/i })).toHaveAttribute('href', '/pricing')
  })

  // It is the page's only contentinfo, so it needs no accessible name — the role
  // alone is what makes the legal links reachable via landmark navigation.
  it('is a contentinfo landmark', () => {
    render(<SiteFooter />)
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
  })

  // It used to float (`fixed`) over cards and the sidebar's controls; in the page flow it covers nothing.
  it('sits in the page flow, never fixed over content', () => {
    render(<SiteFooter />)
    expect(screen.getByRole('contentinfo')).not.toHaveClass('fixed')
  })
})
