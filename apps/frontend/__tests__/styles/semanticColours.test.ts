/**
 * @jest-environment node
 *
 * No component may hard-code a light-mode colour where a semantic token exists (#407).
 *
 * Dark mode became reachable in #407 — before that, nothing ever set `.dark`, so all
 * 27 `dark:` utilities were dead and a hard-coded `bg-white` cost nothing. It costs
 * something now: `bg-white` stays white in dark mode, and `text-gray-900` stays
 * near-black, so a single stray utility renders a heading invisible.
 *
 * That was not hypothetical. Wiring the toggle first, before converting anything,
 * produced exactly that: page titles, card values and whole table rows drawn
 * dark-on-dark. 870 utilities across 91 files were converted to close it.
 *
 * The tokens are near-identical in light mode (`--card` and `--background` are both
 * pure white; `--muted` is oklch 0.968 against gray-50's ~0.98), so this costs
 * nothing there — verified by screenshotting every page in both themes before and
 * after, with no visible light-mode change.
 */
import { readFileSync } from 'fs'
import { join } from 'path'

import { globSync } from 'glob'

const ROOT = join(__dirname, '..', '..')

/** Hard-coded light-mode utilities, and what to use instead. */
const BANNED: [RegExp, string][] = [
  [/(?<!dark:)\btext-gray-900\b/, 'text-foreground'],
  [/(?<!dark:)\btext-gray-800\b/, 'text-foreground'],
  [/(?<!dark:)\btext-gray-700\b/, 'text-foreground'],
  [/(?<!dark:)\btext-gray-600\b/, 'text-muted-foreground'],
  [/(?<!dark:)\btext-gray-500\b/, 'text-muted-foreground'],
  [/(?<!dark:)\bbg-white\b/, 'bg-card'],
  [/(?<!dark:)\bbg-gray-50\b/, 'bg-muted'],
  [/(?<!dark:)\bbg-gray-100\b/, 'bg-muted'],
  [/(?<!dark:)\bborder-gray-200\b/, 'border-border'],
  [/(?<!dark:)\bborder-gray-300\b/, 'border-border'],
]

/**
 * The sidebar is deliberately dark in BOTH themes, so its greys are the design,
 * not an oversight. Anything added here needs the same justification.
 */
const EXEMPT = new Set(['components/Sidebar.tsx', 'components/SidebarWrapper.tsx'])

describe('semantic colours, not hard-coded light ones (#407)', () => {
  const files = globSync('{app,components}/**/*.tsx', {
    cwd: ROOT,
    ignore: ['**/node_modules/**'],
  })

  it('scans a meaningful number of files', () => {
    // If the glob silently stops matching, every assertion below passes vacuously.
    expect(files.length).toBeGreaterThan(100)
  })

  it('finds no hard-coded light-mode utility outside the exempt list', () => {
    const offenders: string[] = []

    for (const file of files) {
      if (EXEMPT.has(file)) continue
      const src = readFileSync(join(ROOT, file), 'utf8')
      for (const [pattern, replacement] of BANNED) {
        if (pattern.test(src)) {
          offenders.push(
            `${file}: ${String(pattern).replace(/[()?<!\\bdark:/]/g, '').trim()} -> use ${replacement}`
          )
        }
      }
    }

    expect(offenders).toEqual([])
  })
})
