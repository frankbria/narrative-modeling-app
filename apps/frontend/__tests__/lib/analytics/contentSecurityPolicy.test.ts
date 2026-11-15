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

const frontendFiles = globSync('**/*.{ts,tsx,js,jsx,mjs,cjs}', {
  cwd: FRONTEND,
  ignore: ['{e2e,coverage}/**', '**/{__tests__,__mocks__,node_modules}/**', '**/*.test.*'],
}).map((file) => join(FRONTEND, file))
const edgeFiles = globSync('**/*.conf', { cwd: REPOSITORY, ignore: ['**/{node_modules,coverage}/**'] }).map((file) => join(REPOSITORY, file))
const sources = [...frontendFiles, ...edgeFiles].map((file) => ({ file, text: readFileSync(file, 'utf8') }))

interface Source {
  file: string
  text: string
}

/** CSP separates names and sources with ASCII whitespace only; a no-break space is part of a token. */
const ASCII_SPACE = String.raw`[\t\n\f\r ]`

/** What may follow a directive name: anything else (`connect-src!`, `connect-src'self'`, `connect-src-extra`) makes another name, which browsers ignore. */
const NAME_END = String.raw`(?=${ASCII_SPACE}|[;,]|$)`

/**
 * Each `connect-src` directive's sources in a policy text (an nginx value or a code string's
 * contents), up to the end of the directive (`;`), of the policy (`,` starts another one) or of the
 * text. Every character but ASCII whitespace belongs to a source, so a stray quote or a no-break
 * space makes that source invalid and refused. A list split across strings reads as empty and is
 * refused; so is `x-connect-src`.
 */
const connectSources = (text: string) =>
  [...text.matchAll(new RegExp(String.raw`(?<![\w-])connect-src${NAME_END}([^;,]*)`, 'gi'))].map(([, list]) =>
    list.split(new RegExp(`${ASCII_SPACE}+`)).filter((entry) => entry !== ''),
  )

/** A quoted string, in code or an nginx file: single- and double-quoted ones end at their line, a template may span lines. */
const STRING_LITERAL = /"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\[\s\S]|[^`\\])*`/g

/** A comment: `#` in an nginx file, block and `//` in code. */
const NGINX_COMMENT = String.raw`#.*$`
const CODE_COMMENT = String.raw`(?:\/\*[\s\S]*?\*\/|\/\/.*$)`

/**
 * The source without its comments, so a note neither stands in for a directive nor counts as a
 * header. A marker counts only at a line start or after a space: one inside a source (a block
 * comment glued to the Plausible origin) stays and keeps that source refused. The text is read left
 * to right in one pass that steps over quoted strings, so a marker in a string is not a comment, and
 * a `/*` inside a line comment, or a `//` inside a block comment, cannot pair with a later comment
 * and hide a header. shortcut: a quote in a regular expression literal or in JSX text, or a backtick
 * in an nginx file (nginx has no templates), can start a string here; parse properly if one ever
 * hides a header.
 */
const withoutComments = ({ file, text }: Source) =>
  text.replace(
    new RegExp(String.raw`(${STRING_LITERAL.source})|(^|\s)${file.endsWith('.conf') ? NGINX_COMMENT : CODE_COMMENT}`, 'gm'),
    (_match, literal: string | undefined, before: string | undefined) => literal ?? before ?? '',
  )

/**
 * One header value can carry several policies, each enforced: a browser splits them at every comma
 * (a source cannot hold one unencoded) and skips a blank one after a comma. The first is always
 * kept, so a header whose value could not be read stays refused.
 */
const policiesIn = (value: string) => value.split(',').filter((policy, index) => index === 0 || policy.trim() !== '')

/** Where a policy header starts; the report-only one never blocks a request, so its value is left out. */
const AT_A_HEADER = /(?<![\w-])(?=content-security-policy)/i
const REPORT_ONLY = /^content-security-policy-report-only/i
/**
 * A header name, not a mention. In code its own closing quote or a separator and a value follow it,
 * which prose such as `the Content-Security-Policy is…` has not; in nginx, where prose sits only in
 * the comments already removed, any whole name counts (an unquoted value is valid there).
 */
const HEADER_NAME_IN_NGINX = /^content-security-policy(?![\w-])/i
const HEADER_NAME_IN_CODE = /^content-security-policy(?![\w-])(?=['"`]|\s*['"`:]|$)/i
/** The header name with the quote that closes its own string in code. */
const NAME_AND_ITS_QUOTE = /^content-security-policy(?:-report-only)?['"`]?/i

/** The quoted strings of a part, after its header name: the texts a browser could receive as a policy. */
const stringsOf = (part: string) => [...part.replace(NAME_AND_ITS_QUOTE, '').matchAll(STRING_LITERAL)].map(([literal]) => literal)

/** A comma after the value may only be the trailing one: anything after it in the object (a spread, a later key in any spelling) could replace the value. */
const TRAILING_COMMA = String.raw`\s*[)}]`

/**
 * A header's value: the string right after its name, with only a separator between them (`, `,
 * `: `, `, value: ` or a space), so `headers.set(name, policy)`, `base + "…"` or a fallback before
 * the string has none; and only when the string ends the expression: a `+` or `.concat(…)` after it,
 * or anything after it in the same object or call (a spread or a later key could replace it; write
 * the value last), means the emitted value is not this string, so none is read and the header is
 * refused. So is a value holding a `\` (a JS escape such as `\u002c` emits a comma) or a `$` (a
 * `${…}` substitution, an nginx variable), whose emitted value is not its text. shortcut: a header name written with an
 * escape (`Content-\x53ecurity-Policy`) is not found; decode strings if one is ever written so.
 * shortcut: valid policies are refused too (fails closed): an nginx nonce (`'nonce-$request_id'`),
 * the origin with a trailing slash, a `<meta httpEquiv>` policy; allow each when one is wanted.
 */
const HEADER_VALUE = new RegExp(String.raw`^\s*(?:[,:]\s*(?:value\s*:\s*)?)?(${STRING_LITERAL.source})(?=\s*(?:,${TRAILING_COMMA}|[;)}\]]|always\b|$))`)
const headerValue = (header: string) => {
  const literal = HEADER_VALUE.exec(header.replace(NAME_AND_ITS_QUOTE, ''))?.[1]
  return literal === undefined || /[\\$]/.test(literal.slice(1, -1)) ? '' : literal.slice(1, -1)
}

/** A `connect-src` that starts a directive: at the start of a policy or after a `;`, never inside another's source list. */
const DIRECTIVE_START = new RegExp(String.raw`(?:^|;)${ASCII_SPACE}*connect-src${NAME_END}`, 'i')

/**
 * shortcut: this reads source text because no policy exists yet to emit (#1237). It reads strings,
 * not program flow: a value replaced after it is written (`headers[0].value = …`, a function, an
 * import) or an nginx `include` of a file outside the repository is not seen. When the first policy
 * lands, check the emitted values instead (Next's `headers()` result, the middleware response, the
 * expanded nginx configuration), which is simpler and stricter than these patterns.
 *
 * What the guard reports, each problem prefixed with its file: empty when the counts can reach
 * Plausible. A browser enforces every policy it receives (Next's, the edge's, a `location` block's,
 * each one of a comma-separated value), so each header's value, and each policy after a comma in
 * it, needs a `connect-src` of its own; and every `connect-src` outside a report-only header must
 * list Plausible. shortcut: a header whose value is not a quoted string right after its name
 * (`headers.set(name, policy)`, a value from another file) is refused; resolve the variable when
 * such a file exists.
 */
function policyProblems(sources: Source[]): string[] {
  return sources.flatMap((source) => {
    const headerName = source.file.endsWith('.conf') ? HEADER_NAME_IN_NGINX : HEADER_NAME_IN_CODE
    const parts = withoutComments(source).split(AT_A_HEADER).filter((part) => !REPORT_ONLY.test(part))
    const blocking = parts
      .flatMap(stringsOf)
      .flatMap((literal) => connectSources(literal.slice(1, -1)))
      .filter((list) => !list.some((entry) => entry.toLowerCase() === PLAUSIBLE_ORIGIN))
      .map((list) => `connect-src ${list.join(' ')}`)
    const policies = parts.filter((part) => headerName.test(part)).flatMap((header) => policiesIn(headerValue(header)))
    const withoutConnectSource = policies.filter((policy) => !DIRECTIVE_START.test(policy)).map(() => 'a policy without connect-src')
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

  it('reads every frontend source outside the tests, wherever it sits (a new root file or folder too)', () => {
    expect(frontendFiles).toEqual(
      expect.arrayContaining(
        ['playwright.config.ts', 'scripts/check-auth-adapter.mjs', 'types/next-auth.d.ts'].map((file) => join(FRONTEND, file)),
      ),
    )
    expect(frontendFiles.filter((file) => /[/\\](__tests__|__mocks__|e2e|node_modules|\.next|coverage)[/\\]|\.test\./.test(file))).toEqual([])
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

    it.each([
      ['an upper-case origin', `add_header Content-Security-Policy "connect-src HTTPS://PLAUSIBLE.IO" always;`],
      ['a mixed-case origin', `add_header Content-Security-Policy "connect-src 'self' https://Plausible.io" always;`],
    ])('accepts %s, as browsers match scheme and host in any case', (_where, text) => {
      expect(policyProblems([edge(text)])).toEqual([])
    })

    it('accepts a blank policy after a trailing comma, which browsers skip', () => {
      expect(policyProblems([edge(`add_header Content-Security-Policy "connect-src https://plausible.io, " always;`)])).toEqual([])
    })

    it('accepts Plausible at the end of a single-quoted string', () => {
      expect(policyProblems([code("const policy = 'connect-src https://plausible.io'")])).toEqual([])
    })

    it.each([
      ['a second policy after a comma', `add_header Content-Security-Policy "connect-src https://plausible.io, default-src 'self'" always;`, ['a policy without connect-src']],
      ['a second policy that starts with frame-ancestors', `add_header Content-Security-Policy "connect-src https://plausible.io, frame-ancestors 'none'; default-src 'self'" always;`, ['a policy without connect-src']],
      ['a second policy that starts with a directive the guard does not name', `add_header Content-Security-Policy "connect-src https://plausible.io, require-sri-for script; default-src 'self'" always;`, ['a policy without connect-src']],
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
      ['a connect-src left inside another directive by a missing semicolon', `add_header Content-Security-Policy "default-src 'self'; script-src 'self' connect-src https://plausible.io" always;`, ['a policy without connect-src']],
      ['a directive name with a suffix', `add_header Content-Security-Policy "default-src 'self'; connect-src-extra https://plausible.io" always;`, ['a policy without connect-src']],
      ['a directive name followed by punctuation', `add_header Content-Security-Policy "default-src 'none'; connect-src! https://plausible.io" always;`, ['a policy without connect-src']],
      ['a stray quote after the origin in an nginx value', `add_header Content-Security-Policy "connect-src https://plausible.io'" always;`, ["connect-src https://plausible.io'"]],
    ])('refuses %s', (_where, text, problems) => {
      expect(policyProblems([edge(text)])).toEqual(problems.map((problem) => `nginx-staging.conf: ${problem}`))
    })

    it('reads only the header value, not a later string that holds a connect-src', () => {
      const edgeHeaders = edge(`add_header Content-Security-Policy "default-src 'self'" always;
add_header X-Policy-Example "connect-src https://plausible.io" always;`)
      expect(policyProblems([edgeHeaders])).toEqual(['nginx-staging.conf: a policy without connect-src'])
    })

    it('does not take a later string for the value of a header set from a variable', () => {
      const middleware = code(`res.headers.set('Content-Security-Policy', policy)
const note = "connect-src https://plausible.io"`)
      expect(policyProblems([middleware])).toEqual(['middleware.ts: a policy without connect-src'])
    })

    it('accepts a value with a trailing comma, last in its object or call', () => {
      expect(policyProblems([code("{\n  key: 'Content-Security-Policy',\n  value: 'connect-src https://plausible.io',\n}")])).toEqual([])
      expect(policyProblems([code("res.headers.set(\n  'Content-Security-Policy',\n  'connect-src https://plausible.io',\n)")])).toEqual([])
    })

    it('reads a Next header value written on the line after its name', () => {
      const nextHeader = code(`{
  key: 'Content-Security-Policy',
  value: "default-src 'self'; connect-src 'self' https://plausible.io",
}`)
      expect(policyProblems([nextHeader])).toEqual([])
    })

    it.each([
      ['a concatenation', "res.headers.set(\n  'Content-Security-Policy',\n  'connect-src https://plausible.io' + '.invalid',\n)"],
      ['a method call', "res.headers.set('Content-Security-Policy', 'connect-src https://plausible.io'.concat('.invalid'))"],
    ])('refuses a header value that %s continues past its first string', (_how, text) => {
      expect(policyProblems([code(text)])).toContain('middleware.ts: a policy without connect-src')
    })

    it('refuses a stray single quote after the origin inside a double-quoted code string', () => {
      expect(policyProblems([code(`const policy = "connect-src https://plausible.io'"`)])).toEqual([`middleware.ts: connect-src https://plausible.io'`])
    })

    it.each([
      ['a quote glued to the directive name', code(`res.headers.set('Content-Security-Policy', "default-src 'none'; connect-src'self' https://plausible.io")`), ['a policy without connect-src']],
      ['a no-break space after the directive name', edge(`add_header Content-Security-Policy "default-src 'none'; connect-src\u00a0https://plausible.io" always;`), ['a policy without connect-src']],
      ['a no-break space between two sources', edge(`add_header Content-Security-Policy "connect-src 'self'\u00a0https://plausible.io" always;`), ["connect-src 'self'\u00a0https://plausible.io"]],
      ['a stray quote and a space after the origin in a double-quoted code string', code(`res.headers.set('Content-Security-Policy', "connect-src https://plausible.io' ")`), ["connect-src https://plausible.io'"]],
      ['a template value with a substitution', code("const extra = \", default-src 'none'\"\nres.headers.set(\n  'Content-Security-Policy',\n  `connect-src https://plausible.io ${extra}`,\n)"), ['a policy without connect-src']],
      ['a header after a comment marker inside a string', code(`const note = " //"; res.headers.set('Content-Security-Policy', "default-src 'none'")`), ['a policy without connect-src']],
      ['an escaped comma that makes a second policy', code(`res.headers.set('Content-Security-Policy', "connect-src https://plausible.io \\u002c default-src 'none'")`), ['a policy without connect-src']],
      ['an nginx header after a # inside a quoted value', edge(`set $note " #"; add_header Content-Security-Policy "default-src 'none'" always;`), ['a policy without connect-src']],
      ['an nginx value with a variable', edge(`add_header Content-Security-Policy "connect-src https://plausible.io $extra" always;`), ['a policy without connect-src']],
      ['a fallback before the value', code(`res.headers.set('Content-Security-Policy', process.env.CSP_POLICY || "connect-src https://plausible.io")`), ['a policy without connect-src']],
      ['a variable added before the value', code(`res.headers.set('Content-Security-Policy', base + "connect-src https://plausible.io")`), ['a policy without connect-src']],
      ['a value joined from an array', code(`{ key: 'Content-Security-Policy', value: [base, "connect-src https://plausible.io"].join(', ') }`), ['a policy without connect-src']],
      ['a header after a link in JSX text', code(`<p>docs at https://example.com</p>; res.headers.set('Content-Security-Policy', "default-src 'none'")`), ['a policy without connect-src']],
      ['a value a later spread replaces', code("headers: [{\n  key: 'Content-Security-Policy',\n  value: 'connect-src https://plausible.io',\n  ...override,\n}]"), ['a policy without connect-src']],
      ['a value a later duplicate key replaces', code("{ key: 'Content-Security-Policy', value: 'connect-src https://plausible.io', value: override.value }"), ['a policy without connect-src']],
      ['a value a later quoted key replaces', code("{ key: 'Content-Security-Policy', value: 'connect-src https://plausible.io', 'value': override.value }"), ['a policy without connect-src']],
      ['a value a later computed key replaces', code(`{ key: 'Content-Security-Policy', value: 'connect-src https://plausible.io', ["value"]: override.value }`), ['a policy without connect-src']],
      ['an unquoted nginx value', edge(`add_header Content-Security-Policy default-src;`), ['a policy without connect-src']],
    ])('refuses %s, which browsers read differently', (_where, source, problems) => {
      expect(policyProblems([source])).toEqual(problems.map((problem) => `${source.file}: ${problem}`))
    })

    it('refuses a header whose policy is written before it', () => {
      expect(policyProblems([code("const policy = `connect-src https://plausible.io`\nheaders.set('Content-Security-Policy', policy)")])).toEqual([
        'middleware.ts: a policy without connect-src',
      ])
    })

    it.each([
      ['JSX text', code('<p>Our Content-Security-Policy is set at the edge.</p>')],
      ['an error message', code("throw new Error('Content-Security-Policy is not set in this app')")],
      ['the plural', code("const note = 'Content-Security-Policies differ per host'")],
      ['the legacy prefixed name, which browsers ignore', edge(`add_header X-Content-Security-Policy "default-src 'self'" always;`)],
    ])('does not take a mention of the header name in %s for a header', (_where, source) => {
      expect(policyProblems([source])).toEqual([])
    })

    it('accepts a connect-src list written across lines in a template', () => {
      const middleware = code("res.headers.set('Content-Security-Policy', `default-src 'self';\n  connect-src 'self'\n    https://plausible.io`)")
      expect(policyProblems([middleware])).toEqual([])
    })

    it('accepts sources that set no policy', () => {
      expect(policyProblems([code('export const nothing = 1')])).toEqual([])
    })
  })
})
