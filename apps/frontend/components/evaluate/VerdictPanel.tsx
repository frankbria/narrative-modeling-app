import { Card, CardContent } from '@/components/ui/card'
import type { Verdict } from '@/components/evaluate/evaluationReading'

const detailLines = (verdict: Verdict): string[] =>
  [verdict.sentence, verdict.baseline, verdict.drivers].filter((line): line is string => line !== null)

/** The first thing Evaluate shows: how good the model is, in one glance (#1168). */
export function VerdictPanel({ verdict }: { verdict: Verdict }) {
  return (
    <Card data-testid="verdict-panel">
      <CardContent className="flex flex-wrap items-center gap-6">
        <div>
          <div className="text-5xl font-bold text-primary">{verdict.headline}</div>
          <div className="text-sm text-muted-foreground">{verdict.caption}</div>
        </div>
        <div className="min-w-60 flex-1 space-y-1 text-foreground">
          {detailLines(verdict).map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
