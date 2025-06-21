import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { auth } from "@/app/auth";

export default async function middleware(request: NextRequest) {
  // Get the origin from the request headers
  const origin = request.headers.get('origin') || '*'

  // Handle preflight requests
  if (request.method === 'OPTIONS') {
    return new NextResponse(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': origin,
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, Accept',
        'Access-Control-Max-Age': '86400',
      },
    })
  }

  // Skip auth check if SKIP_AUTH is enabled
  const skipAuth = process.env.SKIP_AUTH === 'true';
  
  if (!skipAuth) {
    // Check authentication for protected routes
    const session = await auth();
    const isAuthPage = request.nextUrl.pathname.startsWith('/auth');
    const isPublicPage = request.nextUrl.pathname === '/' || isAuthPage;

    if (!session && !isPublicPage) {
      return NextResponse.redirect(new URL('/auth/signin', request.url));
    }

    if (session && isAuthPage) {
      return NextResponse.redirect(new URL('/', request.url));
    }
  }

  // Continue to the route
  const response = NextResponse.next()

  // Add CORS headers to the response
  response.headers.set('Access-Control-Allow-Origin', origin)
  response.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
  response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept')
  response.headers.set('Access-Control-Max-Age', '86400')

  return response
}

export const config = {
  matcher: [
    // Skip Next.js internals and all static files, unless found in search params
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|docx?|xlsx?|zip|webmanifest)).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
};