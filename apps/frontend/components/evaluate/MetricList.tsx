import type { MetricRow } from '@/components/evaluate/evaluationReading'

/** Metrics as readable percentages, each with what it means (#1168). */
export function MetricList({ rows }: { rows: MetricRow[] }) {
  return (
    <dl className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {rows.map(({ label, value, explanation }) => (
        <div key={label} className="rounded-lg bg-muted p-4">
          <dt className="text-sm text-muted-foreground">{label}</dt>
          <dd className="text-2xl font-bold text-foreground">{value}</dd>
          <dd className="mt-1 text-sm text-muted-foreground">{explanation}</dd>
        </div>
      ))}
    </dl>
  )
}
