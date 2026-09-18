import React, { act } from 'react'
import { renderToString } from 'react-dom/server'
import { hydrateRoot } from 'react-dom/client'
import { ThemeToggle } from '@/components/ThemeToggle'

// next-themes cannot read localStorage on the server, so `useTheme().theme` is
// undefined there and "system" in the browser. Model exactly that split.
let mockTheme: string | undefined
jest.mock('next-themes', () => ({
  useTheme: () => ({ theme: mockTheme, setTheme: jest.fn() }),
}))

it('hydrates the server markup without a mismatch, then shows the stored theme', async () => {
  mockTheme = undefined
  const container = document.createElement('div')
  container.innerHTML = renderToString(<ThemeToggle />)
  document.body.appendChild(container)

  mockTheme = 'system'
  const errors = jest.spyOn(console, 'error').mockImplementation(() => {})
  await act(async () => {
    hydrateRoot(container, <ThemeToggle />)
  })

  expect(errors.mock.calls.flat().join(' ')).not.toMatch(/hydrat/i)
  errors.mockRestore()
  const system = container.querySelector('[aria-label="System"]')
  expect(system).toHaveAttribute('aria-checked', 'true')
})
