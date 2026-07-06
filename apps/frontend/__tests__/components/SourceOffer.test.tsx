import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { SourceOffer } from '@/components/SourceOffer'

describe('SourceOffer (AGPL-3.0 §13 source offer)', () => {
  it('renders a visible link to the corresponding source', () => {
    render(<SourceOffer />)
    const link = screen.getByRole('link', { name: /source/i })
    expect(link).toHaveAttribute(
      'href',
      'https://github.com/frankbria/narrative-modeling-app'
    )
    expect(link).toHaveTextContent(/AGPL-3\.0/i)
    // External link opened safely.
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })
})
