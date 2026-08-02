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

  it('defaults to System with nothing else selected, which is what makes hydration safe', () => {
    // As first written this asserted `aria-checked` matched /true|false/ — true of
    // ANY render, so it could not fail. Flagged in the #421 review, and checking
    // properly corrected my understanding: the first render is not "nothing
    // selected". With `defaultTheme="system"` and no stored preference, `theme` is
    // already "system" on the very first render — and crucially the SERVER renders
    // the same thing, so the markup agrees and there is no mismatch to avoid.
    //
    // The assertion that can actually fail is therefore this one: System selected,
    // the other two not. Changing defaultTheme, or reintroducing a mount flag that
    // blanks the selection, both turn it red.
    renderToggle()

    expect(screen.getByRole('radio', { name: 'System' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Light' })).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByRole('radio', { name: 'Dark' })).toHaveAttribute('aria-checked', 'false')
  })

  it('moves selection with the arrow keys and keeps one tab stop (APG)', () => {
    // Three independently tabbable buttons is three tab stops for one control.
    // Flagged in the #421 review.
    renderToggle()

    const system = screen.getByRole('radio', { name: 'System' })
    expect(system).toHaveAttribute('tabindex', '0')
    expect(screen.getByRole('radio', { name: 'Light' })).toHaveAttribute('tabindex', '-1')

    fireEvent.keyDown(system, { key: 'ArrowRight' })

    // Wraps from the last option back to the first.
    expect(screen.getByRole('radio', { name: 'Light' })).toHaveAttribute('aria-checked', 'true')
  })

  it('moves backwards with ArrowLeft', () => {
    renderToggle()

    fireEvent.keyDown(screen.getByRole('radio', { name: 'System' }), { key: 'ArrowLeft' })

    expect(screen.getByRole('radio', { name: 'Dark' })).toHaveAttribute('aria-checked', 'true')
  })
})
