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
}