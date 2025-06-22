// frontend/app/middleware.ts

// Middleware cannot use @/auth or any server-only code. If you need authentication, use only cookies or headers, or move logic to API routes.

// If you need a placeholder, you can export a no-op middleware:
import { NextResponse } from 'next/server';

export function middleware() {
  return NextResponse.next();
}
