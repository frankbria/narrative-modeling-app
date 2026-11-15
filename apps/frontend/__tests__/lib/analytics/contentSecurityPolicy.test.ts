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
  .concat(globSync('{instrumentation*,middleware,proxy,auth}.ts', { cwd: FRONTEND }), ['next.config.mjs'])
  .map((file) => join(FRONTEND, file))
const edgeFiles = globSync('nginx*.conf', { cwd: REPOSITORY }).map((file) => join(REPOSITORY, file))
const sources = [...frontendFiles, ...edgeFiles].map((file) => ({ file, text: readFileSync(file, 'utf8') }))

interface Source {
  file: string
  text: string
}

/**
 * Each `connect-src` directive's sources, up to the end of the directive (`;`), of the policy (`,`
 * starts another one) or of the string holding it. A single quote cannot end it (keywords are
 * written `'self'`), so one closing a JS string is trimmed off the last source when comparing. A
 * list split across array items reads as empty and is refused; so are `x-connect-src` and
 * `connect-src-extra`, which browsers ignore.
 */
const connectSources = (text: string) =>
  [...text.matchAll(/(?<![\w-])connect-src(?![\w-])([^;,"`\n]*)/gi)].map((match) => match[1].trim().split(/\s+/))

/**
 * The source without its comments (`#` in an nginx file, block and `//` in code), so a note neither
 * stands in for a directive nor counts as a header. A marker counts only at a line start or after a
 * space: one inside a source (a block comment glued to the Plausible origin) stays and keeps that
 * source refused. Both code markers are read in one pass, left to right, so a `/*` inside a line
 * comment, or a `//` inside a block comment, cannot pair with a later comment and hide a header.
 * shortcut: a ` //` or ` /*` inside a string is read as a comment; parse with TypeScript if a real
 * header ever sits after one on the same line.
 */
const withoutComments = ({ file, text }: Source) =>
  file.endsWith('.conf')
    ? text.replace(/(^|\s)#.*$/gm, '$1')
    : text.replace(/(^|\s)(?:\/\*[\s\S]*?\*\/|\/\/.*$)/gm, '$1')

/** A comma before a directive name: one header value can carry several policies, each enforced. */
const NEXT_POLICY =
  /,(?=\s*(?:[a-z-]+-src|base-uri|form-action|frame-ancestors|navigate-to|sandbox|upgrade-insecure-requests|block-all-mixed-content|report-uri|report-to|require-trusted-types-for|trusted-types|webrtc)\b)/i

/** Where a policy header starts; the report-only one never blocks a request, so its value is left out. */
const AT_A_HEADER = /(?=content-security-policy)/i
const REPORT_ONLY = /^content-security-policy-report-only/i
const HEADER_NAME = /^content-security-policy/i

/**
 * What the guard reports, each problem prefixed with its file: empty when the counts can reach
 * Plausible. A browser enforces every policy it receives (Next's, the edge's, a `location` block's,
 * each one of a comma-separated value), so the text after each header name, up to the next one, and
 * each policy after a comma in it need a `connect-src` of their own, and every one must list Plausible.
 * shortcut: a header whose value is written before it or in another file (`headers.set(name, policy)`)
 * is refused; pair them by variable when such a file exists.
 */
function policyProblems(sources: Source[]): string[] {
  return sources.flatMap((source) => {
    const parts = withoutComments(source).split(AT_A_HEADER)
    const headers = parts.filter((part) => HEADER_NAME.test(part) && !REPORT_ONLY.test(part))
    const policies = headers.flatMap((header) => header.split(NEXT_POLICY))
    const beforeAnyPolicy = parts.filter((part) => !HEADER_NAME.test(part))
    const blocking = [...beforeAnyPolicy, ...policies]
      .flatMap(connectSources)
      .filter((list) => !list.some((entry) => entry.replace(/'$/, '') === PLAUSIBLE_ORIGIN))
      .map((list) => `connect-src ${list.join(' ')}`)
    const withoutConnectSource = policies.filter((policy) => connectSources(policy).length === 0).map(() => 'a policy without connect-src')
    return [...blocking, ...withoutConnectSource].map((problem) => `${source.file}: ${problem}`)
  })
}

const edge = (text: string): Source => ({ file: 'nginx-staging.conf', text })
const code = (text: string): Source => ({ file: 'middleware.ts', text })

describe('a Content-Security-Policy lets the visit counts reach Plausible', () => {
  it('reads the frontend sources, its config and middleware, and the nginx edge', () => {
    expect(frontendFiles.length).toBeGreaterThan(50)
    expect(frontendFiles).toEqual(
      expect.arrayContaining([join(FRONTEND, 'next.config.mjs'), join(FRONTEND, 'middleware.ts')]),
    )
    expect(edgeFiles).toContain(join(REPOSITORY, 'nginx-staging.conf'))
  })

  it('every connect-src lists Plausible, and no policy is set without a connect-src', () => {
    expect(policyProblems(sources)).toEqual([])
  })

  describe('the check itself', () => {
    it.each([
      ['an edge header', edge(`add_header Content-Security-Policy "default-src 'self'; connect-src 'self' https://o1.ingest.sentry.io" always;`)],
      ['a Next header', code(`{ key: 'Content-Security-Policy', value: "default-src 'self'; connect-src 'self'" }`)],
      ['a directive kept apart from the header', code("const policy = `connect-src 'self'`")],
    ])('refuses %s whose connect-src leaves Plausible out, naming the file', (_where, source) => {
      expect(policyProblems([source])).toEqual([expect.stringMatching(new RegExp(`^${source.file}: connect-src 'self'`))])
    })

    it('refuses a policy that governs connections through default-src alone', () => {
      expect(policyProblems([edge(`add_header content-security-policy "default-src 'self'" always;`)])).toEqual([
        'nginx-staging.conf: a policy without connect-src',
      ])
    })

    it('accepts a policy whose connect-src lists Plausible', () => {
      expect(
        policyProblems([edge(`add_header Content-Security-Policy "default-src 'self'; connect-src 'self' https://plausible.io" always;`)]),
      ).toEqual([])
    })

    it('refuses a second policy without connect-src even when the first one lists Plausible', () => {
      const nextHeader = code(`{ key: 'Content-Security-Policy', value: "default-src 'self'; connect-src 'self' https://plausible.io" }`)
      const edgeHeader = edge(`add_header Content-Security-Policy "default-src 'self'" always;`)
      expect(policyProblems([nextHeader, edgeHeader])).toEqual(['nginx-staging.conf: a policy without connect-src'])
    })

    it.each([
      ['a JS comment line', code("// connect-src https://plausible.io\nheaders.set('Content-Security-Policy', \"default-src 'self'\")")],
      ['an inline JS comment', code("headers.set('Content-Security-Policy', \"default-src 'self'\") // connect-src https://plausible.io")],
      ['a block comment', code("/* connect-src https://plausible.io */ headers.set('Content-Security-Policy', \"default-src 'self'\")")],
      ['an nginx comment', edge(`add_header Content-Security-Policy "default-src 'self'" always; # connect-src https://plausible.io`)],
    ])('does not let %s stand in for the directive', (_where, source) => {
      expect(policyProblems([source])).toEqual([`${source.file}: a policy without connect-src`])
    })

    it.each([
      ['a JS comment', code('// Content-Security-Policy is set at the edge, not here\nexport const nothing = 1')],
      ['an nginx comment', edge(`# Content-Security-Policy: see #1227\nadd_header Content-Security-Policy "connect-src https://plausible.io" always;`)],
      ['a report-only header, which never blocks', edge(`add_header Content-Security-Policy-Report-Only "default-src 'self'" always;`)],
    ])('does not take %s for an enforced policy', (_where, source) => {
      expect(policyProblems([source])).toEqual([])
    })

    it('does not let a report-only header supply the enforced policy before it with Plausible', () => {
      const edgeHeaders = edge(`add_header Content-Security-Policy "default-src 'self'" always;
add_header Content-Security-Policy-Report-Only "connect-src https://plausible.io" always;`)
      expect(policyProblems([edgeHeaders])).toEqual(['nginx-staging.conf: a policy without connect-src'])
    })

    it.each([
      ['a /* inside a line comment', "// per the wiki, /* marks the header section\nres.headers.set('Content-Security-Policy', \"default-src 'self'\")\n/* footer */"],
      ['a // inside a block comment', "/* see the wiki // header section */\nres.headers.set('Content-Security-Policy', \"default-src 'self'\")\n/* footer */"],
    ])('does not let %s pair with a later comment and hide a header', (_where, text) => {
      expect(policyProblems([code(text)])).toEqual(['middleware.ts: a policy without connect-src'])
    })

    it('reads a # in code as code, so a header after it still counts', () => {
      expect(policyProblems([code(`const brand = { colour: '#0D5C63', header: 'Content-Security-Policy', value: "default-src 'self'" }`)])).toEqual([
        'middleware.ts: a policy without connect-src',
      ])
    })

    it('accepts Plausible at the end of a single-quoted string', () => {
      expect(policyProblems([code("const policy = 'connect-src https://plausible.io'")])).toEqual([])
    })

    it.each([
      ['a second policy after a comma', `add_header Content-Security-Policy "connect-src https://plausible.io, default-src 'self'" always;`, ['a policy without connect-src']],
      ['a second policy that starts with frame-ancestors', `add_header Content-Security-Policy "connect-src https://plausible.io, frame-ancestors 'none'; default-src 'self'" always;`, ['a policy without connect-src']],
      [
        'a second policy in a location block',
        `add_header Content-Security-Policy "default-src 'self'; connect-src 'self' https://plausible.io" always;
location = /pricing { add_header Content-Security-Policy "default-src 'self'" always; }`,
        ['a policy without connect-src'],
      ],
      [
        'a policy whose doubled directive would cover the next one',
        `add_header Content-Security-Policy "connect-src https://plausible.io; connect-src https://plausible.io" always;
location = /pricing { add_header Content-Security-Policy "default-src 'self'" always; }`,
        ['a policy without connect-src'],
      ],
      ['a comment marker inside a source', `add_header Content-Security-Policy "connect-src https://plausible.io/*blocked*/" always;`, ['connect-src https://plausible.io/*blocked*/']],
      ['a directive browsers do not know', `add_header Content-Security-Policy "default-src 'self'; x-connect-src https://plausible.io" always;`, ['a policy without connect-src']],
      ['a directive name with a suffix', `add_header Content-Security-Policy "default-src 'self'; connect-src-extra https://plausible.io" always;`, ['a policy without connect-src']],
    ])('refuses %s', (_where, text, problems) => {
      expect(policyProblems([edge(text)])).toEqual(problems.map((problem) => `nginx-staging.conf: ${problem}`))
    })

    it('refuses a header whose policy is written before it', () => {
      expect(policyProblems([code("const policy = `connect-src https://plausible.io`\nheaders.set('Content-Security-Policy', policy)")])).toEqual([
        'middleware.ts: a policy without connect-src',
      ])
    })

    it('accepts sources that set no policy', () => {
      expect(policyProblems([code('export const nothing = 1')])).toEqual([])
    })
  })
})
