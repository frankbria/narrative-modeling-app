import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import type { ClerkMiddlewareAuth } from "@clerk/nextjs/server";

// Create a custom middleware that combines Clerk auth and CORS
function customMiddleware(auth: ClerkMiddlewareAuth, request: NextRequest) {
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

  // Continue to the next middleware (Clerk auth)
  const response = NextResponse.next()

  // Add CORS headers to the response
  response.headers.set('Access-Control-Allow-Origin', origin)
  response.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
  response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept')
  response.headers.set('Access-Control-Max-Age', '86400')

  return response
}

// Combine our custom middleware with Clerk's middleware
export default clerkMiddleware(customMiddleware);

export const config = {
  matcher: [
    // Skip Next.js internals and all static files, unless found in search params
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|docx?|xlsx?|zip|webmanifest)).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
};