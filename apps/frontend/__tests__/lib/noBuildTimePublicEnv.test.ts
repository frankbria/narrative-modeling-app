/**
 * @jest-environment node
 *
 * `next build` replaces every `process.env.NEXT_PUBLIC_*` member access with the
 * value present at build, which would pin one host's settings into the image that
 * serves both (#831). Public settings are read through `lib/runtimeEnv.ts` instead.
 */
import { readFileSync } from 'fs'
import { join } from 'path'
import { globSync } from 'glob'

const ROOT = join(__dirname, '..', '..')

const files = globSync('{app,lib,components,hooks}/**/*.{ts,tsx}', {
  cwd: ROOT,
  ignore: ['**/__tests__/**', '**/node_modules/**', '**/*.test.*'],
}).concat(globSync('{instrumentation*,middleware,auth}.ts', { cwd: ROOT }))

describe('no public setting is read at build time', () => {
  it('scans the app, its root entry points and a non-trivial number of source files', () => {
    expect(files.length).toBeGreaterThan(50)
    expect(files).toEqual(
      expect.arrayContaining(['instrumentation-client.ts', 'instrumentation.ts', 'middleware.ts', 'auth.ts']),
    )
  })

  it('no source file reads process.env.NEXT_PUBLIC_* as a member access', () => {
    const offenders = files.filter((file) => /process\.env\.NEXT_PUBLIC_/.test(readFileSync(join(ROOT, file), 'utf8')))

    expect(offenders).toEqual([])
  })
})
