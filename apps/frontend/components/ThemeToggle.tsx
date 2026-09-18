'use client'

import { useRef, useSyncExternalStore } from 'react'
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
 * Nothing is selected until hydration. next-themes cannot read localStorage on the
 * server, so `theme` is `undefined` there and `"system"` (or the stored choice) in
 * the browser; rendering the selection straight from it made the server's
 * `aria-checked="false"` disagree with the client's `true`, a hydration mismatch
 * React never patches up (`ThemeToggle.hydration.test.tsx`). `useSyncExternalStore`
 * reports false while hydrating and true afterwards, with no setState in an effect.
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
const noSubscription = () => () => {}

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const hydrated = useSyncExternalStore(noSubscription, () => true, () => false)
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
        const selected = hydrated && theme === value
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
            // Before hydration nothing is selected, so System holds it.
            tabIndex={selected || (!hydrated && value === 'system') ? 0 : -1}
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
