// ./middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

export default async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Public auth flow (sign-in/out, error pages, NextAuth endpoints) — always allowed.
  if (pathname.startsWith('/auth/') || pathname.startsWith('/api/auth/')) {
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
  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });

  if (!token) {
    const signInUrl = new URL('/auth/signin', request.url);
    signInUrl.searchParams.set('callbackUrl', pathname);
    return NextResponse.redirect(signInUrl);
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
