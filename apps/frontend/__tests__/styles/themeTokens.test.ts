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

/**
 * Collect custom-property declarations from every rule whose selector list
 * contains `wanted` as a whole selector.
 *
 * Matching the selector exactly matters. A looser `/\.dark[^{]*\{/` also matches
 * compiled variant utilities like `.dark\:bg-blue-950:is(.dark *) {`, which are
 * not the theme block. Nothing breaks today, since those rules declare no bare
 * `--token`, but it would silently read the wrong block the moment one did — and
 * reading the wrong block is how this whole class of bug stays invisible.
 *
 * Declarations are matched only at the top level of the block (`[^{}]*`), so a
 * rule containing a nested at-rule is skipped rather than half-parsed.
 */
function tokensIn(wanted: string): Record<string, string> {
  const found: Record<string, string> = {}
  for (const block of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selectors = block[1].split(',').map((s) => s.trim())
    if (!selectors.includes(wanted)) continue

    for (const decl of block[2].matchAll(/--([a-z-]+):\s*([^;]+)/g)) {
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
    const light = tokensIn(':root')
    const dark = tokensIn('.dark')

    expect(light[token]).toBeDefined()
    expect(dark[token]).toBeDefined()
  })

  it('gives light and dark genuinely different values', () => {
    // Dark mode was entirely non-functional before #345 — the light and dark
    // screenshots came out byte-identical. Identical values would mean that
    // regressed, even though every token above is still "defined".
    const light = tokensIn(':root')
    const dark = tokensIn('.dark')

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

  it('does not load the typography plugin yet', () => {
    // Inverted on purpose. `prose` is used in OnboardingStep, AIInsightsPanel and
    // app/onboarding, and @tailwindcss/typography is a devDependency — but v4 only
    // applies a plugin via @plugin, so those blocks render unstyled. That is a
    // pre-existing bug held back from this PR deliberately (tracked as #398): enabling it restyles
    // real content, which is a visual change needing its own sign-off rather than
    // riding along inside a version migration. This assertion pins the scope, so
    // turning it on is a deliberate edit here and not an accident.
    expect(css).not.toMatch(/\.prose\s*[,{]/)
  })

  it('applies the global border colour that @apply border-border provides', () => {
    expect(css).toMatch(/\*[^{]*\{[^}]*border-color:\s*var\(--border\)/)
  })
})

describe('ported v3 config survives', () => {
  // v3's `theme.container.screens = { "2xl": "1400px" }` REPLACED the container's
  // breakpoint list rather than extending it, so v3 emitted exactly one max-width
  // rule — `@media (min-width: 1400px)`. Verified by compiling the old config with
  // tailwindcss@3. The v4 port is therefore a single unconditional `max-width: 1400px`,
  // which is equivalent: below 1400px neither caps, above it both cap at 1400px.
  /** Our flat override: a .container block with no nested at-rule inside it. */
  const OVERRIDE = /\.container\s*\{[^{}]*max-width:\s*1400px[^{}]*\}/
  /** v4's built-in: a .container block whose max-widths are nested in @media. */
  const BUILTIN = /\.container\s*\{[^{}]*@media/

  it('declares the container box model v3 produced', () => {
    expect(css).toMatch(OVERRIDE)

    const rule = css.match(OVERRIDE)![0]
    expect(rule).toMatch(/width:\s*100%/)      // as a flex/grid item, auto shrink-to-fits
    expect(rule).toMatch(/margin-inline:\s*auto/)
    expect(rule).toMatch(/padding-inline:\s*2rem/)
  })

  it('emits the container override AFTER v4 built-in breakpoint rules', () => {
    // The load-bearing assertion, and the one most likely to break silently.
    // v4 ships its OWN breakpoint-scoped .container max-widths (40/48/64/80/96rem).
    // Ours carries no media query and has identical specificity, so it wins only by
    // arriving later in source order. If a future version reorders the utilities
    // layer, the built-in stepped max-widths take over and the container starts
    // capping at 640/768/1024px — a layout regression at every intermediate width,
    // with nothing failing anywhere. Assert the ordering, not just the presence.
    const builtin = css.search(BUILTIN)
    const override = css.search(OVERRIDE)

    expect(override).toBeGreaterThan(-1)
    expect(builtin).toBeGreaterThan(-1)
    expect(override).toBeGreaterThan(builtin)
  })

  it('generates the accordion animations from the nested @keyframes', () => {
    // Radix drives these via data-state, so the bare `animate-accordion-*` class
    // never appears in source and is correctly absent from the output. Assert the
    // prefixed variants that are actually used, plus the keyframes they reference.
    // Attribute values may or may not be quoted depending on the emitter.
    expect(css).toMatch(
      /animate-accordion-down\[data-state=["']?open["']?\]\s*\{\s*animation:\s*var\(--animate-accordion-down\)/,
    )
    expect(css).toMatch(
      /animate-accordion-up\[data-state=["']?closed["']?\]\s*\{\s*animation:\s*var\(--animate-accordion-up\)/,
    )

    expect(css).toMatch(/@keyframes\s+accordion-down\s*\{/)
    expect(css).toMatch(/@keyframes\s+accordion-up\s*\{/)
    expect(css).toMatch(/--radix-accordion-content-height/)
  })
})
