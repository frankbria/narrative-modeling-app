'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { modelService } from '@/lib/services/model'
import type {
  ConfusionPair,
  ErrorAnalysisResponse
} from '@/lib/types/evaluation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, AlertTriangle, Lightbulb, Target } from 'lucide-react'

interface ErrorAnalysisDashboardProps {
  modelId: string
}

const pct = (value: number) => `${(value * 100).toFixed(1)}%`

/**
 * Error-analysis dashboard (issue #81). Shows where and why a model fails:
 * error distribution, confusion pairs, high-error segments, error clusters,
 * decision-tree patterns, a browsable error-case table (filterable by clicking
 * a confusion pair), and AI improvement suggestions. Degrades gracefully for
 * `partial` models (no feature matrix → no segments/clusters/patterns).
 */
export function ErrorAnalysisDashboard({ modelId }: ErrorAnalysisDashboardProps) {
  const [analysis, setAnalysis] = useState<ErrorAnalysisResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pairFilter, setPairFilter] = useState<ConfusionPair | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      setAnalysis(await modelService.getErrorAnalysis(modelId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load error analysis')
    } finally {
      setIsLoading(false)
    }
  }, [modelId])

  useEffect(() => {
    void load()
  }, [load])

  const filteredCases = useMemo(() => {
    if (!analysis) return []
    if (!pairFilter) return analysis.cases
    return analysis.cases.filter(
      (c) => c.actual === pairFilter.actual && c.predicted === pairFilter.predicted
    )
  }, [analysis, pairFilter])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12" role="status">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">Analyzing errors…</span>
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription data-testid="error-analysis-error">{error}</AlertDescription>
      </Alert>
    )
  }

  if (!analysis) return null

  const dist = analysis.distribution

  return (
    <div className="space-y-6" data-testid="error-analysis-dashboard">
      {analysis.message && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{analysis.message}</AlertDescription>
        </Alert>
      )}

      {/* Overview cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Errors</CardDescription>
            <CardTitle className="text-2xl">{dist?.total_errors ?? '—'}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Error Rate</CardDescription>
            <CardTitle className="text-2xl">
              {dist ? pct(dist.overall_error_rate) : '—'}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Most Confused</CardDescription>
            <CardTitle className="text-2xl">
              {analysis.confusion_pairs[0]
                ? `${analysis.confusion_pairs[0].actual} → ${analysis.confusion_pairs[0].predicted}`
                : '—'}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* AI suggestions */}
      {analysis.suggestions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5" />
              AI Suggestions
              <Badge variant="outline" className="ml-2 text-xs">
                {analysis.suggestions_generated_by === 'openai' ? 'AI' : 'Rule-based'}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-5 space-y-2 text-sm">
              {analysis.suggestions.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Per-class distribution */}
      {dist && Object.keys(dist.per_class_error_rate).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Error Rate by Class</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.entries(dist.per_class_error_rate)
              .sort((a, b) => b[1] - a[1])
              .map(([label, rate]) => (
                <div key={label} className="flex items-center gap-3">
                  <span className="w-28 text-sm font-mono truncate">{label}</span>
                  <div className="flex-1 bg-muted rounded h-3">
                    <div
                      className="bg-red-500 h-3 rounded"
                      style={{ width: `${Math.min(100, rate * 100)}%` }}
                    />
                  </div>
                  <span className="w-14 text-right text-sm">{pct(rate)}</span>
                </div>
              ))}
          </CardContent>
        </Card>
      )}

      {/* Confusion pairs (clickable to filter cases) */}
      {analysis.confusion_pairs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Commonly Confused Classes</CardTitle>
            <CardDescription>
              Click a pair to filter the error cases below.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {analysis.confusion_pairs.map((p, i) => {
              const active =
                pairFilter?.actual === p.actual && pairFilter?.predicted === p.predicted
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => setPairFilter(active ? null : p)}
                  className={`w-full flex items-center justify-between rounded-lg px-3 py-2 text-sm transition-all ${
                    active ? 'bg-primary/10 ring-[2px] ring-primary' : 'bg-muted/50 hover:bg-muted'
                  }`}
                >
                  <span className="font-mono">
                    {p.actual} → {p.predicted}
                  </span>
                  <span className="text-muted-foreground">
                    {p.count} cases ({pct(p.rate)})
                  </span>
                </button>
              )
            })}
          </CardContent>
        </Card>
      )}

      {/* High-error segments */}
      {analysis.segments.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>High-Error Feature Segments</CardTitle>
            <CardDescription>
              Feature value-ranges where the model fails more often.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {analysis.segments.map((s, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <span className="font-mono">{s.range_label}</span>
                <span>
                  <Badge variant="destructive" className="mr-2">{pct(s.error_rate)}</Badge>
                  <span className="text-muted-foreground">{s.sample_count} samples</span>
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Decision-tree patterns */}
      {analysis.patterns.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5" />
              Error Patterns
            </CardTitle>
            <CardDescription>Feature conditions that isolate errors.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {analysis.patterns.map((p, i) => (
              <div key={i} className="rounded-lg bg-muted/50 px-3 py-2 text-sm">
                <div className="font-mono">{p.rule}</div>
                <div className="text-muted-foreground">
                  {pct(p.error_rate)} error rate · {p.error_count}/{p.sample_count} samples
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Clusters */}
      {analysis.clusters.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Error Clusters</CardTitle>
            <CardDescription>Groups of similar error cases.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {analysis.clusters.map((c) => (
              <div key={c.cluster_id} className="flex items-center justify-between text-sm">
                <span>
                  Cluster {c.cluster_id + 1}
                  {c.characteristics.length > 0 && (
                    <span className="text-muted-foreground"> — {c.characteristics.join(', ')}</span>
                  )}
                  {c.dominant_confusion && (
                    <span className="font-mono text-muted-foreground"> ({c.dominant_confusion})</span>
                  )}
                </span>
                <Badge variant="outline">{c.size}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Error case browser */}
      {analysis.cases.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Error Cases</span>
              {pairFilter && (
                <button
                  type="button"
                  onClick={() => setPairFilter(null)}
                  className="text-sm font-normal text-primary underline"
                >
                  Clear filter ({pairFilter.actual} → {pairFilter.predicted})
                </button>
              )}
            </CardTitle>
            <CardDescription>{filteredCases.length} cases shown</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground border-b">
                    <th className="py-2 pr-4">#</th>
                    <th className="py-2 pr-4">Actual</th>
                    <th className="py-2 pr-4">Predicted</th>
                    <th className="py-2 pr-4">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCases.map((c) => (
                    <tr key={c.index} className="border-b last:border-0">
                      <td className="py-2 pr-4 font-mono">{c.index}</td>
                      <td className="py-2 pr-4 font-mono">{c.actual}</td>
                      <td className="py-2 pr-4 font-mono">{c.predicted}</td>
                      <td className="py-2 pr-4">
                        {c.confidence != null ? pct(c.confidence) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
