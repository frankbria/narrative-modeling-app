/**
 * @jest-environment node
 *
 * Nothing in the frontend may hand the backend anything but the minted API JWT (#527).
 *
 * Three shapes have shipped: `session.accessToken` (the OAuth provider's credential
 * for Google/GitHub, forwarded to our own API), `Bearer nextauth-<id>` (a placeholder
 * the backend rejects, so the route it lived in never worked), and `|| 'default'`
 * (a literal sent as a bearer when the real one was missing). Each is a grep away
 * from coming back in a new component, so this test is the sweep, kept running.
 */
import { readFileSync } from 'fs'
import { join } from 'path'
import { globSync } from 'glob'

const ROOT = join(__dirname, '..', '..')

const BANNED: [RegExp, string][] = [
  [/session\??\.accessToken\b/, 'session.apiToken — the provider token is not exposed on the session'],
  [/\.accessToken\b\s*\|\|/, 'session.apiToken (no fallback)'],
  [/Bearer nextauth-/, 'Bearer ${session.apiToken}'],
  [/\|\|\s*['"]default['"]\s*}?`/, 'return 401 when there is no token'],
  [/Bearer\s+default\b/, 'return 401 when there is no token'],
]

const files = globSync('{app,lib,components,hooks}/**/*.{ts,tsx}', {
  cwd: ROOT,
  ignore: ['**/__tests__/**', '**/node_modules/**', '**/*.test.*'],
})

describe('no provider token or placeholder reaches the backend', () => {
  it('scans a non-trivial number of source files', () => {
    expect(files.length).toBeGreaterThan(50)
  })

  it.each(BANNED)('no source file matches %s', (pattern, replacement) => {
    const offenders = files.filter((f) => pattern.test(readFileSync(join(ROOT, f), 'utf8')))
    expect(offenders).toEqual([])
    void replacement
  })
})
