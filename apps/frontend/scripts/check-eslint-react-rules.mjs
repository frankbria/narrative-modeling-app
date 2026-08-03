// Every enabled eslint-plugin-react rule, exercised under the installed ESLint (#432).
//
// WHY THIS EXISTS. We run `eslint-plugin-react@7.37.5` outside its declared peer
// range (`eslint ^9.7`) on eslint 10. It works because `settings.react.version`
// is pinned, which skips the only path reaching the removed
// `context.getFilename()`.
//
// The gap that left: #391's evidence was rule-for-rule *output* parity across the
// repo, which only proves the rules our source happens to trigger. 17 react/*
// rules are enabled and our code trips two. The other 15 could reach another
// removed API on a file nobody has written yet, and the first symptom would be a
// crash in someone's unrelated PR.
//
// So each enabled rule runs alone against a fixture rich enough to make it build
// listeners and walk real components. Rule setup is where the original crash was
// (Components.componentRule -> usedPropTypesInstructions -> testReactVersion), so
// this covers the dangerous path for every rule, not just the violated ones.
//
// This is what let #432 close rather than sit open waiting on upstream. When
// eslint-plugin-react ships an eslint-10 release the pin can stay (good practice
// regardless) and this keeps holding.
//
// Usage: npm run check:eslint-react

import { ESLint, Linter } from 'eslint'

// Rich enough that the rules build listeners and walk real components.
const FIXTURE = `
import React, { useRef, useState, Component } from 'react'

export class Legacy extends Component {
  render() {
    return <div ref={this.el}>{this.props.children}</div>
  }
}

export function Fn({ items, label }) {
  const [n, setN] = useState(0)
  const box = useRef(null)
  return (
    <section aria-label={label} ref={box}>
      <button onClick={() => setN(n + 1)}>{n}</button>
      <ul>{items.map((i) => <li key={i.id}>{i.name}</li>)}</ul>
      <Legacy>{'nested'}</Legacy>
    </section>
  )
}

export default function App() {
  return <Fn items={[{ id: 1, name: 'a' }]} label="x" />
}
`

// How many react/* rules eslint-config-next enables today. PINNED, not a floor:
// a floor lets the set shrink silently, which is coverage quietly disappearing
// while the check still reports green. If this trips, look at WHY the count moved
// (a config-next bump usually) and update it deliberately — same ratchet
// discipline as `--max-warnings`.
const EXPECTED_RULES = 17

const eslint = new ESLint()
// Any path matching the TSX glob resolves the same config; nothing is read from
// disk, and the file does not need to exist. Named to say so, rather than
// pointing at a real component whose deletion would puzzle a future reader.
const config = await eslint.calculateConfigForFile('components/__config_probe__.tsx')

const enabled = Object.entries(config.rules ?? {})
  .filter(([rule]) => rule.startsWith('react/'))
  .filter(([, value]) => {
    const level = Array.isArray(value) ? value[0] : value
    return level !== 'off' && level !== 0
  })
  .map(([rule]) => rule)

console.log(`eslint:  ${ESLint.version}`)
console.log(`plugin:  eslint-plugin-react (peer range says eslint ^9.7)`)
console.log(`enabled react/* rules: ${enabled.length}\n`)

if (enabled.length !== EXPECTED_RULES) {
  // Catches both directions. Zero (or few) means the plugin stopped loading and
  // every check below would pass vacuously. Fewer-but-nonzero means rules
  // silently stopped being enforced. More means new rules nobody has verified.
  console.error(
    `Expected ${EXPECTED_RULES} enabled react/* rules, found ${enabled.length}.\n` +
    `If eslint-config-next changed its rule set, verify the new list and update ` +
    `EXPECTED_RULES deliberately.`
  )
  process.exit(1)
}

// The plugin instance ESLint itself resolved, taken off the computed config.
// Requiring it by path fails: eslint-config-next's `exports` map does not expose
// its nested node_modules, and this is the more honest object anyway — it is the
// one that would actually run.
const plugin = config.plugins?.react
if (!plugin?.rules) {
  console.error('Could not reach the react plugin from the computed config.')
  process.exit(1)
}
// The REPO's resolved settings, not settings this script invents. Injecting a
// known-good `react.version` here would test the plugin in a vacuum and pass
// even if our own config had reverted to "detect" — which is the exact
// incompatibility being guarded. Using what ESLint computed means this fails
// when the real configuration regresses.
const settings = config.settings ?? {}
console.log(`settings.react.version: ${settings.react?.version ?? '(unset)'}\n`)
let failed = 0

for (const rule of enabled) {
  // One rule at a time: a crash in any single rule is otherwise masked by
  // whichever rule ESLint happens to load first.
  //
  // Bare `'error'`, deliberately dropping any options the real config passes.
  // This checks that a rule LOADS and RUNS under this ESLint — the failure mode
  // being guarded — which happens at listener setup and is option-independent.
  // It is not a check of configured behaviour, and should not be read as one.
  try {
    const messages = new Linter().verify(FIXTURE, {
      // No `files` key: with one present the config does not apply to a string
      // passed to Linter.verify, and every rule reports a bogus parse error.
      plugins: { react: plugin },
      languageOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        parserOptions: { ecmaFeatures: { jsx: true } },
      },
      settings,
      rules: { [rule]: 'error' },
    })
    const fatal = messages.find((m) => m.fatal)
    if (fatal) {
      console.log(`FAIL  ${rule} — ${fatal.message}`)
      failed++
    } else {
      console.log(`PASS  ${rule}`)
    }
  } catch (error) {
    console.log(`FAIL  ${rule} — threw ${error.message}`)
    failed++
  }
}

console.log(
  failed
    ? `\nRESULT: ${failed} rule(s) are NOT compatible with eslint ${ESLint.version}`
    : `\nRESULT: all ${enabled.length} enabled react/* rules work on eslint ${ESLint.version}`
)
process.exit(failed ? 1 : 0)
