'use client'

import { useRef } from 'react'
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
 * No `mounted` flag — and not for the reason this comment used to give. With
 * `defaultTheme="system"` and no stored preference, `useTheme()` returns `"system"`
 * on the very *first* render, and the server renders the same value, so the markup
 * agrees and there is nothing to guard against. (The earlier claim that `theme` is
 * `undefined` until storage is read was simply wrong; `ThemeToggle.test.tsx` now
 * asserts what actually happens.) A mount flag would also mean a setState inside an
 * effect, which `react-hooks/set-state-in-effect` rejects here.
 *
 * Implements the APG radiogroup keyboard pattern: one tab stop for the group,
 * arrows move and select (selection follows focus), Home/End jump to the ends.
 *
 * The colours here are deliberately fixed rather than semantic, and this is the
 * real reason the file is in `semanticColours.test.ts`'s EXEMPT set. The control
 * lives inside the Sidebar, which is dark in BOTH themes, so it needs a constant
 * white overlay: `bg-card` would follow the global theme and resolve to a light
 * card colour in light mode, or blend into the sidebar in dark. `bg-white/15` is
 * correct here specifically — do not "fix" it back to a token.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  // Refs rather than walking `parentElement.querySelectorAll('[role=radio]')`: the
  // DOM walk holds only while these stay direct children, and would break silently
  // the moment a wrapper element is introduced.
  const buttons = useRef<(HTMLButtonElement | null)[]>([])

  const focusOption = (index: number) => {
    const next = (index + OPTIONS.length) % OPTIONS.length
    setTheme(OPTIONS[next].value)
    buttons.current[next]?.focus()
  }

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
            ref={(el) => {
              buttons.current[index] = el
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={label}
            title={label}
            // Roving tabindex: the selected option is the group's single tab stop.
            // `theme` is always set (see above), so no fallback branch is needed —
            // one here would be dead code.
            tabIndex={selected ? 0 : -1}
            onKeyDown={(e) => {
              switch (e.key) {
                case 'ArrowRight':
                case 'ArrowDown':
                  e.preventDefault()
                  return focusOption(index + 1)
                case 'ArrowLeft':
                case 'ArrowUp':
                  e.preventDefault()
                  return focusOption(index - 1)
                case 'Home':
                  e.preventDefault()
                  return focusOption(0)
                case 'End':
                  e.preventDefault()
                  return focusOption(OPTIONS.length - 1)
                default:
                  return
              }
            }}
            onClick={() => setTheme(value)}
            className={`flex flex-1 items-center justify-center rounded p-1.5 transition-colors ${
              selected
                ? 'bg-white/15 text-white'
                : 'text-gray-400 hover:bg-white/10 hover:text-white'
            }`}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
          </button>
        )
      })}
    </div>
  )
}
