/**
 * @jest-environment node
 */
jest.mock('next-auth/jwt', () => ({ getToken: jest.fn() }))

import middleware, { config } from '@/middleware'
import { PUBLIC_LINKS } from '@/lib/publicLinks'
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
      // The cookie value is irrelevant here since getToken is mocked — whether a
      // valid session exists is decided by the mock's return value, not by the
      // header. Kept only for request-shape realism. Real secure/bare cookie
      // resolution is covered by middlewareSecureCookie.test.ts (#469).
      get: (h: string) =>
        h === 'origin' ? origin : h === 'cookie' ? 'authjs.session-token=stub' : null,
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
    '/review',
    '/dashboard',
    '/some-future-page', // proves new pages are protected automatically
    '/legality', // the /legal public prefix must not leak onto a lookalike path
    '/legal-review',
    '/pricingx', // the /pricing exact-path exemption must not leak onto a lookalike
    '/pricing/plans',
    '/security/x', // the exact-path exemptions of #772 do not extend to children
    '/securityx',
    '/how-it-works/x',
    '/how-it-works-not',
  ])('redirects requests without a valid session for protected page %s', async (pathname) => {
    mockGetToken.mockResolvedValue(null) // no / invalid token
    const res = await middleware(mockRequest(pathname))
    expect(res.status).toBe(307) // NextResponse.redirect default
    expect(res.headers.get('location')).toContain('/auth/signin')
    expect(res.headers.get('location')).toContain(`callbackUrl=${encodeURIComponent(pathname)}`)
  })

  it('allows a request with a valid session to a protected page', async () => {
    // /dashboard rather than /admin: since #477 the admin route also needs the
    // ADMIN_EMAILS check, which is asserted separately below.
    mockGetToken.mockResolvedValue({ sub: 'user-1' } as never)
    const res = await middleware(mockRequest('/dashboard'))
    expect(res.status).not.toBe(307)
    expect(res.headers.get('x-middleware-rewrite')).toBeNull()
  })

  it('always allows the public auth flow (without checking a token)', async () => {
    const res = await middleware(mockRequest('/auth/signin'))
    expect(res.status).not.toBe(307)
    expect(mockGetToken).not.toHaveBeenCalled()
  })

  // Issue #473: Stripe reviewers, regulators and prospective customers all read
  // these before they have an account. Behind the session wall they are useless.
  //
  // Scope note: `mockRequest` sets nextUrl.pathname to the literal string given,
  // so these cases cover what middleware itself decides and nothing more. Path
  // normalisation (`/legal/../dashboard`, `//legal/terms`, `/legal%2F..`) happens
  // in the routing layer BEFORE middleware runs, so a test passing those strings
  // here would assert against a pathname the runtime never produces and would
  // pass whether or not normalisation actually protects us. Those are verified
  // against a real build instead — see the table in PR #601.
  it.each(['/legal/terms', '/legal/privacy'])(
    'always allows the public legal page %s (without checking a token)',
    async (pathname) => {
      const res = await middleware(mockRequest(pathname))
      expect(res.status).not.toBe(307)
      expect(mockGetToken).not.toHaveBeenCalled()
    },
  )

  // Issue #475: a prospective customer reads the price before they have an
  // account. Exact path, not a prefix — a prefix would make every future file
  // under it public by construction (the /legal/ note in CLAUDE.md).
  it('always allows the public /pricing page (without checking a token)', async () => {
    const res = await middleware(mockRequest('/pricing'))
    expect(res.status).not.toBe(307)
    expect(res.headers.get('x-middleware-rewrite')).toBeNull()
    expect(mockGetToken).not.toHaveBeenCalled()
  })

  // Issue #766: the landing page, and the two files a crawler fetches before it
  // decides anything. /robots.txt and /sitemap.xml are not excluded by the
  // matcher's extension list, so without an entry they redirect to sign-in.
  it.each(['/', '/security', '/how-it-works', '/robots.txt', '/sitemap.xml'])(
    'always allows the public page %s (without checking a token)',
    async (pathname) => {
      const res = await middleware(mockRequest(pathname))
      expect(res.status).not.toBe(307)
      expect(res.headers.get('x-middleware-rewrite')).toBeNull()
      expect(mockGetToken).not.toHaveBeenCalled()
    },
  )

  // #772 AC5: a link added to the shared list must also be reachable anonymously.
  it.each(PUBLIC_LINKS.map((link) => link.href))(
    'lets the shared public link %s through without a session',
    async (pathname) => {
      const res = await middleware(mockRequest(pathname))
      expect(res.status).not.toBe(307)
      expect(mockGetToken).not.toHaveBeenCalled()
    },
  )

  it.each(['/robots.txtx', '/sitemap.xml/extra', '/sitemap'])(
    'keeps the lookalike %s behind the session wall',
    async (pathname) => {
      mockGetToken.mockResolvedValue(null)
      const res = await middleware(mockRequest(pathname))
      expect(res.status).toBe(307)
    },
  )

  it('does not redirect API routes (they self-guard with 401)', async () => {
    const res = await middleware(mockRequest('/api/chat', { method: 'POST' }))
    expect(res.status).not.toBe(307)
    expect(mockGetToken).not.toHaveBeenCalled()
  })
})

// #772: the public pages name an image and a video under /how-it-works/. A file the matcher
// does not exempt goes through the session check, so an anonymous visitor's request for it
// is a redirect to sign-in: the page renders and its video does not play.
describe('middleware matcher', () => {
  const pageMatcher = new RegExp(`^${config.matcher[0]}$`)

  it.each([
    '/how-it-works/churn-walkthrough.webm',
    '/how-it-works/data_loading.webp',
    '/logo.svg',
    '/_next/static/chunks/app.js',
  ])('leaves the static file %s to the file server', (pathname) => {
    expect(pageMatcher.test(pathname)).toBe(false)
  })

  it.each(['/dashboard', '/security', '/how-it-works', '/sitemap.xml'])('runs middleware for the page %s', (pathname) => {
    expect(pageMatcher.test(pathname)).toBe(true)
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

// Issue #477: authentication is not authorization. Every signed-in tenant used to
// reach /admin; now only an email on ADMIN_EMAILS does, decided here — server-side
// — not by the page hiding itself. A non-admin gets the same answer as for a page
// that does not exist, so the route is not an existence oracle either.
describe('middleware /admin authorization (#477)', () => {
  const ORIGINAL = process.env.ADMIN_EMAILS
  const NOT_FOUND = 'http://localhost:3000/_not-found'

  beforeEach(() => {
    mockGetToken.mockReset()
    process.env.ADMIN_EMAILS = 'root@example.com, Ops@Example.com'
  })

  afterEach(() => {
    if (ORIGINAL === undefined) delete process.env.ADMIN_EMAILS
    else process.env.ADMIN_EMAILS = ORIGINAL
  })

  it.each(['/admin', '/admin/', '/admin/anything'])(
    'answers 404 (not-found rewrite) to an authenticated non-admin on %s',
    async (pathname) => {
      mockGetToken.mockResolvedValue({ sub: 'user-1', email: 'tenant@example.com' } as never)
      const res = await middleware(mockRequest(pathname))
      expect(res.status).not.toBe(307)
      expect(res.headers.get('x-middleware-rewrite')).toBe(NOT_FOUND)
    },
  )

  it('lets a listed admin through (case-insensitive)', async () => {
    mockGetToken.mockResolvedValue({ sub: 'user-2', email: 'ops@example.com' } as never)
    const res = await middleware(mockRequest('/admin'))
    expect(res.status).not.toBe(307)
    expect(res.headers.get('x-middleware-rewrite')).toBeNull()
  })

  it('fails closed: with ADMIN_EMAILS unset nobody reaches /admin', async () => {
    delete process.env.ADMIN_EMAILS
    mockGetToken.mockResolvedValue({ sub: 'user-2', email: 'ops@example.com' } as never)
    const res = await middleware(mockRequest('/admin'))
    expect(res.headers.get('x-middleware-rewrite')).toBe(NOT_FOUND)
  })

  it('a token without an email is not an admin', async () => {
    mockGetToken.mockResolvedValue({ sub: 'user-3' } as never)
    const res = await middleware(mockRequest('/admin'))
    expect(res.headers.get('x-middleware-rewrite')).toBe(NOT_FOUND)
  })

  it('still redirects an unauthenticated request to sign-in first', async () => {
    mockGetToken.mockResolvedValue(null)
    const res = await middleware(mockRequest('/admin'))
    expect(res.status).toBe(307)
  })

  it('does not treat a lookalike prefix as the admin route', async () => {
    mockGetToken.mockResolvedValue({ sub: 'user-1', email: 'tenant@example.com' } as never)
    const res = await middleware(mockRequest('/administration'))
    expect(res.status).not.toBe(307)
    expect(res.headers.get('x-middleware-rewrite')).toBeNull()
  })
})
