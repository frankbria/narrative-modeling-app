/**
 * @jest-environment node
 *
 * A counted visit is a fetch to Plausible that `sendPageview` swallows when it is refused,
 * so a Content-Security-Policy whose `connect-src` leaves out https://plausible.io would stop
 * the counts without any error (#1227). No policy exists today; this fails the day one is added
 * without it, wherever the pages' headers can be set: Next's `headers()`, the middleware, any
 * other frontend source, or the nginx edge.
 */
import { readFileSync } from 'fs'
import { join } from 'path'
import { globSync } from 'glob'
import { PLAUSIBLE_EVENT_URL } from '@/lib/analytics/plausible'

const FRONTEND = join(__dirname, '..', '..', '..')
const REPOSITORY = join(FRONTEND, '..', '..')
const PLAUSIBLE_ORIGIN = new URL(PLAUSIBLE_EVENT_URL).origin

const frontendFiles = globSync('{app,lib,components,hooks}/**/*.{ts,tsx,js,jsx,mjs}', {
  cwd: FRONTEND,
  ignore: ['**/__tests__/**', '**/node_modules/**', '**/*.test.*'],
})
  .concat(globSync('{instrumentation*,middleware,auth}.ts', { cwd: FRONTEND }), ['next.config.mjs'])
  .map((file) => join(FRONTEND, file))
const edgeFiles = globSync('nginx*.conf', { cwd: REPOSITORY }).map((file) => join(REPOSITORY, file))
const sources = [...frontendFiles, ...edgeFiles].map((file) => ({ file, text: readFileSync(file, 'utf8') }))

/**
 * Each `connect-src` directive's sources, up to the end of the directive or of the string holding it.
 * A single quote cannot end it (keywords are written `'self'`), so one closing a JS string is
 * trimmed off the last source. A list split across array items reads as empty and is refused.
 */
const connectSources = (text: string) =>
  [...text.matchAll(/connect-src([^;"`\n]*)/gi)].map((match) => match[1].trim().split(/\s+/).map((source) => source.replace(/['),]+$/, '')))

const namesPolicy = (text: string) => /content-security-policy/i.test(text)

/** What the guard reports for a set of sources: the problems, empty when the counts can reach Plausible. */
function policyProblems(texts: string[]): string[] {
  const directives = texts.flatMap(connectSources)
  const blocking = directives.filter((list) => !list.includes(PLAUSIBLE_ORIGIN)).map((list) => `connect-src ${list.join(' ')}`)
  const withoutConnectSource = texts.some(namesPolicy) && directives.length === 0 ? ['a policy without connect-src'] : []
  return [...blocking, ...withoutConnectSource]
}

describe('a Content-Security-Policy lets the visit counts reach Plausible', () => {
  it('reads the frontend sources, its config and middleware, and the nginx edge', () => {
    expect(frontendFiles.length).toBeGreaterThan(50)
    expect(frontendFiles).toEqual(
      expect.arrayContaining([join(FRONTEND, 'next.config.mjs'), join(FRONTEND, 'middleware.ts')]),
    )
    expect(edgeFiles).toContain(join(REPOSITORY, 'nginx-staging.conf'))
  })

  it('every connect-src lists Plausible, and no policy is set without a connect-src', () => {
    expect(policyProblems(sources.map((source) => source.text))).toEqual([])
  })

  describe('the check itself', () => {
    it.each([
      ['an edge header', `add_header Content-Security-Policy "default-src 'self'; connect-src 'self' https://o1.ingest.sentry.io" always;`],
      ['a Next header', `{ key: 'Content-Security-Policy', value: "default-src 'self'; connect-src 'self'" }`],
      ['a directive kept apart from the header', "const policy = `connect-src 'self'`"],
    ])('refuses %s whose connect-src leaves Plausible out', (_where, text) => {
      expect(policyProblems([text])).toHaveLength(1)
    })

    it('refuses a policy that governs connections through default-src alone', () => {
      expect(policyProblems([`add_header content-security-policy "default-src 'self'" always;`])).toEqual([
        'a policy without connect-src',
      ])
    })

    it('accepts a policy whose connect-src lists Plausible, wherever the header is named', () => {
      expect(
        policyProblems(["headers.set('Content-Security-Policy', policy)", "const policy = `default-src 'self'; connect-src 'self' https://plausible.io`"]),
      ).toEqual([])
    })

    it('accepts Plausible at the end of a single-quoted string', () => {
      expect(policyProblems(["const policy = 'connect-src https://plausible.io'"])).toEqual([])
    })

    it('accepts sources that set no policy', () => {
      expect(policyProblems(['export const nothing = 1'])).toEqual([])
    })
  })
})
