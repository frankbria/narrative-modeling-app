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

  it('is a labelled landmark so the legal links are reachable by assistive tech', () => {
    render(<SiteFooter />)
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
  })
})
