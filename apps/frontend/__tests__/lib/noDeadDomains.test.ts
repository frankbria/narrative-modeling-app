/**
 * @jest-environment node
 *
 * `narrativeml.com` is a test-fixture domain, never the company's (#770). It shipped
 * as the access-denied page's request-access mailbox, so a user asking for an
 * invite wrote to nobody. Contact addresses come from `lib/legal/company.ts`; this
 * sweep keeps the fixture domain out of everything a user can reach.
 */
import { readFileSync } from 'fs'
import { join } from 'path'
import { globSync } from 'glob'

const ROOT = join(__dirname, '..', '..')

// The development/test-only credentials provider and its sign-in form default to
// the e2e user's address. auth.ts registers that provider only outside production.
const FIXTURE_SITES = ['auth.ts', 'app/auth/signin/page.tsx']

const files = globSync('{app,lib,components,hooks}/**/*.{ts,tsx}', {
  cwd: ROOT,
  ignore: ['**/__tests__/**', '**/node_modules/**', '**/*.test.*'],
}).concat(['auth.ts', 'middleware.ts'])

describe('no dead product domain reaches a user', () => {
  it('scans a non-trivial number of source files', () => {
    expect(files.length).toBeGreaterThan(50)
  })

  it('no source file outside the test fixtures names narrativeml.com or narrativemodeling.ai', () => {
    const offenders = files
      .filter((f) => !FIXTURE_SITES.includes(f))
      .filter((f) => /narrativeml\.com|narrativemodeling\.ai/.test(readFileSync(join(ROOT, f), 'utf8')))
    expect(offenders).toEqual([])
  })

  it('the fixture sites use the domain only for the test user', () => {
    for (const f of FIXTURE_SITES) {
      const hits = readFileSync(join(ROOT, f), 'utf8').match(/[\w.+-]*@?narrativeml\.com/g) ?? []
      expect(hits.length).toBeGreaterThan(0)
      expect(new Set(hits)).toEqual(new Set(['test@narrativeml.com']))
    }
  })
})
