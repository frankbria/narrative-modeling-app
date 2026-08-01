/**
 * @jest-environment node
 *
 * Regression guard for the bug fixed in #345.
 *
 * `tailwind.config.mjs` wrapped every colour token in `hsl(...)` while `globals.css`
 * defined those tokens as `oklch(...)`. The composed declaration was `hsl(oklch(...))`,
 * which is invalid CSS, so browsers dropped it and ~35 theme utilities silently
 * rendered as transparent or black. Nothing failed: the build was green, every test
 * passed, and the broken default (white background, black text) looked close enough
 * to the intended theme that it shipped unnoticed.
 *
 * That is the point of this file. The failure lived in the *compiled stylesheet*, so
 * asserting against compiled output is what catches it. A component test cannot —
 * it never runs Tailwind. This compiles globals.css through the real PostCSS plugin
 * and checks the tokens actually resolve, which also covers the next CSS-toolchain
 * bump that breaks them a different way.
 */
import { readFileSync } from 'fs'
import { join } from 'path'

import postcss from 'postcss'
import tailwind from '@tailwindcss/postcss'

const CSS_PATH = join(__dirname, '..', '..', 'app', 'globals.css')

/** Every semantic token the theme promises, in both modes. */
const THEME_TOKENS = [
  'background', 'foreground',
  'card', 'card-foreground',
  'popover', 'popover-foreground',
  'primary', 'primary-foreground',
  'secondary', 'secondary-foreground',
  'muted', 'muted-foreground',
  'accent', 'accent-foreground',
  'destructive', 'destructive-foreground',
  'border', 'input', 'ring',
]

let css = ''

beforeAll(async () => {
  const source = readFileSync(CSS_PATH, 'utf8')
  const result = await postcss([tailwind()]).process(source, { from: CSS_PATH })
  css = result.css
}, 60_000)

/** Collect custom-property declarations from every block matching `selector`. */
function tokensIn(selector: RegExp): Record<string, string> {
  const found: Record<string, string> = {}
  for (const block of css.matchAll(new RegExp(`${selector.source}\\s*\\{([^}]*)\\}`, 'g'))) {
    for (const decl of block[1].matchAll(/--([a-z-]+):\s*([^;]+)/g)) {
      found[decl[1]] = decl[2].trim()
    }
  }
  return found
}

describe('globals.css compiles to a working theme', () => {
  it('compiles at all', () => {
    expect(css.length).toBeGreaterThan(1000)
  })

  it('never composes a colour function around a custom property', () => {
    // The exact shape of the #345 bug: hsl(var(--x)) where --x is not an
    // <hue-rotation>. Invalid, silently dropped by every browser.
    const composed = css.match(/(?:hsl|rgb|hwb|lab|lch|oklab|oklch)\(\s*var\(--/g) ?? []
    expect(composed).toEqual([])
  })

  it.each(THEME_TOKENS)('defines --%s in both light and dark', (token) => {
    const light = tokensIn(/:root[^{]*/)
    const dark = tokensIn(/\.dark[^{]*/)

    expect(light[token]).toBeDefined()
    expect(dark[token]).toBeDefined()
  })

  it('gives light and dark genuinely different values', () => {
    // Dark mode was entirely non-functional before #345 — the light and dark
    // screenshots came out byte-identical. Identical values would mean that
    // regressed, even though every token above is still "defined".
    const light = tokensIn(/:root[^{]*/)
    const dark = tokensIn(/\.dark[^{]*/)

    const identical = THEME_TOKENS.filter((t) => light[t] === dark[t])
    expect(identical).toEqual([])
  })

  it.each([
    ['bg-background', '--background'],
    ['bg-primary', '--primary'],
    ['bg-destructive', '--destructive'],
    ['text-foreground', '--foreground'],
    ['text-destructive-foreground', '--destructive-foreground'],
  ])('utility .%s resolves to var(%s)', (utility, token) => {
    // Selectors are emitted grouped with their opacity variants, e.g.
    // `.bg-primary,.bg-primary\/5{...}`, so match the declaration block that
    // carries this selector rather than assuming it stands alone.
    const rule = new RegExp(`\\.${utility}[^{]*\\{[^}]*var\\(${token}\\)`)
    expect(css).toMatch(rule)
  })

  it('loads the typography plugin that the prose classes depend on', () => {
    // `prose` is used in OnboardingStep, AIInsightsPanel and app/onboarding.
    // The plugin is a devDependency, but v4 only applies it via @plugin.
    expect(css).toMatch(/\.prose\s*[,{]/)
  })

  it('applies the global border colour that @apply border-border provides', () => {
    expect(css).toMatch(/\*[^{]*\{[^}]*border-color:\s*var\(--border\)/)
  })
})
