/**
 * Transformation service for data pipeline operations
 *
 * Provides methods for transformation operations, recipe management,
 * and pipeline execution.
 *
 * @module lib/services/transformation
 */

import type {
  Recipe,
  RecipeListResponse,
  RecipeCompatibilityResponse,
  RecipeShareResponse,
  SharedRecipeListResponse,
  RecipeExportJSONResponse,
  RecipeVersionHistoryResponse,
  RecipeCreateRequest,
  TransformationStep,
  ParameterValue
} from '@/lib/types/recipe'

// Re-export recipe types so consumers importing the service (which also need
// the value-level TransformationService) can pull the related types from a
// single module.
export type {
  Recipe,
  RecipeListResponse,
  RecipeCompatibilityResponse,
  RecipeShareResponse,
  SharedRecipe,
  SharedRecipeListResponse,
  RecipeExportJSONResponse,
  RecipeVersionHistoryResponse,
  RecipeCreateRequest,
  TransformationStep,
  ParameterValue
} from '@/lib/types/recipe'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

export interface TransformationRequest {
  dataset_id: string
  transformation_type: string
  parameters: Record<string, ParameterValue>
  preview_rows?: number
}

// =============================================================================
// Bulk Transformation Types
// =============================================================================

export interface ColumnMetadata {
  column_name: string
  field_type: string
  missing_values: number
  unique_values: number
  is_constant: boolean
  is_high_cardinality: boolean
}

export interface ColumnSelectionPatternRequest {
  pattern_type: 'data_type' | 'name_pattern' | 'quality_metric' | 'custom'
  criteria: Record<string, ParameterValue>
}

export interface ColumnSelectionResponse {
  columns: ColumnMetadata[]
  total_matched: number
  pattern_applied: string
}

export interface BulkTransformationPreviewRequest {
  selected_columns: string[]
  transformation_type: string
  global_parameters?: Record<string, ParameterValue>
  per_column_params?: Record<string, Record<string, ParameterValue>>
  preview_rows?: number
}

export interface ColumnPreviewResult {
  column_name: string
  success: boolean
  preview_data?: Array<Record<string, ParameterValue>>
  stats_before?: Record<string, ParameterValue>
  stats_after?: Record<string, ParameterValue>
  affected_rows: number
  error?: string
  warnings: string[]
}

export interface BulkTransformationPreviewResponse {
  success: boolean
  column_previews: ColumnPreviewResult[]
  total_estimated_rows_affected: number
  total_columns: number
  successful_previews: number
  failed_previews: number
  error?: string
  warnings: string[]
}

export interface BulkTransformationRequest {
  selected_columns: string[]
  transformation_type: string
  global_parameters?: Record<string, ParameterValue>
  per_column_params?: Record<string, Record<string, ParameterValue>>
  stop_on_error?: boolean
}

export interface BulkTransformationJobResponse {
  job_id: string
  status: string
  selected_columns: string[]
  total_columns: number
  message: string
}

export interface BulkTransformationProgressResponse {
  job_id: string
  status: string
  progress: Record<string, ParameterValue>
  percentage_complete: number
  total_columns: number
  processed_columns: number
  successful_columns: number
  failed_columns: number
  current_column?: string
  estimated_remaining_seconds?: number
  error_message?: string
  result?: {
    successful_columns: string[]
    failed_columns: Array<{ column_name: string; error: string }>
    total_time_ms: number
    total_rows_affected: number
  }
}

export interface BulkJobListResponse {
  jobs: BulkTransformationJobResponse[]
  total: number
}

export interface TransformationPreviewResponse {
  success: boolean
  preview_data: Array<Record<string, ParameterValue>>
  affected_rows: number
  affected_columns: string[]
  stats_before: Record<string, ParameterValue>
  stats_after: Record<string, ParameterValue>
  error?: string
  warnings?: string[]
}

export interface TransformationApplyResponse {
  success: boolean
  dataset_id: string
  transformation_id: string
  affected_rows: number
  affected_columns: string[]
  execution_time_ms: number
  error?: string
}

export interface TransformationPipelineRequest {
  dataset_id: string
  transformations: TransformationStep[]
  save_as_recipe?: boolean
  recipe_name?: string
  recipe_description?: string
}

export interface AutoCleanRequest {
  dataset_id: string
  options: {
    remove_duplicates?: boolean
    trim_whitespace?: boolean
    handle_missing?: 'drop' | 'impute'
  }
}

export interface TransformationSuggestionResponse {
  suggestions: Array<{ suggestion: string }>
  data_quality_score: number
  critical_issues: string[]
}

/**
 * Statistical impact of transformations on data
 */
export interface ImpactStatistics {
  rows_affected: number
  values_changed: number
  columns_affected: string[]
  quality_score_before: number
  quality_score_after: number
  value_distributions?: Record<string, { before: Record<string, number>; after: Record<string, number> }>
}

/**
 * Result of transformation preview generation
 */
export interface PreviewResult {
  original_data: Array<Record<string, ParameterValue>>
  transformed_data: Array<Record<string, ParameterValue>>
  impact_stats: ImpactStatistics
  warnings: string[]
  errors: string[]
}

/**
 * API response for transformation preview endpoint
 */
export interface PreviewResponse {
  success: boolean
  preview_result?: PreviewResult
  error?: string
  cache_hit: boolean
}

// Recipe types are imported from @/lib/types/recipe

export class TransformationService {
  private static abortController: AbortController | null = null
  private static async getHeaders(token: string | null): Promise<HeadersInit> {
    return {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` })
    }
  }

  static async previewTransformation(
    request: TransformationRequest,
    token: string | null
  ): Promise<TransformationPreviewResponse> {
    const response = await fetch(`${API_BASE_URL}/transformations/preview`, {
      method: 'POST',
      headers: await this.getHeaders(token),
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Preview transformation failed')
    }

    return response.json()
  }

  static async applyTransformation(
    request: TransformationRequest,
    token: string | null
  ): Promise<TransformationApplyResponse> {
    const response = await fetch(`${API_BASE_URL}/transformations/apply`, {
      method: 'POST',
      headers: await this.getHeaders(token),
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Apply transformation failed')
    }

    return response.json()
  }

  static async applyTransformationPipeline(
    request: TransformationPipelineRequest,
    token: string | null
  ): Promise<TransformationApplyResponse> {
    const response = await fetch(`${API_BASE_URL}/transformations/pipeline/apply`, {
      method: 'POST',
      headers: await this.getHeaders(token),
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Apply pipeline failed')
    }

    return response.json()
  }

  /**
   * Preview transformation effects before applying them permanently
   *
   * Calls: POST /api/datasets/{datasetId}/transformations/preview
   *
   * @param datasetId - Dataset identifier
   * @param operations - List of transformation steps
   * @param sampleSize - Number of rows to sample (10-1000, default: 100)
   * @returns PreviewResponse with success status, preview_result, error, and cache_hit
   * @throws Error on network failures, 404, 429, or other HTTP errors
   */
  static async previewTransformations(
    datasetId: string,
    operations: TransformationStep[],
    sampleSize: number = 100,
    token: string | null = null
  ): Promise<PreviewResponse> {
    // Cancel any previous request to prevent race conditions
    if (this.abortController) {
      this.abortController.abort()
    }

    // Create new abort controller for request cancellation (debouncing support)
    this.abortController = new AbortController()

    const response = await fetch(
      `${API_BASE_URL}/datasets/${datasetId}/transformations/preview`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify({
          transformation_steps: operations,
          preview_rows: sampleSize
        }),
        signal: this.abortController.signal
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || `Preview failed with status ${response.status}`)
    }

    return response.json()
  }

  static async autoCleanDataset(
    request: AutoCleanRequest,
    token: string | null
  ): Promise<TransformationApplyResponse> {
    const response = await fetch(`${API_BASE_URL}/transformations/auto-clean`, {
      method: 'POST',
      headers: await this.getHeaders(token),
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Auto-clean failed')
    }

    return response.json()
  }

  static async getTransformationSuggestions(
    datasetId: string,
    token: string | null
  ): Promise<TransformationSuggestionResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/suggestions/${datasetId}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to get suggestions')
    }

    return response.json()
  }

  /**
   * List recipes with pagination and filtering
   *
   * @param token - Authentication token
   * @param page - Page number (1-indexed)
   * @param perPage - Results per page
   * @param includePublic - Include public recipes from other users
   * @param tags - Filter by tags (optional)
   * @returns Paginated recipe list
   */
  static async listRecipes(
    token: string | null,
    page: number = 1,
    perPage: number = 20,
    includePublic: boolean = true,
    tags?: string[]
  ): Promise<RecipeListResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      per_page: perPage.toString(),
      include_public: includePublic.toString()
    })

    if (tags && tags.length > 0) {
      tags.forEach(tag => params.append('tags', tag))
    }

    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes?${params}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to fetch recipes')
    }

    return response.json()
  }

  static async getPopularRecipes(
    token: string | null,
    limit: number = 10
  ): Promise<RecipeListResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/popular?limit=${limit}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to fetch popular recipes')
    }

    return response.json()
  }

  static async getRecipe(
    recipeId: string,
    token: string | null
  ): Promise<Recipe> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/${recipeId}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to fetch recipe')
    }

    return response.json()
  }

  static async applyRecipe(
    recipeId: string,
    datasetId: string,
    token: string | null
  ): Promise<TransformationApplyResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/${recipeId}/apply`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify({ dataset_id: datasetId })
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to apply recipe')
    }

    return response.json()
  }

  /**
   * Create a new recipe
   *
   * @param recipe - Recipe creation request
   * @param token - Authentication token
   * @returns The created recipe
   */
  static async createRecipe(
    recipe: RecipeCreateRequest,
    token: string | null
  ): Promise<Recipe> {
    const response = await fetch(`${API_BASE_URL}/transformations/recipes`, {
      method: 'POST',
      headers: await this.getHeaders(token),
      body: JSON.stringify(recipe)
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to create recipe')
    }

    return response.json()
  }

  static async deleteRecipe(
    recipeId: string,
    token: string | null
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/${recipeId}`,
      {
        method: 'DELETE',
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to delete recipe')
    }
  }

  /**
   * Check if a recipe is compatible with a dataset schema
   *
   * @param recipeId - ID of the recipe to check
   * @param datasetSchema - Dataset column schema (column_name -> data_type)
   * @param token - Authentication token
   * @returns Compatibility report with score and suggestions
   */
  static async checkRecipeCompatibility(
    recipeId: string,
    datasetSchema: Record<string, string>,
    token: string | null
  ): Promise<RecipeCompatibilityResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/${recipeId}/check-compatibility`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify({ dataset_schema: datasetSchema })
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to check compatibility')
    }

    return response.json()
  }

  /**
   * Duplicate an existing recipe with a new name
   *
   * @param recipeId - ID of the recipe to duplicate
   * @param newName - Name for the duplicated recipe
   * @param token - Authentication token
   * @returns The newly created duplicate recipe
   */
  static async duplicateRecipe(
    recipeId: string,
    newName: string,
    token: string | null
  ): Promise<Recipe> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/${recipeId}/duplicate`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify({ new_name: newName })
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to duplicate recipe')
    }

    return response.json()
  }

  /**
   * Share a recipe with another user (creates independent copy)
   *
   * @param recipeId - ID of the recipe to share
   * @param targetUserId - User ID to share the recipe with
   * @param token - Authentication token
   * @returns Share confirmation with shared recipe details
   */
  static async shareRecipe(
    recipeId: string,
    targetUserId: string,
    token: string | null
  ): Promise<RecipeShareResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/${recipeId}/share`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify({ target_user_id: targetUserId })
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to share recipe')
    }

    return response.json()
  }

  static async getSharedRecipes(
    token: string | null
  ): Promise<SharedRecipeListResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/shared`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to fetch shared recipes')
    }

    return response.json()
  }

  /**
   * Export a recipe as JSON for backup or sharing
   *
   * @param recipeId - ID of the recipe to export
   * @param token - Authentication token
   * @returns Recipe data in JSON format with format version
   */
  static async exportRecipeAsJSON(
    recipeId: string,
    token: string | null
  ): Promise<RecipeExportJSONResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/${recipeId}/export/json`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to export recipe')
    }

    return response.json()
  }

  /**
   * Import a recipe from JSON data
   *
   * @param jsonData - Recipe JSON data (from export)
   * @param token - Authentication token
   * @param nameOverride - Optional new name for the imported recipe
   * @returns The newly created recipe from import
   */
  static async importRecipe(
    jsonData: RecipeExportJSONResponse,
    token: string | null,
    nameOverride?: string
  ): Promise<Recipe> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/import`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify({
          json_data: jsonData,
          name_override: nameOverride
        })
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to import recipe')
    }

    return response.json()
  }

  /**
   * Create a new version of an existing recipe
   *
   * @param recipeId - ID of the recipe to version
   * @param changes - Changes to apply to the new version
   * @param versionNotes - Optional notes about this version
   * @param token - Authentication token
   * @returns The newly created recipe version
   */
  static async createRecipeVersion(
    recipeId: string,
    changes: Record<string, ParameterValue>,
    versionNotes: string | undefined,
    token: string | null
  ): Promise<Recipe> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/${recipeId}/versions`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify({
          changes,
          version_notes: versionNotes
        })
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to create recipe version')
    }

    return response.json()
  }

  /**
   * Get version history for a recipe
   *
   * @param recipeId - ID of the recipe
   * @param token - Authentication token
   * @returns Version history with all versions
   */
  static async getRecipeVersionHistory(
    recipeId: string,
    token: string | null
  ): Promise<RecipeVersionHistoryResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/${recipeId}/versions`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to fetch version history')
    }

    return response.json()
  }

  // ===========================================================================
  // Bulk Transformation Methods
  // ===========================================================================

  /**
   * Select columns by pattern (data type, name pattern, quality metric)
   *
   * @param datasetId - Dataset identifier
   * @param pattern - Column selection pattern
   * @param token - Authentication token
   * @returns List of matching columns with metadata
   */
  static async selectColumnsByPattern(
    datasetId: string,
    pattern: ColumnSelectionPatternRequest,
    token: string | null
  ): Promise<ColumnSelectionResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/datasets/${datasetId}/columns/select-pattern`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify(pattern)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to select columns by pattern')
    }

    return response.json()
  }

  /**
   * Preview bulk transformation on multiple columns
   *
   * @param datasetId - Dataset identifier
   * @param request - Bulk preview request
   * @param token - Authentication token
   * @returns Preview results for each column
   */
  static async previewBulkTransformation(
    datasetId: string,
    request: BulkTransformationPreviewRequest,
    token: string | null
  ): Promise<BulkTransformationPreviewResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/datasets/${datasetId}/bulk-preview`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify(request)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to preview bulk transformation')
    }

    return response.json()
  }

  /**
   * Apply bulk transformation to multiple columns
   *
   * Creates an async job that processes columns with progress tracking.
   *
   * @param datasetId - Dataset identifier
   * @param request - Bulk transformation request
   * @param token - Authentication token
   * @returns Job response with job ID for status polling
   */
  static async applyBulkTransformation(
    datasetId: string,
    request: BulkTransformationRequest,
    token: string | null
  ): Promise<BulkTransformationJobResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/datasets/${datasetId}/bulk-apply`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify(request)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to apply bulk transformation')
    }

    return response.json()
  }

  /**
   * Get status and progress of a bulk transformation job
   *
   * @param datasetId - Dataset identifier
   * @param jobId - Job identifier
   * @param token - Authentication token
   * @returns Job progress and status
   */
  static async getBulkJobStatus(
    datasetId: string,
    jobId: string,
    token: string | null
  ): Promise<BulkTransformationProgressResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/datasets/${datasetId}/bulk-jobs/${jobId}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to get bulk job status')
    }

    return response.json()
  }

  /**
   * List bulk transformation jobs for a dataset
   *
   * @param datasetId - Dataset identifier
   * @param token - Authentication token
   * @param status - Optional status filter
   * @param limit - Maximum number of jobs to return
   * @returns List of jobs
   */
  static async listBulkJobs(
    datasetId: string,
    token: string | null,
    status?: string,
    limit: number = 50
  ): Promise<BulkJobListResponse> {
    const params = new URLSearchParams({ limit: limit.toString() })
    if (status) {
      params.append('status', status)
    }

    const response = await fetch(
      `${API_BASE_URL}/transformations/datasets/${datasetId}/bulk-jobs?${params}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to list bulk jobs')
    }

    return response.json()
  }

  /**
   * Cancel a pending or running bulk transformation job
   *
   * @param datasetId - Dataset identifier
   * @param jobId - Job identifier
   * @param token - Authentication token
   * @returns Success status
   */
  static async cancelBulkJob(
    datasetId: string,
    jobId: string,
    token: string | null
  ): Promise<{ success: boolean; message: string }> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/datasets/${datasetId}/bulk-jobs/${jobId}/cancel`,
      {
        method: 'POST',
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to cancel bulk job')
    }

    return response.json()
  }

  /**
   * Retry a failed bulk transformation job
   *
   * @param datasetId - Dataset identifier
   * @param jobId - Job identifier
   * @param token - Authentication token
   * @returns Restarted job response
   */
  static async retryBulkJob(
    datasetId: string,
    jobId: string,
    token: string | null
  ): Promise<BulkTransformationJobResponse> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/datasets/${datasetId}/bulk-jobs/${jobId}/retry`,
      {
        method: 'POST',
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to retry bulk job')
    }

    return response.json()
  }
}