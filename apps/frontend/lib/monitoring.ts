import type { UsageStats } from '@/lib/services/production'

export type MonitoredModel = UsageStats['models'][number]

/** Rows shown before "Show more" on the model list. */
export const MODEL_PAGE_SIZE = 10

const NO_VALUE = '—'

/** Latency means nothing without predictions, so 0 predictions shows a dash, not "<1ms". */
export function formatLatency(ms: number, predictions: number): string {
  if (predictions <= 0) return NO_VALUE
  if (ms < 1) return '<1ms'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

const LATENCY_VERDICTS = [
  { below: 100, label: 'Excellent Performance', className: 'bg-success text-success-foreground' },
  { below: 500, label: 'Good Performance', className: 'bg-primary' },
  { below: Infinity, label: 'Consider Optimization', className: 'bg-warning text-warning-foreground' },
]

/** How fast the model answers; nothing to judge before its first prediction (#1188). */
export function latencyVerdict(ms: number, predictions: number) {
  if (predictions <= 0) return undefined
  return LATENCY_VERDICTS.find((verdict) => ms < verdict.below)
}

/** Models that answered at least one prediction in the window. */
export function modelsWithPredictions(models: MonitoredModel[]): MonitoredModel[] {
  return models.filter((m) => m.predictions_24h > 0)
}

/** Prediction-weighted mean latency; the dash when nothing was predicted. */
export function averageLatencyText(models: MonitoredModel[]): string {
  const total = models.reduce((sum, m) => sum + m.predictions_24h, 0)
  const weighted = models.reduce((sum, m) => sum + m.avg_latency_ms * m.predictions_24h, 0)
  return formatLatency(weighted / (total || 1), total)
}

/** "churn · XGBoost": what the model predicts and how; the stored name for old rows. */
export function modelTitle(model: MonitoredModel): string {
  if (!model.target_column) return model.name
  return model.algorithm ? `${model.target_column} · ${model.algorithm}` : model.target_column
}

/** "customers.csv · 8 Nov 2026"; the dataset part is dropped when the dataset is gone. */
export function modelSubtitle(model: MonitoredModel): string {
  const date = model.created_at ? new Date(model.created_at).toLocaleDateString() : ''
  return [model.dataset_name, date].filter(Boolean).join(' · ')
}
