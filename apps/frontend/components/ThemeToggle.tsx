'use client'

import { useTheme } from 'next-themes'
import { Monitor, Moon, Sun } from 'lucide-react'

const OPTIONS = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'system', label: 'System', Icon: Monitor },
] as const

/**
 * The control that makes dark mode reachable at all (#407).
 *
 * No `mounted` flag: `useTheme()` already returns `undefined` until next-themes
 * has read storage on the client, so the server render and the first client
 * render agree by construction — nothing is marked selected in either. Tracking
 * mount separately would mean a setState inside an effect, which
 * `react-hooks/set-state-in-effect` rejects outright here.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <div
      role="radiogroup"
      aria-label="Colour theme"
      className="flex items-center gap-1 rounded-md border border-white/10 p-1"
    >
      {OPTIONS.map(({ value, label, Icon }, index) => {
        const selected = theme === value
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={label}
            title={label}
            // APG radiogroup: one tab stop for the group, arrows move within it.
            // Without this every option is independently tabbable, which is three
            // stops for one control (#421 review).
            tabIndex={selected || (!theme && index === 0) ? 0 : -1}
            onKeyDown={(e) => {
              const delta =
                e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1
                : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1
                : 0
              if (!delta) return
              e.preventDefault()
              const next = OPTIONS[(index + delta + OPTIONS.length) % OPTIONS.length]
              setTheme(next.value)
              // Selection follows focus in a radiogroup, so move focus with it.
              const group = e.currentTarget.parentElement
              const buttons = group?.querySelectorAll<HTMLButtonElement>('[role="radio"]')
              buttons?.[(index + delta + OPTIONS.length) % OPTIONS.length]?.focus()
            }}
            onClick={() => setTheme(value)}
            className={`flex flex-1 items-center justify-center rounded p-1.5 transition-colors ${
              selected
                ? 'bg-card/15 text-white'
                : 'text-gray-400 hover:bg-card/10 hover:text-white'
            }`}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
          </button>
        )
      })}
    </div>
  )
}
