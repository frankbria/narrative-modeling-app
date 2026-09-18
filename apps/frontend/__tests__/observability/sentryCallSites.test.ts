/**
 * #769: scrubSentryEvent only scrubs the fields the SDK and these files fill
 * in. Any other Sentry call site (captureException with `extra`, setTag,
 * addBreadcrumb, ...) can put data past it, so a new one must be reviewed
 * against the scrubber and added here on purpose.
 */
import { readFileSync } from 'fs'
import { globSync } from 'glob'

const REVIEWED = [
  'app/global-error.tsx',
  'instrumentation.ts',
  'instrumentation-client.ts',
  'lib/observability/sentry.ts',
]

it('only reviewed files import Sentry', () => {
  const importers = globSync('{app,components,lib,hooks}/**/*.{ts,tsx}')
    .concat(globSync('*.ts'))
    .filter((f) => /from ['"]@sentry\//.test(readFileSync(f, 'utf8')))
    .sort()
  expect(importers).toEqual([...REVIEWED].sort())
})
