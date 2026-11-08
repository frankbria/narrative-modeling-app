/**
 * Plain-language readings of an evaluation (#1168, #1171): every sentence the
 * Evaluate page and its charts say about the numbers is built here, from the
 * response alone.
 */
import type { ReactNode } from 'react'
import {
  isClassificationMetrics,
  type ConfusionMatrixData,
  type ModelEvaluationResponse,
  type PRCurveData,
  type ShapSummaryResponse,
  type ROCCurveData
} from '@/lib/types/evaluation'

export interface MetricRow {
  label: string
  value: string
  explanation: string
}

export interface Verdict {
  headline: string
  caption: string
  sentence: string
  baseline: string | null
  drivers: string | null
}

const MAX_DRIVERS = 3

export const percent = (value: number): string => `${Math.round(value * 100)}%`

const words = (name: string): string => name.replace(/_/g, ' ')

const joinWords = (items: string[]): string =>
  items.length < 2 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`

/** Share of rows a model that always answers the most common class would get right. */
export function majorityBaseline(matrix: number[][]): number | null {
  const supports = matrix.map((counts) => counts.reduce((sum, count) => sum + count, 0))
  const total = supports.reduce((sum, count) => sum + count, 0)
  return total > 0 ? Math.max(...supports) / total : null
}

export function topDrivers(importance: Record<string, number> | null): string | null {
  const names = Object.entries(importance ?? {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, MAX_DRIVERS)
    .map(([name]) => words(name))
  return names.length > 0 ? `Mostly driven by ${joinWords(names)}.` : null
}

const baselineLine = (accuracy: number, baseline: number | null): string | null =>
  baseline === null
    ? null
    : `${accuracy > baseline ? 'Beats' : 'Does not beat'} always guessing the most common answer (${percent(baseline)}).`

function classificationVerdict(accuracy: number, baseline: number | null): Omit<Verdict, 'drivers'> {
  return {
    headline: percent(accuracy),
    caption: 'of predictions correct',
    sentence: `Right about ${Math.round(accuracy * 100)} times out of 100 on rows it had never seen.`,
    baseline: baselineLine(accuracy, baseline)
  }
}

function regressionVerdict(r2: number): Omit<Verdict, 'drivers'> {
  return {
    headline: percent(r2),
    caption: 'of the variation explained',
    sentence: `Accounts for ${percent(r2)} of the ups and downs in what you are predicting.`,
    baseline: 'Always guessing the average would explain 0%.'
  }
}

export function buildVerdict(evaluation: ModelEvaluationResponse): Verdict | null {
  const { metrics } = evaluation
  if (!metrics) return null
  const matrix = evaluation.confusion_matrix?.matrix
  const base = isClassificationMetrics(metrics)
    ? classificationVerdict(metrics.accuracy, matrix ? majorityBaseline(matrix) : null)
    : regressionVerdict(metrics.r2)
  return { ...base, drivers: topDrivers(evaluation.feature_importance) }
}

type RowSpec = [key: string, label: string, explanation: string]

const CLASSIFICATION_ROWS: RowSpec[] = [
  ['accuracy', 'Accuracy', 'How often the prediction is right.'],
  ['precision_weighted', 'Precision', 'When it picks an outcome, how often that is correct.'],
  ['recall_weighted', 'Recall', 'Of the rows that really had an outcome, how many it found.'],
  ['f1_weighted', 'Balance (F1)', 'One score that balances precision and recall.'],
  ['roc_auc', 'Ranking ability', 'How well it ranks likely rows above unlikely ones. 50% is a coin flip.']
]

const REGRESSION_ROWS: RowSpec[] = [
  ['r2', 'Variation explained', 'How much of the ups and downs the model captures. 0% is no better than the average.'],
  ['mae', 'Typical miss', 'On average, how far off the prediction is, in the units of your column.'],
  ['rmse', 'Miss, big errors weighted', 'Like the typical miss, but large mistakes count more.']
]

const decimals = (value: number): string => value.toFixed(2)

const FORMATTERS: Record<string, (value: number) => string> = {
  accuracy: percent,
  precision_weighted: percent,
  recall_weighted: percent,
  f1_weighted: percent,
  roc_auc: percent,
  r2: percent,
  mae: decimals,
  rmse: decimals
}

export function metricRows(evaluation: ModelEvaluationResponse): MetricRow[] {
  const { metrics } = evaluation
  if (!metrics) return []
  const specs = isClassificationMetrics(metrics) ? CLASSIFICATION_ROWS : REGRESSION_ROWS
  const values = metrics as unknown as Record<string, number | null>
  return specs
    .filter(([key]) => typeof values[key] === 'number')
    .map(([key, label, explanation]) => ({
      label,
      value: FORMATTERS[key](values[key] as number),
      explanation
    }))
}

/** The class the model missed most often, as one sentence. */
export function confusionReading(data: ConfusionMatrixData): string | null {
  const rows = data.matrix
    .map((counts, i) => {
      const total = counts.reduce((sum, count) => sum + count, 0)
      return { label: data.labels[i], total, missed: total - counts[i] }
    })
    .filter((r) => r.total > 0)
    .sort((a, b) => b.missed / b.total - a.missed / a.total)
  const [worst] = rows
  return worst
    ? `Of ${worst.total} rows that really were "${worst.label}", the model missed ${worst.missed}.`
    : null
}

export function rocReading(data: ROCCurveData): string | null {
  return data.macro_auc === null
    ? null
    : `A curve hugging the top-left corner is best. On average the model ranks a true case above a false one ${percent(data.macro_auc)} of the time (50% is a coin flip).`
}

export function prReading(data: PRCurveData): string | null {
  const [first] = Object.entries(data.baseline_per_class)
  return first
    ? `The higher the curve stays, the fewer false alarms as it finds more cases. Picking at random would give about ${percent(first[1])} precision for "${first[0]}".`
    : null
}

/** Renders `render(value)` only when `value` is truthy; keeps branches out of JSX components. */
export const when = <T,>(value: T, render: (present: NonNullable<T>) => ReactNode): ReactNode =>
  value ? render(value as NonNullable<T>) : null

export interface TabFlags {
  confusion: ConfusionMatrixData | null
  curves: boolean
}

export function tabFlags(evaluation: ModelEvaluationResponse): TabFlags {
  const classification = evaluation.metrics !== null && isClassificationMetrics(evaluation.metrics)
  return {
    confusion: classification ? evaluation.confusion_matrix : null,
    curves: classification && (evaluation.roc_curve !== null || evaluation.pr_curve !== null)
  }
}

/** The SHAP summary, only when it has something to draw. */
export function shapToShow(shap: ShapSummaryResponse | null | undefined): ShapSummaryResponse | null {
  return shap && !shap.partial && shap.feature_importance.length > 0 ? shap : null
}

/** Feature importances scaled so the strongest is 1, ranked. */
export function featureScores(importance: Record<string, number> | null) {
  const entries = Object.entries(importance ?? {}).sort(([, a], [, b]) => b - a)
  const max = entries.length > 0 ? entries[0][1] : 0
  return entries.map(([name, value], index) => ({
    feature_name: name,
    score: max > 0 ? value / max : 0,
    rank: index + 1,
    selected: true
  }))
}

export const modelTitle = (evaluation: ModelEvaluationResponse): string =>
  evaluation.model_name ?? evaluation.model_id
