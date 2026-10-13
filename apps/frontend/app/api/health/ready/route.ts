import { NextResponse } from 'next/server'
import { readiness } from '@/lib/health/readiness'

// Asked on every call, never cached or prerendered: the answer is the state of this
// container's credentials right now.
export const dynamic = 'force-dynamic'

/**
 * Readiness of what the frontend shares with the backend (#756): 200 when its Mongo
 * credential connects and the backend accepts a token signed with its NEXTAUTH_SECRET,
 * 503 with the failing check otherwise.
 *
 * Not reachable from the internet: the edge sends every `/api/health*` path to the
 * backend, so this answers only on the container's own port, where
 * `scripts/deploy/frontend_probe.sh` asks it. It opens a database connection per
 * call, which is why it must stay that way.
 */
export async function GET() {
  const report = await readiness()
  return NextResponse.json(report, { status: report.status === 'healthy' ? 200 : 503 })
}
