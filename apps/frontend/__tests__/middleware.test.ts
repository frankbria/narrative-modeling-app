/**
 * @jest-environment node
 */
jest.mock('next-auth/jwt', () => ({ getToken: jest.fn() }))

import middleware from '@/middleware'
import { getToken } from 'next-auth/jwt'
import type { NextRequest } from 'next/server'

const mockGetToken = getToken as jest.MockedFunction<typeof getToken>

function mockRequest(pathname: string, { method = 'GET' }: { method?: string } = {}): NextRequest {
  const url = `http://localhost:3000${pathname}`
  return {
    nextUrl: { pathname },
    url,
    method,
    headers: {
      get: (h: string) => (h === 'origin' ? 'http://localhost:3000' : null),
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
