import { sanitizeForDisplay, validateDatasetId } from '@/lib/utils/sanitize'

describe('sanitizeForDisplay', () => {
  it.each([
    [null, ''],
    [undefined, ''],
    [42, '42'],
    ['plain text', 'plain text'],
    ['<b>bold</b> text', 'bold text'],
    // the tags go, the script body stays as inert text
    ['<script>alert(1)</script>', 'alert(1)'],
    ['<SCRIPT type="x">alert(1)</SCRIPT>after', 'alert(1)after'],
    ['<script src=x>', ''],
    ['<scr<script>ipt>alert(1)</scr</script>ipt>', 'ipt>alert(1)ipt>'],
    ['a < b and c > d', 'a  d'],
    ['a <script', 'a <script'],
    [{ a: '<i>x</i>' }, '{"a":"x"}'],
  ])('%j becomes %j', (input, expected) => {
    expect(sanitizeForDisplay(input)).toBe(expected)
  })

  it('leaves no script element for any input the tag strip can leave behind', () => {
    for (const input of ['<script>x</script>', '<<script>script>x<</script>/script>', '<script\n>x</script\n>']) {
      expect(sanitizeForDisplay(input)).not.toMatch(/<\/?script/i)
    }
  })

  it('stringifies an object that cannot be stringified as a placeholder', () => {
    const circular: Record<string, unknown> = {}
    circular.self = circular

    expect(sanitizeForDisplay(circular)).toBe('[Complex Object]')
  })

  it('cuts to maxLength and marks the cut', () => {
    expect(sanitizeForDisplay('abcdef', 3)).toBe('abc...')
    expect(sanitizeForDisplay('abc', 3)).toBe('abc')
  })
})

describe('validateDatasetId', () => {
  it.each([
    ['abc-123_X', 'abc-123_X'],
    ['', null],
    ['has space', null],
    ['../etc', null],
    ['a'.repeat(101), null],
    ['a'.repeat(100), 'a'.repeat(100)],
  ])('%j gives %j', (input, expected) => {
    expect(validateDatasetId(input)).toBe(expected)
  })
})
