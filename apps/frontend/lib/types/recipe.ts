/**
 * TypeScript type definitions for Recipe System
 *
 * These types mirror the backend Pydantic schemas for type safety across the API boundary.
 *
 * @module lib/types/recipe
 */

/**
 * Generic parameter value (can be string, number, boolean, array, or object)
 */
export type ParameterValue = string | number | boolean | null | ParameterValue[] | { [key: string]: ParameterValue }

/**
 * Transformation step within a recipe
 */
export interface TransformationStep {
  type: string
  parameters: Record<string, ParameterValue>
  description?: string
}

/**
 * Detailed recipe step with metadata
 */
export interface RecipeStep {
  step_id: string
  type: string
  parameters: Record<string, ParameterValue>
  description: string
  order: number
}

/**
 * Complete recipe with all metadata
 */
export interface Recipe {
  id: string
  name: string
  description: string
  user_id: string
  steps: RecipeStep[]
  created_at: string
  updated_at: string
  is_public: boolean
  tags: string[]
  usage_count: number
  rating: number
  version?: number
  parent_recipe_id?: string
}

/**
 * Recipe list response with pagination
 */
export interface RecipeListResponse {
  recipes: Recipe[]
  total: number
  page: number
  per_page: number
}

/**
 * Recipe compatibility check response
 */
export interface RecipeCompatibilityResponse {
  is_compatible: boolean
  missing_columns: string[]
  type_mismatches: Array<{
    column: string
    expected: string
    actual: string
  }>
  warnings: string[]
  suggestions: string[]
  compatibility_score: number
}

/**
 * Recipe sharing response
 */
export interface RecipeShareResponse {
  shared_recipe_id: string
  target_user_id: string
  shared_at: string
  message: string
}

/**
 * Shared recipe (independent copy)
 */
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

/**
 * List of shared recipes
 */
export interface SharedRecipeListResponse {
  shared_recipes: SharedRecipe[]
  total: number
}

/**
 * Recipe version metadata
 */
export interface RecipeVersion {
  id: string
  name: string
  version: number
  parent_recipe_id: string | null
  created_at: string
  version_notes?: string
  changes_summary?: string
}

/**
 * Recipe version history response
 */
export interface RecipeVersionHistoryResponse {
  versions: RecipeVersion[]
  total_versions: number
}

/**
 * Recipe export as JSON
 */
export interface RecipeExportJSONResponse {
  format_version: string
  recipe: {
    name: string
    description: string
    steps: RecipeStep[]
    tags: string[]
    metadata: Record<string, ParameterValue>
  }
}

/**
 * Request to create a new recipe
 */
export interface RecipeCreateRequest {
  name: string
  description: string
  steps: TransformationStep[]
  dataset_id?: string
  is_public?: boolean
  tags?: string[]
}

/**
 * Request to create a recipe version
 */
export interface RecipeVersionRequest {
  changes: Record<string, ParameterValue>
  version_notes?: string
}

/**
 * Request to duplicate a recipe
 */
export interface RecipeDuplicateRequest {
  new_name: string
}

/**
 * Request to share a recipe
 */
export interface RecipeShareRequest {
  target_user_id: string
}

/**
 * Request to check recipe compatibility
 */
export interface RecipeCompatibilityRequest {
  dataset_schema: Record<string, string>
}

/**
 * Request to apply a recipe to a dataset
 */
export interface RecipeApplyRequest {
  dataset_id: string
}

/**
 * Request to import a recipe from JSON
 */
export interface RecipeImportRequest {
  json_data: RecipeExportJSONResponse
  name_override?: string
}
