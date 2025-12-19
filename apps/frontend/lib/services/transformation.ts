/**
 * Transformation service for data pipeline operations
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

export interface TransformationStep {
  type: string
  parameters: Record<string, any>
  description?: string
}

export interface TransformationRequest {
  dataset_id: string
  transformation_type: string
  parameters: Record<string, any>
  preview_rows?: number
}

export interface TransformationPreviewResponse {
  success: boolean
  preview_data: any[]
  affected_rows: number
  affected_columns: string[]
  stats_before: Record<string, any>
  stats_after: Record<string, any>
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

export interface Recipe {
  id: string
  name: string
  description: string
  user_id: string
  steps: Array<{
    step_id: string
    type: string
    parameters: Record<string, any>
    description: string
    order: number
  }>
  created_at: string
  updated_at: string
  is_public: boolean
  tags: string[]
  usage_count: number
  rating: number
}

export interface RecipeListResponse {
  recipes: Recipe[]
  total: number
  page: number
  per_page: number
}

export interface RecipeCompatibilityResponse {
  is_compatible: boolean
  missing_columns: string[]
  type_mismatches: Record<string, string>
  warnings: string[]
  suggestions: string[]
  compatibility_score: number
}

export interface RecipeShareResponse {
  shared_recipe_id: string
  target_user_id: string
  shared_at: string
  message: string
}

export interface SharedRecipe {
  id: string
  name: string
  description: string
  original_recipe_id: string
  original_owner_id: string
  shared_at: string
  version: number
  tags: string[]
  steps_count: number
}

export interface SharedRecipeListResponse {
  shared_recipes: SharedRecipe[]
  total: number
}

export interface RecipeExportJSONResponse {
  format_version: string
  recipe: any
}

export class TransformationService {
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

  static async createRecipe(
    recipe: {
      name: string
      description: string
      steps: TransformationStep[]
      dataset_id?: string
      is_public?: boolean
      tags?: string[]
    },
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

  static async importRecipe(
    jsonData: any,
    token: string | null
  ): Promise<Recipe> {
    const response = await fetch(
      `${API_BASE_URL}/transformations/recipes/import`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify({ json_data: jsonData })
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to import recipe')
    }

    return response.json()
  }
}