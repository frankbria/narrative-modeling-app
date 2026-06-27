/**
 * Data quality scoring system types (issue #102).
 *
 * Mirrors backend schemas in apps/backend/app/schemas/quality.py and
 * apps/backend/app/schemas/version.py — change both together.
 */

export interface ActionableRecommendation {
  dimension: string
  description: string
  transformation_type: string
  affected_columns: string[]
  severity: 'low' | 'medium' | 'high'
}

export interface QualityGateResult {
  gate_name: string
  passed: boolean
  actual_score: number
  required_score: number
  failing_dimensions: string[]
  is_blocking: boolean
}

export interface QualityReportResponse {
  file_id: string
  filename: string | null
  score_0_100: number
  component_scores: Record<string, number>
  recommendations: string[]
  actionable_recommendations: ActionableRecommendation[]
  gates: QualityGateResult[]
  critical_issue_count: number
  warning_count: number
  partial: boolean
}

export interface QualityTrendPoint {
  version_number: number | null
  created_at: string
  score_before: number | null
  score_after: number | null
  improvement: number | null
  transformation: string
}

export interface QualityTrendResponse {
  dataset_id: string
  points: QualityTrendPoint[]
  overall_improvement: number | null
  best_score: number | null
  worst_score: number | null
}
