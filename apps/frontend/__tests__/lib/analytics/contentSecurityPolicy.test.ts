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
 * Each `connect-src` directive's sources, up to the end of the directive (`;`), of the policy (`,`
 * starts another one) or of the string holding it. A single quote cannot end it (keywords are
 * written `'self'`), so one closing a JS string is trimmed off the last source. A list split across
 * array items reads as empty and is refused; so is `x-connect-src`, which browsers ignore.
 */
const connectSources = (text: string) =>
  [...text.matchAll(/(?<![\w-])connect-src([^;,"`\n]*)/gi)].map((match) => match[1].trim().split(/\s+/).map((source) => source.replace(/'$/, '')))

/**
 * The text with its comments removed (block, `//`, nginx `#`), so no note can stand in for a
 * directive. A comment marker counts only at a line start or after a space: one inside a source
 * (a block comment glued to the Plausible origin) stays and keeps that source refused.
 */
const withoutComments = (text: string) =>
  text
    .replace(/(^|\s)\/\*[\s\S]*?\*\//g, '$1')
    .replace(/(^|\s)(\/\/|#).*$/gm, '$1')

/** A comma before a directive name: one header value can carry several policies, each enforced. */
const NEXT_POLICY =
  /,(?=\s*(?:[a-z-]+-src|base-uri|form-action|frame-ancestors|navigate-to|sandbox|upgrade-insecure-requests|block-all-mixed-content|report-uri|report-to|require-trusted-types-for|trusted-types|webrtc)\b)/i

/**
 * What the guard reports, one text per file: empty when the counts can reach Plausible. A browser
 * enforces every policy it receives (Next's, the edge's, a `location` block's, each one of a
 * comma-separated value), so the text after each header name, up to the next one, and each policy
 * after a comma in it need a `connect-src` of their own, and every one must list Plausible.
 * shortcut: a header whose value is written before it or in another file (`headers.set(name, policy)`)
 * is refused; pair them by variable when such a file exists.
 */
function policyProblems(texts: string[]): string[] {
  return texts.flatMap((text) => {
    const [beforeAnyPolicy, ...headers] = text.split(/content-security-policy/i).map(withoutComments)
    const policies = headers.flatMap((header) => header.split(NEXT_POLICY))
    const blocking = [beforeAnyPolicy, ...policies]
      .flatMap(connectSources)
      .filter((list) => !list.includes(PLAUSIBLE_ORIGIN))
      .map((list) => `connect-src ${list.join(' ')}`)
    const withoutConnectSource = policies.filter((policy) => connectSources(policy).length === 0).map(() => 'a policy without connect-src')
    return [...blocking, ...withoutConnectSource]
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

    it('refuses a second policy in the same file, as an nginx location block sets it', () => {
      const edge = `add_header Content-Security-Policy "default-src 'self'; connect-src 'self' https://plausible.io" always;
location = /pricing { add_header Content-Security-Policy "default-src 'self'" always; }`
      expect(policyProblems([edge])).toEqual(['a policy without connect-src'])
    })

    it.each([
      ['a JS comment line', "// connect-src https://plausible.io\nheaders.set('Content-Security-Policy', \"default-src 'self'\")"],
      ['an inline JS comment', "headers.set('Content-Security-Policy', \"default-src 'self'\") // connect-src https://plausible.io"],
      ['a block comment', "/* connect-src https://plausible.io */ headers.set('Content-Security-Policy', \"default-src 'self'\")"],
      ['an nginx comment', `add_header Content-Security-Policy "default-src 'self'" always; # connect-src https://plausible.io`],
    ])('does not let %s stand in for the directive', (_where, text) => {
      expect(policyProblems([text])).toEqual(['a policy without connect-src'])
    })

    it('accepts Plausible at the end of a single-quoted string', () => {
      expect(policyProblems(["const policy = 'connect-src https://plausible.io'"])).toEqual([])
    })

    it.each([
      ['a second policy after a comma', `add_header Content-Security-Policy "connect-src https://plausible.io, default-src 'self'" always;`, ['a policy without connect-src']],
      ['a second policy that starts with frame-ancestors', `add_header Content-Security-Policy "connect-src https://plausible.io, frame-ancestors 'none'; default-src 'self'" always;`, ['a policy without connect-src']],
      [
        'a policy whose doubled directive would cover the next one',
        `add_header Content-Security-Policy "connect-src https://plausible.io; connect-src https://plausible.io" always;
location = /pricing { add_header Content-Security-Policy "default-src 'self'" always; }`,
        ['a policy without connect-src'],
      ],
      ['a comment marker inside a source', `add_header Content-Security-Policy "connect-src https://plausible.io/*blocked*/" always;`, ['connect-src https://plausible.io/*blocked*/']],
      ['a directive browsers do not know', `add_header Content-Security-Policy "default-src 'self'; x-connect-src https://plausible.io" always;`, ['a policy without connect-src']],
    ])('refuses %s', (_where, text, problems) => {
      expect(policyProblems([text])).toEqual(problems)
    })

    it('refuses a header whose policy is written before it', () => {
      expect(policyProblems(["const policy = `connect-src https://plausible.io`\nheaders.set('Content-Security-Policy', policy)"])).toEqual([
        'a policy without connect-src',
      ])
    })

    it('accepts sources that set no policy', () => {
      expect(policyProblems(['export const nothing = 1'])).toEqual([])
    })
  })
})
