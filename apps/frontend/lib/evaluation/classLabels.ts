import type {
  ClassificationMetrics,
  ConfusionMatrixData,
  ModelEvaluationResponse,
  PRCurveData,
  RegressionMetrics,
  ROCCurveData,
} from '@/lib/types/evaluation'

const BARE_CLASS = /^(-?\d+(\.\d+)?|true|false)$/i

/** A class as an analyst reads it: a bare number or boolean is named against its target, e.g. `churned = 1` (#1187). */
export function classLabel(label: string, target: string | null | undefined): string {
  return target && BARE_CLASS.test(label) ? `${target} = ${label}` : label
}

const renameKeys = <T>(record: Record<string, T>, target: string | null | undefined) =>
  Object.fromEntries(Object.entries(record).map(([label, value]) => [classLabel(label, target), value]))

const nameConfusion = (confusion: ConfusionMatrixData | null, target: string | null | undefined) =>
  confusion && { ...confusion, labels: confusion.labels.map((label) => classLabel(label, target)) }

const nameRoc = (roc: ROCCurveData | null, target: string | null | undefined) =>
  roc && { ...roc, curves: renameKeys(roc.curves, target), auc_per_class: renameKeys(roc.auc_per_class, target) }

const namePr = (pr: PRCurveData | null, target: string | null | undefined) =>
  pr && { ...pr, curves: renameKeys(pr.curves, target), baseline_per_class: renameKeys(pr.baseline_per_class, target) }

function nameMetrics(metrics: ClassificationMetrics | RegressionMetrics | null, target: string | null | undefined) {
  if (!metrics || !('per_class_metrics' in metrics)) return metrics
  return { ...metrics, per_class_metrics: renameKeys(metrics.per_class_metrics, target) }
}

/** The evaluation with every class-keyed field named the same way, so the charts and tables agree. */
export function nameEvaluationClasses(evaluation: ModelEvaluationResponse): ModelEvaluationResponse {
  const target = evaluation.target_column
  return {
    ...evaluation,
    metrics: nameMetrics(evaluation.metrics, target),
    confusion_matrix: nameConfusion(evaluation.confusion_matrix, target),
    roc_curve: nameRoc(evaluation.roc_curve, target),
    pr_curve: namePr(evaluation.pr_curve, target),
  }
}
