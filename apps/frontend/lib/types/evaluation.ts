/**
 * Types for the model evaluation dashboard (issue #79).
 *
 * Contract shared with the backend: apps/backend/app/schemas/evaluation.py
 * mirrors these interfaces field-for-field. Change both together.
 */

export interface PerClassMetrics {
  precision: number
  recall: number
  f1: number
  support: number
}

export interface ClassificationMetrics {
  accuracy: number
  precision_macro: number
  precision_weighted: number
  recall_macro: number
  recall_weighted: number
  f1_macro: number
  f1_weighted: number
  roc_auc: number | null
  log_loss: number | null
  per_class_metrics: Record<string, PerClassMetrics>
}

export interface RegressionMetrics {
  mae: number
  mse: number
  rmse: number
  r2: number
  mape: number | null
}

export interface ConfusionMatrixData {
  labels: string[]
  /** matrix[i][j] = count of actual labels[i] predicted as labels[j] */
  matrix: number[][]
}

export interface CurvePoint {
  x: number
  y: number
  threshold?: number | null
}

export interface ROCCurveData {
  /** Per-class ROC curves (one-vs-rest for multiclass). x=FPR, y=TPR. */
  curves: Record<string, CurvePoint[]>
  auc_per_class: Record<string, number>
  macro_auc: number | null
}

export interface PRCurveData {
  /** Per-class precision-recall curves. x=recall, y=precision. */
  curves: Record<string, CurvePoint[]>
  /** Positive-class prevalence per class (random-classifier baseline) */
  baseline_per_class: Record<string, number>
}

export interface AIExplanation {
  overall_assessment: string
  metric_explanations: Record<string, string>
  strengths: string[]
  concerns: string[]
  recommendations: string[]
  generated_by: 'openai' | 'fallback'
}

export interface ModelEvaluationResponse {
  model_id: string
  model_name: string | null
  algorithm: string | null
  problem_type: string
  /**
   * True when evaluation artifacts are unavailable (models trained before
   * issue #79) and only stored scalar metrics are returned.
   */
  partial: boolean
  metrics: ClassificationMetrics | RegressionMetrics | null
  /** Scalar metrics persisted at training time (cv_score, test_score, ...) */
  stored_metrics: Record<string, number>
  confusion_matrix: ConfusionMatrixData | null
  roc_curve: ROCCurveData | null
  pr_curve: PRCurveData | null
  feature_importance: Record<string, number> | null
  ai_explanation: AIExplanation | null
  evaluated_at: string
}

export interface ModelComparisonRequest {
  model_ids: string[]
}

export interface ModelEvaluationSummary {
  model_id: string
  name: string
  algorithm: string
  problem_type: string
  cv_score: number | null
  test_score: number | null
  metrics: Record<string, number>
  created_at: string | null
}

export interface ModelComparisonResponse {
  problem_type: string
  dataset_id: string
  models: ModelEvaluationSummary[]
}

/** Type guard: classification vs regression metrics. */
export function isClassificationMetrics(
  metrics: ClassificationMetrics | RegressionMetrics
): metrics is ClassificationMetrics {
  return 'accuracy' in metrics
}
