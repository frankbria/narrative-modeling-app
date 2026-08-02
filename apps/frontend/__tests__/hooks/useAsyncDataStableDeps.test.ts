/**
 * @jest-environment node
 *
 * No `useAsyncData` call site may key on a value with unstable identity (#402).
 *
 * `useAsyncData` compares deps with `Object.is`, so a dep that is a fresh object
 * every render makes the effect re-run on every render: fetch -> setResolved ->
 * re-render -> fetch. The request succeeds every time, so there is no error and no
 * failing test — just a spinner that never clears and a backend being hammered.
 *
 * Measured on `main` before this file existed, over 12 seconds each:
 *
 *     /monitor      740 requests   (two endpoints, alternating)
 *     /model/[id]   378 requests
 *
 * both 100% HTTP 200, both showing "Loading…" the entire time. The cause was
 * `[session]` from `useSession()`, whose `data` is a new object on every render —
 * verified directly: three renders, three distinct identities.
 *
 * This is a source-level scan rather than a runtime test because the defect lives
 * in what a *call site* passes, and there are ~29 of them; a per-page render test
 * would cover whichever pages someone remembered to write, which is exactly how
 * this shipped. Depend on a primitive derived from the object instead —
 * `session?.user?.id` rather than `session`.
 */
import { readFileSync } from 'fs'
import { join } from 'path'

import { globSync } from 'glob'

const ROOT = join(__dirname, '..', '..')

/**
 * Identifiers proven to be a fresh object on every render.
 *
 * Only `session` is listed, and only because there is hard evidence for it: three
 * renders produce three distinct identities, and the two pages that keyed on it
 * issued 740 and 378 requests in 12 seconds until it was removed.
 *
 * `router` is deliberately NOT here. `next/navigation`'s `useRouter()` is memoized,
 * and the same pages that depend on it dropped to 2 requests once `session` alone
 * was fixed — so flagging it would be a false positive dressed up as caution. Add
 * an identifier here when it has been measured, not when it looks suspicious.
 */
const UNSTABLE = ['session']

/** `useAsyncData(loader, [deps], opts)` — capture the dep array text. */
const DEPS = /useAsyncData[\s\S]{0,1600}?\n\s*\[([^\]]*)\]\s*,/g

/** `useEffect(fn, [deps])` — same defect, different hook. `/review` hit this one. */
const EFFECT_DEPS = /\n\s*\}, \[([^\]]*)\]\);/g

function callSites() {
  const files = globSync('{app,components,lib}/**/*.{ts,tsx}', {
    cwd: ROOT,
    ignore: ['**/node_modules/**'],
  })

  const sites: { file: string; deps: string[] }[] = []
  for (const file of files) {
    const src = readFileSync(join(ROOT, file), 'utf8')
    if (!src.includes('useAsyncData(') && !src.includes('useEffect(')) continue
    for (const re of [DEPS, EFFECT_DEPS]) {
      for (const m of src.matchAll(re)) {
        const deps = m[1]
          .split(',')
          .map((d) => d.trim())
          .filter(Boolean)
        sites.push({ file, deps })
      }
    }
  }
  return sites
}

describe('hook dependency stability (#402)', () => {
  const sites = callSites()

  it('finds the call sites', () => {
    // Guards the regex itself: if it silently stops matching, the suite would
    // pass by checking nothing.
    expect(sites.length).toBeGreaterThan(20)
  })

  it('no call site depends on a value with unstable identity', () => {
    const offenders = sites.flatMap(({ file, deps }) =>
      deps
        .filter((d) => UNSTABLE.includes(d))
        .map((d) => `${file}: [${deps.join(', ')}] — '${d}' is a new object every render`)
    )

    expect(offenders).toEqual([])
  })

  it('no call site depends on an object or array literal', () => {
    // `[{...}]` / `[[...]]` inline in the dep list is the same defect, spelled
    // differently.
    const offenders = sites
      .filter(({ deps }) => deps.some((d) => d.startsWith('{') || d.startsWith('[')))
      .map(({ file, deps }) => `${file}: [${deps.join(', ')}]`)

    expect(offenders).toEqual([])
  })
})
