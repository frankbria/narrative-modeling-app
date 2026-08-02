'use client'

import React, { useMemo } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import type { ModelEvaluationSummary } from '@/lib/types/evaluation'

export interface ModelComparisonTableProps {
  models: ModelEvaluationSummary[]
}

/** Metrics where a smaller value wins; everything else is higher-is-better. */
const LOWER_IS_BETTER = new Set(['mae', 'mse', 'rmse', 'log_loss'])

export function isLowerBetter(metric: string): boolean {
  return LOWER_IS_BETTER.has(metric)
}

/** Index of the best value in a row, honoring the metric's direction. */
export function bestValueIndex(metric: string, values: Array<number | null>): number {
  let best = -1
  values.forEach((value, index) => {
    if (value === null) return
    if (best === -1) {
      best = index
      return
    }
    const current = values[best] as number
    if (isLowerBetter(metric) ? value < current : value > current) {
      best = index
    }
  })
  return best
}

/**
 * Side-by-side model comparison (issue #79): metrics as rows, models as
 * columns, with the best value per row highlighted.
 */
export function ModelComparisonTable({ models }: ModelComparisonTableProps) {
  const metricRows = useMemo(() => {
    const keys = new Set<string>(['cv_score', 'test_score'])
    models.forEach((model) => {
      Object.keys(model.metrics).forEach((key) => keys.add(key))
    })
    return Array.from(keys)
  }, [models])

  if (models.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 bg-muted rounded-lg border border-border">
        <p className="text-muted-foreground">No models to compare</p>
      </div>
    )
  }

  const valueFor = (model: ModelEvaluationSummary, metric: string): number | null => {
    if (metric === 'cv_score') return model.cv_score
    if (metric === 'test_score') return model.test_score
    return model.metrics[metric] ?? null
  }

  const formatMetricName = (metric: string): string =>
    metric.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Metric</TableHead>
          {models.map((model) => (
            <TableHead key={model.model_id}>
              <div className="font-semibold text-foreground">{model.name}</div>
              <div className="text-xs font-normal text-muted-foreground">{model.algorithm}</div>
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {metricRows.map((metric) => {
          const values = models.map((model) => valueFor(model, metric))
          const bestIndex = bestValueIndex(metric, values)
          return (
            <TableRow key={metric}>
              <TableCell className="font-medium">
                {formatMetricName(metric)}
                {isLowerBetter(metric) && (
                  <span className="ml-1 text-xs text-gray-400">(lower is better)</span>
                )}
              </TableCell>
              {models.map((model, index) => {
                const value = values[index]
                const isBest = index === bestIndex && value !== null
                return (
                  <TableCell
                    key={model.model_id}
                    data-testid={`cell-${metric}-${model.model_id}`}
                    data-best={isBest ? 'true' : 'false'}
                    className={isBest ? 'text-green-600 font-semibold' : undefined}
                  >
                    {value === null ? (
                      '—'
                    ) : (
                      <span className="inline-flex items-center gap-2">
                        {value.toFixed(4)}
                        {isBest && (
                          <Badge className="bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 hover:bg-green-100 dark:hover:bg-green-900/40">
                            Best
                          </Badge>
                        )}
                      </span>
                    )}
                  </TableCell>
                )
              })}
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
