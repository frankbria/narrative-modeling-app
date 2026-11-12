/**
 * The modules that read a public setting as they load get this host's value from the
 * page, not a value from the build (#831). Each is imported after a page "rendered by
 * production" is in place, the way a browser loads them.
 */
import { publicEnvJson } from '@/lib/runtimeEnv'

const mockSentryInit = jest.fn()
jest.mock('@sentry/nextjs', () => ({ init: (options: unknown) => mockSentryInit(options) }))
jest.mock('@/lib/auth-helpers', () => ({ getAuthToken: jest.fn().mockResolvedValue('token') }))

const API = 'https://www.example.test/api/v1'
const DSN = 'https://key@sentry.example.test/1'

function loadPageRenderedWith(env: Record<string, string>) {
  delete window.__PUBLIC_ENV__
  document.documentElement.dataset.publicEnv = publicEnvJson({ NODE_ENV: 'test', ...env })
}

function requestedUrl(): string {
  return (global.fetch as jest.Mock).mock.calls[0][0]
}

beforeEach(() => {
  jest.resetModules()
  mockSentryInit.mockClear()
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: jest.fn().mockResolvedValue({}) })
})

afterEach(() => {
  delete window.__PUBLIC_ENV__
  delete document.documentElement.dataset.publicEnv
})

describe('browser error reporting', () => {
  it('starts with the DSN and environment of the host that served the page', async () => {
    loadPageRenderedWith({ NEXT_PUBLIC_SENTRY_DSN: DSN, NEXT_PUBLIC_SENTRY_ENVIRONMENT: 'production' })

    await import('@/instrumentation-client')

    expect(mockSentryInit).toHaveBeenCalledTimes(1)
    expect(mockSentryInit.mock.calls[0][0]).toMatchObject({ dsn: DSN, environment: 'production' })
  })

  it('stays off on a host with no DSN, whatever the build saw', async () => {
    const original = process.env.NEXT_PUBLIC_SENTRY_DSN
    process.env.NEXT_PUBLIC_SENTRY_DSN = 'https://from-the-build@sentry.example.test/9'
    try {
      loadPageRenderedWith({ NEXT_PUBLIC_API_URL: API })

      await import('@/instrumentation-client')

      expect(mockSentryInit).not.toHaveBeenCalled()
    } finally {
      if (original === undefined) delete process.env.NEXT_PUBLIC_SENTRY_DSN
      else process.env.NEXT_PUBLIC_SENTRY_DSN = original
    }
  })
})

describe('service clients', () => {
  // Paths are literals from the backend's route table, as in apiUrlConstruction.test.ts.
  it('the quality report is requested from this host API', async () => {
    loadPageRenderedWith({ NEXT_PUBLIC_API_URL: API })
    const { QualityService } = await import('@/lib/services/quality')

    await QualityService.getQualityReport('file 1')

    expect(requestedUrl()).toBe(`${API}/data/file%201/quality-report`)
  })

  it('the correlation matrix is requested from this host API', async () => {
    loadPageRenderedWith({ NEXT_PUBLIC_API_URL: API })
    const { getCorrelationMatrix } = await import('@/lib/services/visualization')

    await getCorrelationMatrix('ds-1', 'token')

    expect(requestedUrl()).toBe(`${API}/visualizations/correlation/ds-1`)
  })

  it('a page with no API setting falls back to the local development API', async () => {
    loadPageRenderedWith({})
    const { getCorrelationMatrix } = await import('@/lib/services/visualization')

    await getCorrelationMatrix('ds-1')

    expect(requestedUrl()).toBe('http://localhost:8000/api/v1/visualizations/correlation/ds-1')
  })
})
