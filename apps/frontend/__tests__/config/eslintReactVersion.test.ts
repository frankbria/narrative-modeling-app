/**
 * Guards the one line that makes eslint 10 work (#391).
 *
 * `eslint-plugin-react@7.37.5` calls `context.getFilename()`, removed in eslint
 * 10. The only path that reaches it is `detectReactVersion()`, which runs only
 * when `settings.react.version === "detect"` — the value `eslint-config-next`
 * sets. Our config overrides it with a concrete version, and that override is the
 * entire reason lint does not crash.
 *
 * It is also fragile in a way that is invisible on review: the override wins only
 * because our block comes AFTER `nextVitals`/`nextTs` in the flat-config array.
 * Reorder those and next's `"detect"` silently wins again. The failure is a hard
 * crash during lint, so CI would catch it — but as a wall of stack trace about a
 * plugin internal, not "someone reordered the config".
 *
 * The config is ESM and loads `eslint/config`, so it is imported in a child node
 * process rather than through jest's module registry — the point is what ESLint
 * itself would resolve, which is exactly what that process reports.
 */
import { execFileSync } from 'child_process'
import path from 'path'

const ROOT = path.resolve(__dirname, '../..')

/** What ESLint will actually see, after the whole flat-config array is merged. */
function resolvedReactSetting(): string | undefined {
  const script = `
    import config from ${JSON.stringify(path.join(ROOT, 'eslint.config.mjs'))}
    // Last write wins, exactly as ESLint merges a flat config array.
    let version
    for (const block of config.flat(Infinity)) {
      if (block?.settings?.react?.version) version = block.settings.react.version
    }
    console.log(JSON.stringify(version ?? null))
  `
  const out = execFileSync('node', ['--input-type=module', '-e', script], {
    cwd: ROOT,
    encoding: 'utf8',
  })
  return JSON.parse(out.trim()) ?? undefined
}

describe('eslint config: React version', () => {
  const version = resolvedReactSetting()

  it('is set at all', () => {
    // Unset means eslint-plugin-react falls back to detection too.
    expect(version).toBeDefined()
  })

  it('is NOT "detect"', () => {
    // The whole point. "detect" reaches the removed eslint 10 API and lint dies.
    expect(version).not.toBe('detect')
  })

  it('is a concrete semver', () => {
    expect(version).toMatch(/^\d+\.\d+(\.\d+)?/)
  })

  it('matches the installed react', () => {
    // Guards drift: the config resolves this from node_modules rather than
    // hardcoding it, and this asserts that stays true. A literal that someone
    // "helpfully" pins back would pass every test above and fail this one.
    // (no eslint-disable needed: __tests__/** already relaxes no-require-imports)
    const installed = require('react/package.json').version
    expect(version).toBe(installed)
  })
})
