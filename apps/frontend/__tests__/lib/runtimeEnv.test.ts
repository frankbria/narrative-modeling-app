/**
 * Public settings are read when the page is served, never when the image is built
 * (#831): the server renders them into `window.__PUBLIC_ENV__` and both halves read
 * them through `publicEnv`.
 */
import { PUBLIC_ENV_NAMES, publicEnv, publicEnvScript } from '@/lib/runtimeEnv'

const ORIGINAL_API_URL = process.env.NEXT_PUBLIC_API_URL

function runInBrowser(scriptText: string): Window['__PUBLIC_ENV__'] {
  new Function(scriptText)()
  return window.__PUBLIC_ENV__
}

afterEach(() => {
  delete window.__PUBLIC_ENV__
  process.env.NEXT_PUBLIC_API_URL = ORIGINAL_API_URL
})

describe('publicEnv', () => {
  it('prefers the value the server rendered into the page over the process environment', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://build.example/api/v1'
    window.__PUBLIC_ENV__ = { NEXT_PUBLIC_API_URL: 'https://www.example/api/v1' }

    expect(publicEnv('NEXT_PUBLIC_API_URL')).toBe('https://www.example/api/v1')
  })

  it('falls back to the process environment, which is what the server reads', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://dev.example/api/v1'

    expect(publicEnv('NEXT_PUBLIC_API_URL')).toBe('https://dev.example/api/v1')
  })

  it('falls back to the process environment for a name the page does not carry', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://dev.example/api/v1'
    window.__PUBLIC_ENV__ = { NEXT_PUBLIC_SENTRY_DSN: 'https://key@sentry.example/1' }

    expect(publicEnv('NEXT_PUBLIC_API_URL')).toBe('https://dev.example/api/v1')
  })

  it.each([undefined, ''])('is undefined for %p, so a blank from compose takes the call site default', (value) => {
    if (value === undefined) delete process.env.NEXT_PUBLIC_API_URL
    else process.env.NEXT_PUBLIC_API_URL = value

    expect(publicEnv('NEXT_PUBLIC_API_URL')).toBeUndefined()
  })
})

describe('publicEnvScript', () => {
  it('hands the browser every listed setting that is set, and nothing else', () => {
    const script = publicEnvScript({
      NODE_ENV: 'production',
      NEXT_PUBLIC_API_URL: 'https://www.example/api/v1',
      NEXT_PUBLIC_SENTRY_DSN: 'https://key@sentry.example/1',
      NEXT_PUBLIC_SENTRY_ENVIRONMENT: '',
      NEXTAUTH_SECRET: 'never-in-a-page',
      NEXT_PUBLIC_UNLISTED: 'not-listed',
    })

    expect(script).not.toContain('never-in-a-page')
    expect(runInBrowser(script)).toEqual({
      NEXT_PUBLIC_API_URL: 'https://www.example/api/v1',
      NEXT_PUBLIC_SENTRY_DSN: 'https://key@sentry.example/1',
    })
  })

  it('carries all four public settings when each is set', () => {
    const everySetting = Object.fromEntries(PUBLIC_ENV_NAMES.map((name) => [name, `value-of-${name}`]))

    expect(runInBrowser(publicEnvScript({ NODE_ENV: 'test', ...everySetting }))).toEqual(everySetting)
  })

  it('reads the process environment when it is given none', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://dev.example/api/v1'

    expect(runInBrowser(publicEnvScript())).toMatchObject({ NEXT_PUBLIC_API_URL: 'https://dev.example/api/v1' })
  })

  it('cannot close its own script element, and the value still arrives intact', () => {
    const hostile = '</script><script>alert(1)</script>'
    const script = publicEnvScript({ NODE_ENV: 'test', NEXT_PUBLIC_INVITE_REQUEST_URL: hostile })

    expect(script).not.toContain('<')
    expect(runInBrowser(script)).toEqual({ NEXT_PUBLIC_INVITE_REQUEST_URL: hostile })
  })

  it('is an empty object when nothing is set', () => {
    expect(runInBrowser(publicEnvScript({ NODE_ENV: 'test' }))).toEqual({})
  })
})
