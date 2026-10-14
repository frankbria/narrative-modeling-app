/**
 * @jest-environment node
 *
 * An e2e test does not end itself with a bare `return;` (#921).
 *
 * Specs used to log a line and `return` when a precondition failed: the workflow gate
 * bounced the page, a form field could not be selected, a tab was missing. The test
 * then passed, and the failure it existed to catch never surfaced: the training form
 * offered no target for any dataset (#919) while four smoke tests stayed green. A
 * precondition is set up and asserted (seed the workflow, train through the fixture),
 * or the test is deleted.
 */
import { readFileSync } from 'fs'
import { join } from 'path'
import { globSync } from 'glob'

const ROOT = join(__dirname, '..', '..')
// A bare `return;` (or `return ;`) alone on a line, ending `if (...)` or `else`, or in a
// one-line block, with or without a trailing comment.
const EARLY_RETURN = /(^|[)}{]|\belse)\s*return\s*;\s*(\}\s*)?(\/\/.*)?$/m

const specs = globSync('e2e/**/*.spec.ts', { cwd: ROOT })

describe('e2e specs do not return early', () => {
  it('scans the specs', () => {
    expect(specs.length).toBeGreaterThan(20)
  })

  it('no spec ends a test with a bare return', () => {
    const offenders = specs.filter((f) => EARLY_RETURN.test(readFileSync(join(ROOT, f), 'utf8')))
    expect(offenders).toEqual([])
  })

  it.each([
    '    if (!ready) return;',
    '      return;',
    '      return ;',
    '    } else return;',
    '    if (!ready) { return; }',
    '      return; // the gate bounced us',
  ])('the pattern catches %j', (line) => {
    expect(EARLY_RETURN.test(`${line}\n`)).toBe(true)
  })

  it.each(['    return page.url();', '    const returned = await go();', '    // return; in prose'])(
    'the pattern leaves %j alone',
    (line) => {
      expect(EARLY_RETURN.test(`${line}\n`)).toBe(false)
    }
  )
})
