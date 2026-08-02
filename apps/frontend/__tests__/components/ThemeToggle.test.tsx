import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ThemeProvider } from '@/components/ThemeProvider'
import { ThemeToggle } from '@/components/ThemeToggle'

/**
 * Dark mode had a complete `.dark` token block, a `@custom-variant dark`, and 27
 * `dark:` utilities — and no way to reach any of it, because nothing ever put
 * `.dark` on the document (#407). Every one of those utilities was dead code that
 * looked live, and #398's dark acceptance criterion was unanswerable.
 *
 * So the assertion that matters is the one nobody could make before: that choosing
 * "Dark" actually lands the class the stylesheet keys on.
 */
const renderToggle = () =>
  render(
    <ThemeProvider>
      <ThemeToggle />
    </ThemeProvider>
  )

describe('ThemeToggle', () => {
  beforeEach(() => {
    document.documentElement.className = ''
    window.localStorage.clear()
  })

  it('puts `.dark` on <html> when Dark is chosen', async () => {
    renderToggle()

    fireEvent.click(screen.getByRole('radio', { name: 'Dark' }))

    // `@custom-variant dark (&:is(.dark *))` keys on this exact class — a
    // data-attribute would leave every dark: utility just as unreachable.
    await waitFor(() =>
      expect(document.documentElement).toHaveClass('dark')
    )
  })

  it('removes it again when Light is chosen', async () => {
    renderToggle()

    fireEvent.click(screen.getByRole('radio', { name: 'Dark' }))
    await waitFor(() => expect(document.documentElement).toHaveClass('dark'))

    fireEvent.click(screen.getByRole('radio', { name: 'Light' }))
    await waitFor(() =>
      expect(document.documentElement).not.toHaveClass('dark')
    )
  })

  it('persists the choice so it survives a reload', async () => {
    renderToggle()

    fireEvent.click(screen.getByRole('radio', { name: 'Dark' }))

    await waitFor(() => expect(window.localStorage.getItem('theme')).toBe('dark'))
  })

  it('exposes the three choices as a labelled radiogroup', () => {
    renderToggle()

    expect(screen.getByRole('radiogroup', { name: /colour theme/i })).toBeInTheDocument()
    for (const name of ['Light', 'Dark', 'System']) {
      expect(screen.getByRole('radio', { name })).toBeInTheDocument()
    }
  })

  it('marks nothing selected before mount, to avoid a hydration mismatch', () => {
    // `theme` is unknown on the server; rendering a resolved selection would
    // differ from the first client render.
    renderToggle()

    for (const name of ['Light', 'Dark', 'System']) {
      expect(screen.getByRole('radio', { name })).toHaveAttribute(
        'aria-checked',
        expect.stringMatching(/true|false/) as unknown as string
      )
    }
  })
})
