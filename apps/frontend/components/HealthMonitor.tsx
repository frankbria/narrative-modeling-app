'use client'

import { publicEnv } from '@/lib/runtimeEnv'
import { HugeiconsIcon } from '@/components/ui/icon'
import { Activity01Icon, AlertCircleIcon, CheckmarkCircle02Icon, Clock01Icon, ServerStack01Icon, WifiOff01Icon } from '@hugeicons/core-free-icons'
import { useEffect, type ReactNode } from 'react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAsyncData } from '@/lib/hooks/useAsyncData'

/**
 * Backend health widget (#479).
 *
 * It used to poll `/health/status` and `/health/metrics`, neither of which
 * exists, so every poll 404'd and the panel read "Unhealthy" forever — an
 * always-red light trains you to ignore the one signal that matters. The real
 * FastAPI table has `/health` (liveness) and `/health/ready` (dependency
 * readiness); this app also mounts the *liveness* one under `/api/v1` (#479) so
 * the browser reaches it through the same nginx `/api/` proxy as every other
 * call — `/health/ready` stays root-only because it is expensive (#503). No
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

type HealthState = 'loading' | 'unreachable' | 'erroring' | 'alive'

const STATE_ICONS: Record<HealthState, ReactNode> = {
  loading: <HugeiconsIcon icon={Activity01Icon} className="h-5 w-5 animate-pulse" data-testid="health-icon-loading" />,
  unreachable: <HugeiconsIcon icon={WifiOff01Icon} className="h-5 w-5 text-destructive" data-testid="health-icon-unreachable" />,
  erroring: <HugeiconsIcon icon={AlertCircleIcon} className="h-5 w-5 text-warning" data-testid="health-icon-erroring" />,
  alive: <HugeiconsIcon icon={CheckmarkCircle02Icon} className="h-5 w-5 text-success" data-testid="health-icon-alive" />,
}

const STATE_LABELS: Record<HealthState, string> = {
  loading: 'Checking…',
  unreachable: 'Cannot reach the backend',
  erroring: 'Backend reachable but reporting a problem',
  alive: 'Backend reachable',
}

async function fetchHealth(backendUrl: string): Promise<HealthResult> {
  // A thrown fetch (network/CORS) becomes useAsyncData's `error` → unreachable.
  // A non-2xx is a *reached* backend answering unwell → `liveness: null`, no throw.
  // NEXT_PUBLIC_API_URL already carries /api/v1, which nginx proxies to the
  // backend; health is mounted there too (#479), so append only the path.
  const response = await fetch(`${backendUrl}/health`)
  if (!response.ok) {
    return { liveness: null, lastUpdate: new Date() }
  }
  const liveness: Liveness = await response.json()
  return { liveness, lastUpdate: new Date() }
}

/** Three states: unreachable (fetch threw), reachable-but-erroring (non-2xx, no liveness body), and alive. */
function healthState(loading: boolean, error: string | null | undefined, liveness: Liveness | null | undefined): HealthState {
  if (loading) return 'loading'
  if (error) return 'unreachable'
  return liveness ? 'alive' : 'erroring'
}

function updateTime(lastUpdate: Date | undefined): string {
  return lastUpdate ? lastUpdate.toLocaleTimeString() : '—'
}

export function HealthMonitor(props: HealthMonitorProps) {
  const {
    backendUrl = publicEnv('NEXT_PUBLIC_API_URL') || 'http://localhost:8000/api/v1',
    refreshInterval = 30000,
  } = props
  const { data, loading, error, reload } = useAsyncData(
    () => fetchHealth(backendUrl),
    [backendUrl],
    { errorMessage: 'Cannot reach the backend.' },
  )

  useEffect(() => {
    const interval = setInterval(reload, refreshInterval)
    return () => clearInterval(interval)
  }, [reload, refreshInterval])

  const liveness = data?.liveness
  const state = healthState(loading, error, liveness)
  const icon = STATE_ICONS[state]
  const label = STATE_LABELS[state]

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HugeiconsIcon icon={ServerStack01Icon} className="h-5 w-5" />
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
                  <HugeiconsIcon icon={Clock01Icon} className="h-3 w-3" />
                  {updateTime(data?.lastUpdate)}
                </p>
              </div>
            </div>

            {error && (
              <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-lg">
                <p className="text-sm text-destructive">{error}</p>
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
