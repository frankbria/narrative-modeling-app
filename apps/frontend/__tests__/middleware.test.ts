/**
 * @jest-environment node
 */
jest.mock('next-auth/jwt', () => ({ getToken: jest.fn() }))

import middleware from '@/middleware'
import { getToken } from 'next-auth/jwt'
import type { NextRequest } from 'next/server'

const mockGetToken = getToken as jest.MockedFunction<typeof getToken>

function mockRequest(
  pathname: string,
  { method = 'GET', origin = 'http://localhost:3000' }: { method?: string; origin?: string | null } = {}
): NextRequest {
  const url = `http://localhost:3000${pathname}`
  return {
    nextUrl: { pathname },
    url,
    method,
    headers: {
      get: (h: string) => (h === 'origin' ? origin : null),
    },
  } as unknown as NextRequest
}

describe('middleware (deny-by-default)', () => {
  beforeEach(() => mockGetToken.mockReset())

  it.each([
    '/admin',
    '/settings/api',
    '/predict',
    '/evaluate',
    '/transform',
    '/features',
    '/experiments',
    '/recipes',
    '/review',
    '/dashboard',
    '/', // previously the only implicitly-covered root
    '/some-future-page', // proves new pages are protected automatically
  ])('redirects requests without a valid session for protected page %s', async (pathname) => {
    mockGetToken.mockResolvedValue(null) // no / invalid token
    const res = await middleware(mockRequest(pathname))
    expect(res.status).toBe(307) // NextResponse.redirect default
    expect(res.headers.get('location')).toContain('/auth/signin')
    expect(res.headers.get('location')).toContain(`callbackUrl=${encodeURIComponent(pathname)}`)
  })

  it('allows a request with a valid session to a protected page', async () => {
    mockGetToken.mockResolvedValue({ sub: 'user-1' } as never)
    const res = await middleware(mockRequest('/admin'))
    expect(res.status).not.toBe(307)
  })

  it('always allows the public auth flow (without checking a token)', async () => {
    const res = await middleware(mockRequest('/auth/signin'))
    expect(res.status).not.toBe(307)
    expect(mockGetToken).not.toHaveBeenCalled()
  })

  it('does not redirect API routes (they self-guard with 401)', async () => {
    const res = await middleware(mockRequest('/api/chat', { method: 'POST' }))
    expect(res.status).not.toBe(307)
    expect(mockGetToken).not.toHaveBeenCalled()
  })
})

describe('middleware CORS allowlist (#256)', () => {
  const ORIGINAL = process.env.ALLOWED_ORIGINS

  beforeEach(() => {
    mockGetToken.mockReset()
    mockGetToken.mockResolvedValue({ sub: 'user-1' } as never) // authenticated
    process.env.ALLOWED_ORIGINS = 'https://app.example.com, https://staging.example.com'
  })

  afterEach(() => {
    if (ORIGINAL === undefined) delete process.env.ALLOWED_ORIGINS
    else process.env.ALLOWED_ORIGINS = ORIGINAL
  })

  it('echoes an allowlisted Origin', async () => {
    const res = await middleware(mockRequest('/dashboard', { origin: 'https://app.example.com' }))
    expect(res.headers.get('Access-Control-Allow-Origin')).toBe('https://app.example.com')
  })

  it('does NOT set Access-Control-Allow-Origin for an off-allowlist Origin', async () => {
    const res = await middleware(mockRequest('/dashboard', { origin: 'https://evil.example.com' }))
    expect(res.headers.get('Access-Control-Allow-Origin')).toBeNull()
  })

  it('does not reflect an arbitrary Origin when the allowlist is empty', async () => {
    process.env.ALLOWED_ORIGINS = ''
    const res = await middleware(mockRequest('/dashboard', { origin: 'https://app.example.com' }))
    expect(res.headers.get('Access-Control-Allow-Origin')).toBeNull()
  })

  it('sets Vary: Origin so caches never replay one origin\'s ACAO for another', async () => {
    const allowed = await middleware(mockRequest('/dashboard', { origin: 'https://app.example.com' }))
    expect(allowed.headers.get('Vary')).toBe('Origin')
    const blocked = await middleware(mockRequest('/dashboard', { origin: 'https://evil.example.com' }))
    expect(blocked.headers.get('Vary')).toBe('Origin')
  })

  it('honors the allowlist on OPTIONS preflight (allowed vs blocked)', async () => {
    const allowed = await middleware(mockRequest('/dashboard', { method: 'OPTIONS', origin: 'https://staging.example.com' }))
    expect(allowed.status).toBe(204)
    expect(allowed.headers.get('Access-Control-Allow-Origin')).toBe('https://staging.example.com')

    const blocked = await middleware(mockRequest('/dashboard', { method: 'OPTIONS', origin: 'https://evil.example.com' }))
    expect(blocked.status).toBe(204)
    expect(blocked.headers.get('Access-Control-Allow-Origin')).toBeNull()
  })
})
