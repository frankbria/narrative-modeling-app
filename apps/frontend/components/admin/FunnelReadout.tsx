'use client'

import { useAsyncData } from '@/lib/hooks/useAsyncData'
import { getFunnel } from '@/lib/services/admin'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const DAYS = 30

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-2xl font-semibold tabular-nums">{value}</dd>
    </div>
  )
}

/** Launch funnel as numbers (#769 AC2): signups → activation → 402s → checkout. */
export function FunnelReadout() {
  const { data, loading, error } = useAsyncData(() => getFunnel(DAYS), [])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Funnel</CardTitle>
        <CardDescription>Last {DAYS} days</CardDescription>
      </CardHeader>
      <CardContent>
        {loading && <p className="text-muted-foreground">Loading…</p>}
        {error && <p className="text-destructive">{error}</p>}
        {data && (
          <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label="Signups" value={data.signups} />
            <Stat
              label="Activated within 7 days"
              value={
                data.activation.rate === null
                  ? '—'
                  : `${data.activation.activated} / ${data.activation.cohort} (${Math.round(data.activation.rate * 100)}%)`
              }
            />
            <Stat label="Checkouts started" value={data.checkout_started} />
            <Stat label="Checkouts completed" value={data.checkout_completed} />
            <Stat label="Subscriptions cancelled" value={data.subscriptions_cancelled} />
            {Object.entries(data.quota_denials_by_metric).map(([metric, n]) => (
              <Stat key={metric} label={`402s: ${metric}`} value={n} />
            ))}
          </dl>
        )}
        {data && data.signups_per_day.length > 0 && (
          <div className="mt-6">
            <h3 className="mb-2 text-sm font-medium">Signups per day</h3>
            <ul className="grid grid-cols-2 gap-x-6 text-sm tabular-nums md:grid-cols-4">
              {data.signups_per_day.map((d) => (
                <li key={d.date}>
                  {d.date}: {d.count}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
