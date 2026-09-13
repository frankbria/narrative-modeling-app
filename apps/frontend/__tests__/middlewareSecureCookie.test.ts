/**
 * @jest-environment node
 *
 * #469 [P0.26]: middleware's getToken must read the session cookie Auth.js
 * actually wrote. Over HTTPS Auth.js writes `__Secure-authjs.session-token`
 * (secure prefix, salt = that name); over http (dev/e2e) it writes the bare
 * `authjs.session-token`. `getToken({ req, secret })` with no `secureCookie`
 * defaults to the bare name and the bare salt, so on HTTPS it finds nothing and
 * every authenticated page redirects to sign-in.
 *
 * Unlike `middleware.test.ts` (which mocks `getToken` and is therefore blind to
 * cookie-name resolution), this exercises the REAL `getToken` against a REAL
 * encoded cookie, so it fails against the pre-fix middleware and is the durable
 * CI guard AC3 asks for. Only the live-staging confirmation (AC1) needs a human.
 */
import { encode } from '@auth/core/jwt'
import middleware from '@/middleware'
import type { NextRequest } from 'next/server'

const SECRET = 'test-secret-value-at-least-32-characters-long!!'
const SECURE_COOKIE = '__Secure-authjs.session-token'
const PLAIN_COOKIE = 'authjs.session-token'

function requestWith(
  cookieHeader: string | null,
  { protocol = 'https:', host = 'app.example.com' } = {},
): NextRequest {
  const pathname = '/dashboard'
  const headers = new Headers()
  if (cookieHeader) headers.set('cookie', cookieHeader)
  return {
    nextUrl: { pathname, protocol },
    url: `${protocol}//${host}${pathname}`,
    method: 'GET',
    headers,
  } as unknown as NextRequest
}

/** Mint a session cookie exactly as Auth.js does: salt === cookie name. */
async function sessionCookie(cookieName: string): Promise<string> {
  const value = await encode({
    token: { sub: 'user-1', email: 'user@example.com' },
    secret: SECRET,
    salt: cookieName,
  })
  return `${cookieName}=${value}`
}

describe('#469 middleware reads the Auth.js session cookie over HTTPS', () => {
  const prev = process.env.NEXTAUTH_SECRET
  beforeAll(() => {
    process.env.NEXTAUTH_SECRET = SECRET
  })
  afterAll(() => {
    process.env.NEXTAUTH_SECRET = prev
  })

  it('accepts the secure-prefixed cookie (HTTPS) — no redirect', async () => {
    const res = await middleware(requestWith(await sessionCookie(SECURE_COOKIE)))
    expect(res.status).not.toBe(307)
    expect(res.headers.get('location')).toBeNull()
  })

  it('still accepts the bare cookie (http dev/e2e) — no redirect', async () => {
    const res = await middleware(
      requestWith(await sessionCookie(PLAIN_COOKIE), { protocol: 'http:', host: 'localhost:3010' }),
    )
    expect(res.status).not.toBe(307)
    expect(res.headers.get('location')).toBeNull()
  })

  it('redirects when no session cookie is present', async () => {
    const res = await middleware(requestWith(null))
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toContain('/auth/signin')
  })

  it('redirects a secure-prefixed cookie signed with the wrong secret (forged/stale)', async () => {
    const forged = await encode({
      token: { sub: 'user-1' },
      secret: 'a-different-secret-value-also-32-characters!!',
      salt: SECURE_COOKIE,
    })
    const res = await middleware(requestWith(`${SECURE_COOKIE}=${forged}`))
    expect(res.status).toBe(307)
  })
})
