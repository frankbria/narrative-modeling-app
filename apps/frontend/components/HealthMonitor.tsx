'use client'

import { Activity, AlertCircle, CheckCircle2, Clock, Server, WifiOff } from 'lucide-react'
import { useEffect } from 'react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAsyncData } from '@/lib/hooks/useAsyncData'

/**
 * Backend health widget (#479).
 *
 * It used to poll `/health/status` and `/health/metrics`, neither of which
 * exists, so every poll 404'd and the panel read "Unhealthy" forever — an
 * always-red light trains you to ignore the one signal that matters. The real
 * FastAPI table has `/health` (liveness) and `/health/ready` (dependency
 * readiness); this app also mounts them under `/api/v1` (#479) so the browser
 * reaches liveness through the same nginx `/api/` proxy as every other call. No
 * metrics endpoint (real metrics are #488), so the fabricated grid is gone.
 *
 * We poll the cheap liveness probe. `/health/ready` would answer the richer
 * "are the dependencies up" question, but it does an outbound OpenAI call and a
 * blocking head_bucket on every request (#503), so pointing a 30s poller at it
 * would make that worse — once #503 removes that per-request work, this can add
 * a readiness tier. Three distinct outcomes (#479 AC3): reachable-and-alive,
 * reachable-but-erroring (a non-2xx: the process answered unwell), and
 * unreachable (the fetch threw: network/CORS/DNS) — "can't reach it" and "it
 * says it's unwell" are different facts.
 */

interface Liveness {
  status: string
  environment: string
  version: string
}

interface HealthResult {
  liveness: Liveness | null
  lastUpdate: Date
}

interface HealthMonitorProps {
  backendUrl?: string
  refreshInterval?: number
}

export function HealthMonitor({
  backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  refreshInterval = 30000,
}: HealthMonitorProps) {
  const { data, loading, error, reload } = useAsyncData(
    async (): Promise<HealthResult> => {
      // A thrown fetch (network/CORS) becomes useAsyncData's `error` → unreachable.
      // A non-2xx is a *reached* backend answering unwell → reachable:false but no throw.
      // NEXT_PUBLIC_API_URL already carries /api/v1, which nginx proxies to the
      // backend; health is mounted there too (#479), so append only the path.
      const response = await fetch(`${backendUrl}/health`)
      if (!response.ok) {
        return { liveness: null, lastUpdate: new Date() }
      }
      const liveness: Liveness = await response.json()
      return { liveness, lastUpdate: new Date() }
    },
    [backendUrl],
    { errorMessage: 'Cannot reach the backend.' },
  )

  useEffect(() => {
    const interval = setInterval(reload, refreshInterval)
    return () => clearInterval(interval)
  }, [reload, refreshInterval])

  const liveness = data?.liveness ?? null
  const lastUpdate = data?.lastUpdate ?? null
  // Three states: unreachable (fetch threw), reachable-but-erroring (non-2xx,
  // no liveness body), and alive.
  const state: 'loading' | 'unreachable' | 'erroring' | 'alive' = loading
    ? 'loading'
    : error
      ? 'unreachable'
      : liveness
        ? 'alive'
        : 'erroring'

  const icon = {
    loading: <Activity className="h-5 w-5 animate-pulse" data-testid="health-icon-loading" />,
    unreachable: <WifiOff className="h-5 w-5 text-red-500" data-testid="health-icon-unreachable" />,
    erroring: <AlertCircle className="h-5 w-5 text-yellow-500" data-testid="health-icon-erroring" />,
    alive: <CheckCircle2 className="h-5 w-5 text-green-500" data-testid="health-icon-alive" />,
  }[state]

  const label = {
    loading: 'Checking…',
    unreachable: 'Cannot reach the backend',
    erroring: 'Backend reachable but reporting a problem',
    alive: 'Backend reachable',
  }[state]

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            System Health Monitor
          </CardTitle>
          <CardDescription>Liveness of the backend, polled from /health</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
              <div className="flex items-center gap-3">
                {icon}
                <div>
                  <p className="font-medium">System Status</p>
                  <p className="text-sm text-muted-foreground" data-testid="health-status-text">
                    {label}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Last Update</p>
                <p className="text-sm font-medium flex items-center justify-end gap-1">
                  <Clock className="h-3 w-3" />
                  {lastUpdate ? lastUpdate.toLocaleTimeString() : '—'}
                </p>
              </div>
            </div>

            {error && (
              <div className="p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg">
                <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
              </div>
            )}

            {liveness && (
              <div className="text-sm text-muted-foreground flex justify-between pt-2">
                <span>Environment: {liveness.environment}</span>
                <span>Version: {liveness.version}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
