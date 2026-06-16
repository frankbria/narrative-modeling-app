/**
 * Shared API response interfaces.
 *
 * These describe the JSON shapes returned by the FastAPI backend that are
 * consumed across the workflow pages (deploy, evaluate, predict, upload,
 * monitor) and the dataset exploration view. They are intentionally narrow
 * to the fields the UI actually reads.
 */

/**
 * Response from the model deployment endpoint (`PUT /models/{id}/deploy`).
 *
 * Mirrors the backend `ModelDeployResponse` Pydantic schema in
 * `apps/backend/app/schemas/model.py` — keep the two in sync. The backend does
 * not issue an API key on deploy, so there is intentionally no `api_key` field.
 */
export interface DeployResponse {
  model_id: string
  status: string
  deployed_at: string
  deployment_endpoint: string | null
  message: string
}

/**
 * Narrow view of `GET /models/{id}` (`ModelConfigResponse`) used by the deploy
 * page to detect an already-deployed model on mount. Only the deployment fields
 * the UI reads are typed here; mirrors `DeploymentConfigResponse` in
 * `apps/backend/app/schemas/model.py`.
 */
export interface ModelDeploymentView {
  deployment_config?: {
    is_deployed: boolean
    deployment_endpoint: string | null
    deployed_at: string | null
  }
}

/** A single feature-importance entry. */
export interface FeatureImportance {
  name: string
  importance: number
}

/** Response from the model evaluation endpoint. */
export interface EvaluationResponse {
  metrics?: Record<string, number | string>
  feature_importance?: FeatureImportance[]
  insights?: string[]
  warnings?: string[]
}

/**
 * Prediction request/response shapes live in `lib/services/model.ts`
 * (the canonical contract for the prediction endpoints, issue #82).
 */

/** Response from a successful chunked upload completion. */
export interface ChunkedUploadResponse {
  file_id: string
  filename?: string
  status?: string
  preview?: Record<string, unknown>[]
  pii_report?: PIIReport
}

/** PII detection summary attached to upload responses. */
export interface PIIReport {
  has_pii: boolean
  detections: Array<{
    column: string
    field: string
    type: string
    confidence: number
    start?: number
    end?: number
  }>
  risk_level: string
  total_detections: number
  affected_columns: string[]
}

/** Distribution of prediction values for the monitoring view. */
export interface PredictionDistribution {
  model_id: string
  distribution: Record<string, number>
  total: number
  unique_values: number
  most_common?: string
  least_common?: string
}

/**
 * A single column entry within a dataset schema.
 *
 * Covers the union of fields consumed by both the SchemaViewer
 * (data_type/nullable/...) and the InteractiveVisualizationDashboard mapper
 * (type/unique_count/null_count).
 */
export interface DatasetColumnSchema {
  name: string
  data_type: string
  nullable: boolean
  unique: boolean
  cardinality: number
  null_count: number
  null_percentage: number
  sample_values?: unknown[]
  type?: string
  unique_count?: number
}

/** Schema portion of a processed dataset. */
export interface DatasetSchema {
  columns: DatasetColumnSchema[]
  row_count: number
  column_count: number
  inference_confidence?: number
}

/** Canonical data_type values (schema_inference.py DataType) treated as numeric
 *  for statistics/visualization purposes. Intentionally excludes legacy pandas
 *  dtypes ('int64', 'float64', ...) — callers tolerating legacy documents add
 *  those themselves (see classifyColumnType in app/explore/[id]/page.tsx). */
export const NUMERIC_DATA_TYPES = ['integer', 'float', 'currency', 'percentage'] as const

/** A column statistic entry for the statistics dashboard. */
export interface DatasetColumnStatistic {
  column_name: string
  data_type: string
  total_count: number
  null_count: number
  null_percentage: number
  unique_count: number
  unique_percentage: number
  mean?: number
  median?: number
  std_dev?: number
  min_value?: number
  max_value?: number
  q1?: number
  q3?: number
  outlier_count?: number
  outlier_percentage?: number
  most_frequent_values?: Array<{ value: unknown; count: number; percentage: number }>
}

/** Statistics portion of a processed dataset. */
export interface DatasetStatistics {
  row_count: number
  column_count: number
  memory_usage_mb: number
  correlation_matrix?: Record<string, Record<string, number>>
  column_statistics: DatasetColumnStatistic[]
  missing_value_summary: {
    total_missing_values: number
    columns_with_missing: number
    complete_columns: number
  }
}

/** A quality issue entry within a dataset quality report. */
export interface DatasetQualityIssue {
  dimension: string
  column?: string
  severity: 'low' | 'medium' | 'high'
  description: string
  affected_rows: number
  affected_percentage: number
}

/** Quality report portion of a processed dataset. */
export interface DatasetQualityReport {
  overall_quality_score: number
  dimension_scores: Record<string, number>
  critical_issues: DatasetQualityIssue[]
  warnings: DatasetQualityIssue[]
  recommendations: string[]
}
