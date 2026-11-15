/**
 * @jest-environment node
 *
 * A counted visit is a fetch to Plausible that `sendPageview` swallows when it is refused,
 * so a Content-Security-Policy whose `connect-src` leaves out https://plausible.io would stop
 * the counts without any error (#1227). No policy exists today; this fails the day one is added
 * without it, wherever the pages' headers can be set: Next's `headers()`, the middleware, any
 * other frontend source, or the nginx edge. Each file's policy is checked on its own.
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

/** The text without its comment lines (`//`, `/*`, ` *`, nginx `#`), so a note cannot stand in for a directive. */
const code = (text: string) =>
  text
    .split('\n')
    .filter((line) => !/^\s*(\/\/|\/\*|\*|#)/.test(line))
    .join('\n')

/**
 * What the guard reports, one text per file: empty when the counts can reach Plausible. Every policy
 * is checked on its own, because a browser enforces each one it receives (Next's and the edge's):
 * a file naming the header needs its own `connect-src`. shortcut: a policy whose directives live in
 * another file than its header is refused too; split the check by header when such a file exists.
 */
function policyProblems(texts: string[]): string[] {
  return texts.map(code).flatMap((text) => {
    const directives = connectSources(text)
    const blocking = directives.filter((list) => !list.includes(PLAUSIBLE_ORIGIN)).map((list) => `connect-src ${list.join(' ')}`)
    return namesPolicy(text) && directives.length === 0 ? [...blocking, 'a policy without connect-src'] : blocking
  })
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

    it('accepts a policy whose connect-src lists Plausible', () => {
      expect(
        policyProblems([`add_header Content-Security-Policy "default-src 'self'; connect-src 'self' https://plausible.io" always;`]),
      ).toEqual([])
    })

    it('refuses a second policy without connect-src even when the first one lists Plausible', () => {
      const nextHeader = `{ key: 'Content-Security-Policy', value: "default-src 'self'; connect-src 'self' https://plausible.io" }`
      const edgeHeader = `add_header Content-Security-Policy "default-src 'self'" always;`
      expect(policyProblems([nextHeader, edgeHeader])).toEqual(['a policy without connect-src'])
    })

    it.each([
      ['a JS comment', "// connect-src https://plausible.io\nheaders.set('Content-Security-Policy', \"default-src 'self'\")"],
      ['an nginx comment', `# connect-src https://plausible.io\nadd_header Content-Security-Policy "default-src 'self'" always;`],
    ])('does not let %s stand in for the directive', (_where, text) => {
      expect(policyProblems([text])).toEqual(['a policy without connect-src'])
    })

    it('accepts Plausible at the end of a single-quoted string', () => {
      expect(policyProblems(["const policy = 'connect-src https://plausible.io'"])).toEqual([])
    })

    it('accepts sources that set no policy', () => {
      expect(policyProblems(['export const nothing = 1'])).toEqual([])
    })
  })
})
