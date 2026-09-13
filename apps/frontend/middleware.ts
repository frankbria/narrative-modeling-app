// ./middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";
import { isAdminEmail } from "@/lib/admin-allowlist";

// Over HTTPS Auth.js writes the session cookie as `__Secure-authjs.session-token`
// (salt === cookie name); over http (dev/e2e) as the bare `authjs.session-token`.
// `getToken({ req, secret })` with no `secureCookie` defaults to the bare name and
// bare salt, so on the production/staging HTTPS URL it reads nothing and every
// authenticated page redirects to sign-in (#469). Detecting HTTPS in edge
// middleware behind a TLS-terminating proxy is unreliable, so instead read
// whichever cookie the browser actually sent: try the secure name first, then the
// bare one. `secureCookie` cascades to both `cookieName` and `salt` in
// next-auth's getToken, so passing it alone selects the matching name+salt; a
// forged or stale cookie still fails signature/expiry inside decode.
const SESSION_COOKIE_VARIANTS = [
  { name: '__Secure-authjs.session-token', secureCookie: true },
  { name: 'authjs.session-token', secureCookie: false },
] as const;

async function readSessionToken(request: NextRequest) {
  const secret = process.env.NEXTAUTH_SECRET;
  const cookieHeader = request.headers.get('cookie') ?? '';
  for (const { name, secureCookie } of SESSION_COOKIE_VARIANTS) {
    // Only attempt a variant whose cookie is actually present, so the common
    // case is a single decode.
    if (!cookieHeader.includes(`${name}=`)) continue;
    const token = await getToken({ req: request, secret, secureCookie });
    if (token) return token;
  }
  return null;
}

export default async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Public auth flow (sign-in/out, error pages, NextAuth endpoints) — always allowed.
  if (pathname.startsWith('/auth/') || pathname.startsWith('/api/auth/')) {
    return NextResponse.next();
  }

  // Terms and Privacy Policy (issue #473). These are read before anyone has an
  // account — by prospective customers, by Stripe's reviewers, and by regulators
  // — so they cannot sit behind the session wall. The trailing slash keeps the
  // exemption to the /legal subtree: a future /legality page stays protected.
  if (pathname.startsWith('/legal/')) {
    return NextResponse.next();
  }

  // API routes are guarded by their own handlers (which return 401 JSON on missing
  // sessions), not by page-redirect middleware. Let them through untouched.
  if (pathname.startsWith('/api/')) {
    return NextResponse.next();
  }

  // Deny-by-default for pages: every page requires a valid session unless explicitly
  // public above. New pages are protected automatically — there is no allowlist to
  // keep in sync, which is the drift that left /admin, /settings/api, /predict, etc.
  // exposed under the old opt-in allowlist. Verify the Auth.js JWT (signature +
  // expiry), not just cookie presence, so a stale or forged session-token cookie
  // cannot serve a protected page.
  const token = await readSessionToken(request);

  if (!token) {
    const signInUrl = new URL('/auth/signin', request.url);
    signInUrl.searchParams.set('callbackUrl', pathname);
    return NextResponse.redirect(signInUrl);
  }

  // Authentication is not authorization (issue #477). /admin is for emails on
  // ADMIN_EMAILS only, decided here on the server — a client-side check would
  // hide the UI, not the data. A non-admin gets the same answer as for a page
  // that does not exist (rewrite to Next's not-found route → 404), so the route
  // is not an existence oracle. The trailing-slash form keeps `/administration`
  // an ordinary protected page.
  if (pathname === '/admin' || pathname.startsWith('/admin/')) {
    if (!isAdminEmail(typeof token.email === 'string' ? token.email : null)) {
      return NextResponse.rewrite(new URL('/_not-found', request.url));
    }
  }

  // Authenticated page request — apply CORS handling. Never reflect an arbitrary
  // Origin (that is CSRF-friendly): echo the caller's Origin only when it is on
  // the configured allowlist, otherwise omit Access-Control-Allow-Origin so the
  // browser blocks the cross-origin read. Same-origin requests need no ACAO.
  const allowlist = (process.env.ALLOWED_ORIGINS ?? '')
    .split(',')
    .map((o) => o.trim())
    .filter(Boolean);
  const requestOrigin = request.headers.get('origin');
  const allowedOrigin =
    requestOrigin && allowlist.includes(requestOrigin) ? requestOrigin : null;

  const corsHeaders: Record<string, string> = {
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, Accept',
    'Access-Control-Max-Age': '86400',
    // The response's ACAO depends on the request Origin (present, absent, or a
    // specific allowlisted value). Behind a shared cache/CDN (nginx), Vary:
    // Origin prevents one origin's cached CORS result being replayed for another.
    Vary: 'Origin',
  };
  if (allowedOrigin) {
    corsHeaders['Access-Control-Allow-Origin'] = allowedOrigin;
  }

  if (request.method === 'OPTIONS') {
    return new NextResponse(null, { status: 204, headers: corsHeaders });
  }

  const response = NextResponse.next();
  for (const [key, value] of Object.entries(corsHeaders)) {
    response.headers.set(key, value);
  }

  return response;
}

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
};
