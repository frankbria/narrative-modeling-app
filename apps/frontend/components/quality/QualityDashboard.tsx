'use client'

import React from 'react'
import { useAsyncData } from '@/lib/hooks/useAsyncData'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { CheckCircle2, AlertCircle, XCircle, Wrench, TrendingUp } from 'lucide-react'
import { LineChart } from '@/components/LineChart'
import { QualityService } from '@/lib/services/quality'
import type {
} from '@/lib/types/quality'

interface QualityDashboardProps {
  /** UserData file id — drives the consolidated report endpoint. */
  fileId: string
  /** DatasetMetadata id — drives the trend endpoint (best-effort). */
  datasetId?: string
}

function scoreLabel(score: number): { label: string; color: string } {
  if (score >= 90) return { label: 'Excellent', color: 'text-green-600' }
  if (score >= 70) return { label: 'Good', color: 'text-green-600' }
  if (score >= 50) return { label: 'Fair', color: 'text-yellow-600' }
  return { label: 'Poor', color: 'text-red-600' }
}

const severityColor: Record<string, string> = {
  high: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200',
  medium: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200',
  low: 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200',
}

export function QualityDashboard({ fileId, datasetId }: QualityDashboardProps) {

  const {
    data: report,
    loading,
    error,
  } = useAsyncData(() => QualityService.getQualityReport(fileId), [fileId], {
    errorMessage: undefined,
  })

  // Best-effort: a dataset without versions just hides the chart, so failures are
  // swallowed rather than surfaced. Re-keying on datasetId also replaces the old
  // explicit `setTrend(null)`, which existed to stop the previous dataset's trend
  // rendering during a load — `data` is simply undefined until this key resolves.
  const { data: trend } = useAsyncData(
    () => QualityService.getQualityTrend(datasetId!).catch(() => null),
    [datasetId],
    { enabled: !!datasetId },
  )

  if (loading) {
    return <div data-testid="quality-dashboard-loading" className="text-sm text-muted-foreground">Loading quality report…</div>
  }

  if (error || !report) {
    return (
      <Alert variant="destructive" data-testid="quality-dashboard-error">
        <XCircle className="h-4 w-4" />
        <AlertTitle>Quality report unavailable</AlertTitle>
        <AlertDescription>{error || 'No quality data for this dataset yet.'}</AlertDescription>
      </Alert>
    )
  }

  const { label, color } = scoreLabel(report.score_0_100)
  // Only plot points with a real post-transformation score (the field is nullable).
  const trendPoints = (trend?.points ?? []).filter((p) => p.score_after != null)

  return (
    <div className="space-y-4" data-testid="quality-dashboard">
      {/* Overall 0-100 score */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            ML-Readiness Score
            <span className={`text-3xl font-bold ${color}`} data-testid="quality-score">
              {report.score_0_100.toFixed(1)}
            </span>
          </CardTitle>
          <CardDescription>
            <span className={color}>{label}</span> · {report.critical_issue_count} critical, {report.warning_count} warnings
            {report.partial && ' · partial (legacy report)'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Progress value={report.score_0_100} className="h-2" />
        </CardContent>
      </Card>

      {/* Quality gates */}
      {report.gates.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Quality Gates</CardTitle>
            <CardDescription>Advisory only — gates never block your workflow.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {report.gates.map((gate) => (
              <div key={gate.gate_name} className="flex items-center justify-between" data-testid="quality-gate">
                <div className="flex items-center gap-2">
                  {gate.passed ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-yellow-600" />
                  )}
                  <span className="text-sm font-medium">{gate.gate_name}</span>
                </div>
                <div className="text-sm text-muted-foreground">
                  {gate.passed ? 'Passed' : `Needs ${gate.required_score} (now ${gate.actual_score.toFixed(0)})`}
                  {gate.failing_dimensions.length > 0 && ` · ${gate.failing_dimensions.join(', ')}`}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Component scores */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Component Scores</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {Object.entries(report.component_scores).map(([dim, value]) => (
            <div key={dim} data-testid={`component-${dim}`}>
              <div className="mb-1 flex justify-between text-sm">
                <span className="capitalize">{dim}</span>
                <span>{value.toFixed(1)}</span>
              </div>
              <Progress value={value} className="h-1.5" />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Actionable recommendations */}
      {report.actionable_recommendations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Wrench className="h-4 w-4" /> Recommended Fixes
            </CardTitle>
            <CardDescription>Each maps to a transformation you can apply.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {report.actionable_recommendations.map((rec, i) => (
              <div key={i} className="flex items-start justify-between gap-3 rounded border p-2" data-testid="recommendation">
                <div className="text-sm">{rec.description}</div>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge className={severityColor[rec.severity] || ''}>{rec.severity}</Badge>
                  <Badge variant="outline">{rec.transformation_type}</Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Quality trend across versions */}
      {trendPoints.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4" /> Quality Trend
            </CardTitle>
            <CardDescription>
              Score after each transformation
              {trend?.overall_improvement != null && ` · ${trend.overall_improvement > 0 ? '+' : ''}${trend.overall_improvement} overall`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <LineChart
              height={280}
              data={{
                data: trendPoints.map((p, i) => ({
                  x: p.version_number != null ? `v${p.version_number}` : `step ${i + 1}`,
                  score: p.score_after as number,
                })),
                lines: [{ dataKey: 'score', label: 'Quality Score', color: '#82ca9d' }],
                xLabel: 'Version',
                yLabel: 'Score (0-100)',
              }}
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
