import { NextResponse } from 'next/server'

// Answered per request: the environment is this container's, never the build's (#831).
export const dynamic = 'force-dynamic'

export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    environment: process.env.ENVIRONMENT || 'development',
  })
}