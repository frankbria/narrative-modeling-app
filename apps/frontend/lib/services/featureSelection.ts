/**
 * Feature Selection service for ML feature engineering
 *
 * Provides methods for feature selection operations including
 * multiple selection algorithms, importance calculation, and
 * redundancy detection.
 *
 * @module lib/services/featureSelection
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

// =============================================================================
// Types
// =============================================================================

export type SelectionMethod =
  | 'correlation'
  | 'mutual_info'
  | 'random_forest'
  | 'rfe'
  | 'lasso'
  | 'statistical'

export type ProblemType = 'classification' | 'regression'

export interface FeatureScore {
  feature_name: string
  score: number
  rank: number
  selected: boolean
}

export interface RedundantPair {
  feature1: string
  feature2: string
  correlation: number
  recommendation: string
}

export interface FeatureSelectionRequest {
  target_column: string
  method: SelectionMethod
  top_k?: number
  threshold?: number
  correlation_threshold?: number
  problem_type?: ProblemType
  algorithm_params?: Record<string, any>
  sample_size?: number
}

export interface FeatureSelectionResult {
  dataset_id: string
  method: SelectionMethod
  selected_features: string[]
  feature_scores: FeatureScore[]
  redundant_pairs: RedundantPair[]
  correlation_matrix?: Record<string, Record<string, number>>
  explanation: string
  metadata: {
    problem_type: string
    n_samples: number
    n_features_original: number
    n_features_selected: number
    target_column: string
  }
  execution_time_ms: number
  created_at: string
}

export interface FeatureImportanceRequest {
  target_column: string
  method: SelectionMethod
  problem_type?: ProblemType
  algorithm_params?: Record<string, any>
}

export interface FeatureImportanceResponse {
  dataset_id: string
  method: SelectionMethod
  feature_scores: FeatureScore[]
  execution_time_ms: number
}

export interface RedundancyDetectionRequest {
  correlation_threshold?: number
  method?: 'pearson' | 'spearman' | 'kendall'
}

export interface RedundancyDetectionResponse {
  dataset_id: string
  redundant_pairs: RedundantPair[]
  correlation_matrix: Record<string, Record<string, number>>
  recommendations: string[]
}

export interface MethodComparisonRequest {
  target_column: string
  methods: SelectionMethod[]
  top_k?: number
  problem_type?: ProblemType
}

export interface MethodComparisonResult {
  method: SelectionMethod
  selected_features: string[]
  top_features: FeatureScore[]
  execution_time_ms: number
}

export interface MethodComparisonResponse {
  dataset_id: string
  results: MethodComparisonResult[]
  consensus_features: string[]
  overlap_matrix: Record<string, Record<string, number>>
  recommendations: string
}

export interface SelectedFeaturesResponse {
  dataset_id: string
  selected_features: string[]
  has_selection: boolean
}

// =============================================================================
// Service Class
// =============================================================================

export class FeatureSelectionService {
  private static async getHeaders(token: string | null): Promise<HeadersInit> {
    return {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` })
    }
  }

  /**
   * Run feature selection on a dataset
   *
   * Calls: POST /api/datasets/{datasetId}/features/select
   *
   * @param datasetId - Dataset identifier
   * @param request - Feature selection configuration
   * @param token - Authentication token
   * @returns Feature selection results with scores and explanations
   */
  static async selectFeatures(
    datasetId: string,
    request: FeatureSelectionRequest,
    token: string | null
  ): Promise<FeatureSelectionResult> {
    const response = await fetch(
      `${API_BASE_URL}/datasets/${datasetId}/features/select`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify(request)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Feature selection failed')
    }

    return response.json()
  }

  /**
   * Calculate feature importance scores
   *
   * Calls: POST /api/datasets/{datasetId}/features/importance
   *
   * @param datasetId - Dataset identifier
   * @param request - Importance calculation configuration
   * @param token - Authentication token
   * @returns Feature importance scores ranked by importance
   */
  static async calculateImportance(
    datasetId: string,
    request: FeatureImportanceRequest,
    token: string | null
  ): Promise<FeatureImportanceResponse> {
    const response = await fetch(
      `${API_BASE_URL}/datasets/${datasetId}/features/importance`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify(request)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Importance calculation failed')
    }

    return response.json()
  }

  /**
   * Detect redundant (highly correlated) features
   *
   * Calls: POST /api/datasets/{datasetId}/features/redundancy
   *
   * @param datasetId - Dataset identifier
   * @param request - Redundancy detection configuration
   * @param token - Authentication token
   * @returns Redundant feature pairs with correlations and recommendations
   */
  static async detectRedundancy(
    datasetId: string,
    request: RedundancyDetectionRequest,
    token: string | null
  ): Promise<RedundancyDetectionResponse> {
    const response = await fetch(
      `${API_BASE_URL}/datasets/${datasetId}/features/redundancy`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify(request)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Redundancy detection failed')
    }

    return response.json()
  }

  /**
   * Compare multiple feature selection methods
   *
   * Calls: POST /api/datasets/{datasetId}/features/compare
   *
   * @param datasetId - Dataset identifier
   * @param request - Method comparison configuration
   * @param token - Authentication token
   * @returns Comparison results with consensus features and overlap matrix
   */
  static async compareMethods(
    datasetId: string,
    request: MethodComparisonRequest,
    token: string | null
  ): Promise<MethodComparisonResponse> {
    const response = await fetch(
      `${API_BASE_URL}/datasets/${datasetId}/features/compare`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify(request)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Method comparison failed')
    }

    return response.json()
  }

  /**
   * Get previously selected features for a dataset
   *
   * Calls: GET /api/datasets/{datasetId}/features/selected
   *
   * @param datasetId - Dataset identifier
   * @param token - Authentication token
   * @returns Previously selected features or empty list
   */
  static async getSelectedFeatures(
    datasetId: string,
    token: string | null
  ): Promise<SelectedFeaturesResponse> {
    const response = await fetch(
      `${API_BASE_URL}/datasets/${datasetId}/features/selected`,
      {
        method: 'GET',
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to retrieve selected features')
    }

    return response.json()
  }
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Get human-readable name for selection method
 */
export function getMethodName(method: SelectionMethod): string {
  const names: Record<SelectionMethod, string> = {
    correlation: 'Correlation',
    mutual_info: 'Mutual Information',
    random_forest: 'Random Forest',
    rfe: 'Recursive Feature Elimination',
    lasso: 'LASSO',
    statistical: 'Statistical Tests'
  }
  return names[method]
}

/**
 * Get description for selection method
 */
export function getMethodDescription(method: SelectionMethod): string {
  const descriptions: Record<SelectionMethod, string> = {
    correlation:
      'Measures linear relationships between features and target using Pearson correlation',
    mutual_info:
      'Captures non-linear dependencies using mutual information theory',
    random_forest:
      'Uses tree-based importance from Random Forest models, handles feature interactions',
    rfe:
      'Recursively removes features to find the optimal subset using backward elimination',
    lasso:
      'Uses L1 regularization to automatically select features while training linear models',
    statistical:
      'Fast statistical tests (Chi-squared for classification, F-test for regression)'
  }
  return descriptions[method]
}

/**
 * Get recommended use case for method
 */
export function getMethodUseCase(method: SelectionMethod): string {
  const useCases: Record<SelectionMethod, string> = {
    correlation: 'Best for: Quick analysis, linear relationships, interpretable results',
    mutual_info: 'Best for: Non-linear data, categorical variables, complex relationships',
    random_forest: 'Best for: Tree-based models, feature interactions, robust selection',
    rfe: 'Best for: Finding optimal feature subset, high accuracy requirements',
    lasso: 'Best for: Linear models, automatic regularization, sparse solutions',
    statistical: 'Best for: Large datasets, quick filtering, statistical validation'
  }
  return useCases[method]
}

/**
 * Format execution time for display
 */
export function formatExecutionTime(ms: number): string {
  if (ms < 1000) {
    return `${Math.round(ms)}ms`
  } else if (ms < 60000) {
    return `${(ms / 1000).toFixed(1)}s`
  } else {
    const minutes = Math.floor(ms / 60000)
    const seconds = Math.round((ms % 60000) / 1000)
    return `${minutes}m ${seconds}s`
  }
}
