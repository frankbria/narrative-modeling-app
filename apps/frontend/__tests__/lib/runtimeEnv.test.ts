/**
 * Public settings are read when the page is served, never when the image is built
 * (#831): the server writes them onto `<html data-public-env>` and the browser reads
 * them from there through `publicEnv`.
 */
import { readFileSync } from 'fs'
import { join } from 'path'
import { PUBLIC_ENV_NAMES, publicEnv, publicEnvJson } from '@/lib/runtimeEnv'

const ORIGINAL_API_URL = process.env.NEXT_PUBLIC_API_URL

function restoreApiUrl() {
  // Assigning undefined would store the string 'undefined'.
  if (ORIGINAL_API_URL === undefined) delete process.env.NEXT_PUBLIC_API_URL
  else process.env.NEXT_PUBLIC_API_URL = ORIGINAL_API_URL
}

/** What a browser has when it loads a page this server rendered. */
function loadPageRenderedWith(env: Record<string, string | undefined>) {
  delete window.__PUBLIC_ENV__
  document.documentElement.dataset.publicEnv = publicEnvJson({ NODE_ENV: 'test', ...env })
}

afterEach(() => {
  delete window.__PUBLIC_ENV__
  delete document.documentElement.dataset.publicEnv
  restoreApiUrl()
})

describe('publicEnv in a browser', () => {
  it('reads the value the server wrote onto the page', () => {
    loadPageRenderedWith({ NEXT_PUBLIC_API_URL: 'https://www.example/api/v1' })

    expect(publicEnv('NEXT_PUBLIC_API_URL')).toBe('https://www.example/api/v1')
  })

  it('never falls back to the process environment, which in a bundle is what the build saw', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://build.example/api/v1'
    loadPageRenderedWith({ NEXT_PUBLIC_SENTRY_DSN: 'https://key@sentry.example/1' })

    expect(publicEnv('NEXT_PUBLIC_API_URL')).toBeUndefined()
    expect(publicEnv('NEXT_PUBLIC_SENTRY_DSN')).toBe('https://key@sentry.example/1')
  })

  it('is undefined on a page that carries no settings at all', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://build.example/api/v1'
    delete window.__PUBLIC_ENV__

    expect(publicEnv('NEXT_PUBLIC_API_URL')).toBeUndefined()
  })

  it('carries a value with markup in it intact', () => {
    const hostile = '"></html><script>alert(1)</script>'
    loadPageRenderedWith({ NEXT_PUBLIC_INVITE_REQUEST_URL: hostile })

    expect(publicEnv('NEXT_PUBLIC_INVITE_REQUEST_URL')).toBe(hostile)
  })
})

describe('publicEnvJson', () => {
  it('holds every listed setting that is set, and nothing else', () => {
    const settings = JSON.parse(
      publicEnvJson({
        NODE_ENV: 'production',
        NEXT_PUBLIC_API_URL: 'https://www.example/api/v1',
        NEXT_PUBLIC_SENTRY_DSN: 'https://key@sentry.example/1',
        NEXT_PUBLIC_SENTRY_ENVIRONMENT: '',
        NEXTAUTH_SECRET: 'never-in-a-page',
        NEXT_PUBLIC_UNLISTED: 'not-listed',
      }),
    )

    expect(settings).toEqual({
      NEXT_PUBLIC_API_URL: 'https://www.example/api/v1',
      NEXT_PUBLIC_SENTRY_DSN: 'https://key@sentry.example/1',
    })
  })

  it('carries all four public settings when each is set', () => {
    const everySetting = Object.fromEntries(PUBLIC_ENV_NAMES.map((name) => [name, `value-of-${name}`]))

    expect(JSON.parse(publicEnvJson({ NODE_ENV: 'test', ...everySetting }))).toEqual(everySetting)
  })

  it('reads the process environment when it is given none, at call time', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://dev.example/api/v1'
    expect(JSON.parse(publicEnvJson())).toMatchObject({ NEXT_PUBLIC_API_URL: 'https://dev.example/api/v1' })

    process.env.NEXT_PUBLIC_API_URL = 'https://www.example/api/v1'
    expect(JSON.parse(publicEnvJson())).toMatchObject({ NEXT_PUBLIC_API_URL: 'https://www.example/api/v1' })
  })

  it('is an empty object when nothing is set', () => {
    expect(publicEnvJson({ NODE_ENV: 'test' })).toBe('{}')
  })
})

describe('the root layout', () => {
  // The rendered page is checked on the built image by
  // scripts/ci/check_frontend_image_is_host_agnostic.sh; jest cannot render the async layout.
  it('writes the settings onto <html>, which is parsed before any script can run', () => {
    const layout = readFileSync(join(__dirname, '..', '..', 'app', 'layout.tsx'), 'utf8')

    expect(layout).toMatch(/<html [^>]*data-public-env=\{publicEnvJson\(\)\}/)
  })
})
