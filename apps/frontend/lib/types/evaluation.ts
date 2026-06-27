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
  /**
   * True when these metrics were computed on the calibrator's own fit data
   * rather than a clean held-out set, so they may be optimistically biased
   * (issue #201 small-data fallback). False on the honest split.
   */
  evaluation_on_calibration_set: boolean
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

/** One feature's importance, for a ranked importance list (issue #80). */
export interface RankedFeature {
  feature_name: string
  importance: number
}

/**
 * Global feature importance for one model (issue #80). Carries model-native
 * importance and, when the model type is SHAP-supported, SHAP-based importance.
 */
export interface FeatureImportanceResponse {
  model_id: string
  partial: boolean
  /** "tree", "linear", or null when SHAP is unavailable */
  explainer_type: string | null
  native_importance: RankedFeature[]
  shap_importance: RankedFeature[] | null
  message: string | null
}

/**
 * SHAP summary-plot data for one model (issue #80). feature_importance is the
 * mean |SHAP| per feature, ranked. partial=true (with empty lists + a message)
 * for models trained before #80 or whose type isn't SHAP-supported.
 */
export interface ShapSummaryResponse {
  model_id: string
  partial: boolean
  explainer_type: string | null
  problem_type: string
  feature_importance: RankedFeature[]
  base_value: number | null
  plain_language: string
  message: string | null
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

// Model versioning & history (issue #78). Mirrors app/schemas/evaluation.py.

export interface ModelVersionEntry {
  model_id: string
  version_number: number
  name: string
  algorithm: string
  problem_type: string
  cv_score: number | null
  test_score: number | null
  is_production: boolean
  is_active: boolean
  created_at: string | null
  promoted_at: string | null
  dataset_id: string
  dataset_version_id: string | null
  parent_model_id: string | null
  feature_names: string[]
  environment_metadata: Record<string, unknown> | null
  version_notes: string | null
}

export interface ModelVersionListResponse {
  model_id: string
  dataset_id: string
  name: string
  total: number
  production_model_id: string | null
  versions: ModelVersionEntry[]
}

export interface PromoteVersionResponse {
  model_id: string
  is_production: boolean
  promoted_at: string | null
  demoted_model_ids: string[]
}

/** Type guard: classification vs regression metrics. */
export function isClassificationMetrics(
  metrics: ClassificationMetrics | RegressionMetrics
): metrics is ClassificationMetrics {
  return 'accuracy' in metrics
}

// --- Error analysis (issue #81) — mirrors app/schemas/error_analysis.py ---

export interface ErrorDistribution {
  total_samples: number
  total_errors: number
  overall_error_rate: number
  per_class_error_rate: Record<string, number>
}

export interface ConfusionPair {
  actual: string
  predicted: string
  count: number
  rate: number
}

export interface ErrorSegment {
  feature: string
  range_label: string
  lower: number | null
  upper: number | null
  error_rate: number
  error_count: number
  sample_count: number
}

export interface ErrorCluster {
  cluster_id: number
  size: number
  characteristics: string[]
  dominant_confusion: string | null
}

export interface ErrorPattern {
  rule: string
  error_rate: number
  error_count: number
  sample_count: number
}

export interface ErrorCase {
  index: number
  actual: string
  predicted: string
  confidence: number | null
  top_features: Record<string, number>
}

export interface ErrorAnalysisResponse {
  model_id: string
  model_name: string | null
  algorithm: string | null
  problem_type: string
  partial: boolean
  distribution: ErrorDistribution | null
  confusion_pairs: ConfusionPair[]
  segments: ErrorSegment[]
  clusters: ErrorCluster[]
  patterns: ErrorPattern[]
  cases: ErrorCase[]
  suggestions: string[]
  suggestions_generated_by: 'openai' | 'fallback'
  message: string | null
  evaluated_at: string
}
