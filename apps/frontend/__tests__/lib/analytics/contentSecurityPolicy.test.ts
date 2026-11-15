/**
 * @jest-environment node
 *
 * A counted visit is a fetch to Plausible that `sendPageview` swallows when it is refused,
 * so a Content-Security-Policy whose `connect-src` leaves out https://plausible.io would stop
 * the counts without any error (#1227). No policy exists today; this fails the day one is added
 * without it, wherever the pages' headers can be set: Next's `headers()`, the middleware, any
 * other frontend source, or the nginx edge. Each file's policy is checked on its own.
 */
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'fs'
import { tmpdir } from 'os'
import { dirname, join } from 'path'
import { globSync } from 'glob'
import { PLAUSIBLE_EVENT_URL } from '@/lib/analytics/plausible'

const FRONTEND = join(__dirname, '..', '..', '..')
const REPOSITORY = join(FRONTEND, '..', '..')
const PLAUSIBLE_ORIGIN = new URL(PLAUSIBLE_EVENT_URL).origin

/** Dependencies and build or test output, at any depth (glob skips dot folders such as `.next` already; it is named so the list is whole). */
const GENERATED_FOLDERS = ['node_modules', 'coverage', '.next', 'out', 'build', 'dist', 'playwright-report', 'test-results']
const IN_GENERATED_FOLDERS = `**/{${GENERATED_FOLDERS.join(',')}}/**`

const filesUnder = (root: string, pattern: string, ignore: string[]) =>
  globSync(pattern, { cwd: root, ignore: [IN_GENERATED_FOLDERS, ...ignore] }).map((file) => join(root, file))
const frontendSourcesIn = (root: string) =>
  filesUnder(root, '**/*.{ts,tsx,js,jsx,mjs,cjs}', ['e2e/**', '**/{__tests__,__mocks__}/**', '**/*.test.*'])
const edgeConfigsIn = (root: string) => filesUnder(root, '**/*.conf', [])

const frontendFiles = frontendSourcesIn(FRONTEND)
const edgeFiles = edgeConfigsIn(REPOSITORY)
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

/**
 * Where a policy header starts; the report-only one never blocks a request, so its value is left out.
 * A name that ends a path (an MDN link, an `href`) is a mention: its `/` follows a path character,
 * not a quote as in `'/Content-Security-Policy'.slice(1)`, which stays a header.
 */
const AT_A_HEADER = /(?<![\w-])(?<![^'"`]\/)(?=content-security-policy)/i
const REPORT_ONLY = /^content-security-policy-report-only/i
const DIRECTIVE_NAME = String.raw`(?:[a-z]+(?:-[a-z]+)*-src(?:-elem|-attr)?|base-uri|block-all-mixed-content|form-action|frame-ancestors|navigate-to|plugin-types|report-to|report-uri|require-sri-for|require-trusted-types-for|sandbox|trusted-types|upgrade-insecure-requests|webrtc)`
/**
 * After a string and any brackets it closes, what ends its expression: a separator, a JSX tag's end,
 * the text's end, or a line break the next line does not continue (no semicolons here).
 */
const LABEL_END = String.raw`(?=(?:[ \t]*[)\]}])*[ \t]*(?:[,;>]|\/>|$|\n(?!\s*[-+*/%.?:|&^[(\`])))`
/**
 * What makes `Name:` a label in a string opened by `quote`: words up to that same quote, starting with
 * a letter, with no directive name and nothing that builds or escapes a value (`$`, `\`), where the
 * quote also ends the expression (LABEL_END), so neither a `+` nor a later string adds a policy to the
 * words. A policy of only directives browsers do not know (`made-up-directive x`) restricts nothing.
 * shortcut: a directive the spec adds without `-src` reads as a word; add it to DIRECTIVE_NAME.
 * shortcut: label words that program flow later joins to a policy (an array's `join`, a function) are
 * not followed, as no value set after it is written is; the emitted-header check (#1249) ends this.
 */
const labelText = (quote: string) =>
  String.raw`${ASCII_SPACE}*(?=[a-z])(?:(?!(?<![\w-])${DIRECTIVE_NAME}(?![\w-]))[^${quote}$\\\n])+${quote}${LABEL_END}`
/**
 * A header name, not a mention, given the character before it (the quote that opens its string, in
 * code). In code its own closing quote (or the next string) follows it, or a colon (a serialized
 * `Name: policy` line) that a label (`labelText`) does not follow, which prose such as `the
 * Content-Security-Policy is…` or a `Content-Security-Policy: see the wiki` label has not;
 * `'our Content-Security-Policy'` still reads as a name kept in a constant, and is refused. In
 * nginx, where prose sits only in the comments already removed, any whole name counts (an unquoted
 * value is valid there).
 */
const HEADER_NAME_IN_NGINX = /^content-security-policy(?![\w-])/i
const headerNameInCode = (before: string) => {
  const notALabel = /^['"`]$/.test(before) ? `(?!${labelText(before)})` : ''
  return new RegExp(String.raw`^content-security-policy(?![\w-])(?=['"\`]|\s*['"\`]|\s*:${notALabel}|$)`, 'i')
}
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
    const isHeaderName = (part: string, before: string) =>
      (source.file.endsWith('.conf') ? HEADER_NAME_IN_NGINX : headerNameInCode(before)).test(part)
    const allParts = withoutComments(source).split(AT_A_HEADER)
    const enforced = allParts.map((part, index) => ({ part, before: allParts[index - 1]?.slice(-1) ?? '' })).filter(({ part }) => !REPORT_ONLY.test(part))
    const parts = enforced.map(({ part }) => part)
    const blocking = parts
      .flatMap(stringsOf)
      .flatMap((literal) => connectSources(literal.slice(1, -1)))
      .filter((list) => !list.some((entry) => entry.toLowerCase() === PLAUSIBLE_ORIGIN))
      .map((list) => `connect-src ${list.join(' ')}`)
    const policies = enforced.filter(({ part, before }) => isHeaderName(part, before)).flatMap(({ part }) => policiesIn(headerValue(part)))
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

  it('skips build and test output, which no deploy serves a header from, by name', () => {
    const root = mkdtempSync(join(tmpdir(), 'csp-guard-'))
    const generated = ['node_modules', 'coverage', 'out', 'build', 'dist', 'playwright-report', 'test-results', 'apps/frontend/out']
    for (const file of ['middleware.ts', 'nginx-staging.conf', ...generated.flatMap((folder) => [`${folder}/chunk.js`, `${folder}/nginx.conf`])]) {
      mkdirSync(dirname(join(root, file)), { recursive: true })
      writeFileSync(join(root, file), '')
    }
    try {
      expect([frontendSourcesIn(root), edgeConfigsIn(root)]).toEqual([[join(root, 'middleware.ts')], [join(root, 'nginx-staging.conf')]])
    } finally {
      rmSync(root, { recursive: true })
    }
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
      ['a second policy that starts with a directive the guard does not name', `add_header Content-Security-Policy "connect-src https://plausible.io, made-up-directive script; default-src 'self'" always;`, ['a policy without connect-src']],
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
      ['an MDN link', code("const docs = 'https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy'")],
      ['a label with a colon', code(`const label = "Content-Security-Policy: see the wiki"`)],
      ['a label with a colon followed by the next statement', code(`const label = "Content-Security-Policy: see the wiki"\nexport default label`)],
      ['a label with a colon in a JSX attribute', code(`<abbr title="Content-Security-Policy: see the wiki">CSP</abbr>`)],
      ['a label with a colon passed to a call', code(`t('Content-Security-Policy: see the wiki')`)],
      ['a label with a colon closing a JSX element', code(`<Hint text="Content-Security-Policy: see the wiki" />`)],
      ['a label with a colon and an apostrophe', code(`const label = "Content-Security-Policy: see the team's wiki"`)],
      ['a label with a colon in a template', code('const label = `Content-Security-Policy: see the wiki`')],
      ['a label with a colon before a semicolon',code(`const label = 'Content-Security-Policy: see the wiki'; export default label`)],
      ['a label with a colon first in a list', code(`const labels = ['Content-Security-Policy: see the wiki', 'Referrer-Policy']`)],
      ['a label with a colon last in a list', code(`const labels = ['Content-Security-Policy: see the wiki']`)],
      ['a label with a colon in an object', code(`const hints = { csp: 'Content-Security-Policy: see the wiki' }`)],
      ['an href', code('<a href="https://developer.mozilla.org/docs/Web/HTTP/Headers/Content-Security-Policy">the header</a>')],
      ['an nginx redirect path', edge('location = /csp { return 301 https://developer.mozilla.org/docs/Web/HTTP/Headers/Content-Security-Policy; }')],
    ])('does not take a mention of the header name in %s for a header', (_where, source) => {
      expect(policyProblems([source])).toEqual([])
    })

    it('still refuses the name kept in a constant, which a mention in a string cannot be told apart from', () => {
      expect(policyProblems([code("const name = 'Content-Security-Policy'")])).toEqual(['middleware.ts: a policy without connect-src'])
    })

    it('still refuses a name after a slash that is not inside a path', () => {
      expect(policyProblems([code(`res.headers.set('/Content-Security-Policy'.slice(1), "default-src 'none'")`)])).toEqual([
        'middleware.ts: a policy without connect-src',
      ])
    })

    it.each([
      ['a serialized header split later', `["Content-Security-Policy: default-src 'none'"].map((line) => line.split(': '))`],
      ['a directive without a space after the colon', `const line = "Content-Security-Policy:frame-ancestors 'none'"`],
      ['a directive with no sources', `const line = 'Content-Security-Policy: upgrade-insecure-requests'`],
      ['a directive name the spec may add', `const line = 'Content-Security-Policy: future-src https://plausible.io'`],
      ['sandbox, a directive without a hyphen', `const line = 'Content-Security-Policy: SANDBOX allow-scripts'`],
      ['a directive after one browsers ignore', `const line = "Content-Security-Policy: made-up-directive script; default-src 'none'"`],
      ['a directive after an empty one', `const line = "Content-Security-Policy: ; default-src 'none'"`],
      ['a substitution', 'const line = `Content-Security-Policy: ${policy}`'],
      ['a concatenation', "const line = 'Content-Security-Policy: ' + policy"],
      ['the name and colon ending their string', `const lines = ['Content-Security-Policy:', "default-src 'none'"]`],
      ['an escaped tab', String.raw`const line = "Content-Security-Policy:\tdefault-src 'none'"`],
      ['an escaped letter', String.raw`const line = "Content-Security-Policy: \u0064efault-src 'none'"`],
      ['a substitution after a word', 'const line = `Content-Security-Policy: made-up ${policy}`'],
      ['a quoted source inside the words', `const line = "Content-Security-Policy: made-up 'x'; default-src 'none'"`],
      ['another quote and a semicolon inside the words', `const line = "Content-Security-Policy: made-up '; default-src https://example.com"`],
      ['words in parentheses concatenated with a policy', `const line = ('Content-Security-Policy: made-up script; ') + "default-src 'none'"`],
      ['words in a list joined to a policy', `const line = ['Content-Security-Policy: made-up script; '].concat("default-src 'none'")`],
      ['words concatenated with a policy', `const line = 'Content-Security-Policy: made-up script; ' + "default-src 'none'"`],
      ['words continued on the next line', "const line = 'Content-Security-Policy: made-up script; '\n  + policy"],
      ['an escape after a word',String.raw`const line = "Content-Security-Policy: made-up \u0064efault-src 'none'"`],
    ])('still refuses a policy written after the name and a colon: %s', (_where, text) => {
      expect(policyProblems([code(text)])).toEqual(['middleware.ts: a policy without connect-src'])
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
