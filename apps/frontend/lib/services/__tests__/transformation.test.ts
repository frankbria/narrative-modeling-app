/**
 * Tests for TransformationService
 */
import { TransformationService } from '../transformation'

const API_BASE_URL = 'http://localhost:8000'
const API_VERSION = 'api/v1'

describe('TransformationService', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  const mockToken = 'test-jwt-token'
  const mockDatasetId = 'dataset123'

  describe('Authentication Token Handling', () => {
    it('should include auth token in headers when provided', async () => {
      const mockResponse = { success: true, suggestions: [], data_quality_score: 0.95, critical_issues: [] }
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

      await TransformationService.getTransformationSuggestions(mockDatasetId, mockToken)

      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE_URL}/${API_VERSION}/transformations/suggestions/${mockDatasetId}`,
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': `Bearer ${mockToken}`,
            'Content-Type': 'application/json'
          })
        })
      )
    })

    it('should not include auth header when token is null', async () => {
      const mockResponse = { success: true, suggestions: [], data_quality_score: 0.95, critical_issues: [] }
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

      await TransformationService.getTransformationSuggestions(mockDatasetId, null)

      const lastCall = (global.fetch as jest.Mock).mock.calls[(global.fetch as jest.Mock).mock.calls.length - 1]
      const headers = lastCall[1]?.headers as HeadersInit
      expect(headers).not.toHaveProperty('Authorization')
    })
  })

  describe('Preview Transformation', () => {
    it('should preview transformation successfully', async () => {
      const request = {
        dataset_id: mockDatasetId,
        transformation_type: 'trim_whitespace',
        parameters: { columns: ['name'] },
        preview_rows: 100
      }

      const mockResponse = {
        success: true,
        preview_data: [{ name: 'John' }, { name: 'Jane' }],
        affected_rows: 2,
        affected_columns: ['name'],
        stats_before: { name: { unique: 2 } },
        stats_after: { name: { unique: 2 } },
        warnings: []
      }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

      const result = await TransformationService.previewTransformation(request, mockToken)

      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE_URL}/${API_VERSION}/transformations/preview`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(request)
        })
      )
    })

    it('should handle preview errors', async () => {
      const request = {
        dataset_id: mockDatasetId,
        transformation_type: 'invalid_type',
        parameters: {}
      }

      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Invalid transformation type' })
      } as Response)

      await expect(
        TransformationService.previewTransformation(request, mockToken)
      ).rejects.toThrow('Invalid transformation type')
    })
  })

  describe('Apply Transformation', () => {
    it('should apply single transformation successfully', async () => {
      const request = {
        dataset_id: mockDatasetId,
        transformation_type: 'remove_duplicates',
        parameters: { columns: ['email'], keep: 'first' }
      }

      const mockResponse = {
        success: true,
        dataset_id: mockDatasetId,
        transformation_id: 'trans_123',
        affected_rows: 5,
        affected_columns: ['email'],
        execution_time_ms: 250
      }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

      const result = await TransformationService.applyTransformation(request, mockToken)

      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE_URL}/${API_VERSION}/transformations/apply`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(request)
        })
      )
    })

    it('should apply transformation pipeline', async () => {
      const request = {
        dataset_id: mockDatasetId,
        transformations: [
          {
            type: 'trim_whitespace',
            parameters: { columns: [] },
            description: 'Clean whitespace'
          },
          {
            type: 'fill_missing',
            parameters: { columns: ['age'], method: 'mean' },
            description: 'Fill missing ages'
          }
        ],
        save_as_recipe: true,
        recipe_name: 'Data Cleaning Pipeline',
        recipe_description: 'Standard cleaning steps'
      }

      const mockResponse = {
        success: true,
        dataset_id: mockDatasetId,
        transformation_id: 'pipeline_123',
        affected_rows: 100,
        affected_columns: ['name', 'age'],
        execution_time_ms: 500
      }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

      const result = await TransformationService.applyTransformationPipeline(request, mockToken)

      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE_URL}/${API_VERSION}/transformations/pipeline/apply`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(request)
        })
      )
    })
  })

  describe('Auto Clean', () => {
    it('should auto-clean dataset with default options', async () => {
      const request = {
        dataset_id: mockDatasetId,
        options: {
          remove_duplicates: true,
          trim_whitespace: true,
          handle_missing: 'drop' as const
        }
      }

      const mockResponse = {
        success: true,
        dataset_id: mockDatasetId,
        transformation_id: 'auto_clean_123',
        affected_rows: 50,
        affected_columns: ['all'],
        execution_time_ms: 750
      }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

      const result = await TransformationService.autoCleanDataset(request, mockToken)

      expect(result).toEqual(mockResponse)
    })
  })

  describe('Transformation Suggestions', () => {
    it('should get transformation suggestions', async () => {
      const mockResponse = {
        suggestions: [
          { suggestion: 'Remove duplicates in email column' },
          { suggestion: 'Fill missing values in age column' }
        ],
        data_quality_score: 0.85,
        critical_issues: ['High missing data ratio in salary column']
      }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

      const result = await TransformationService.getTransformationSuggestions(mockDatasetId, mockToken)

      expect(result).toEqual(mockResponse)
      expect(result.data_quality_score).toBe(0.85)
      expect(result.critical_issues).toHaveLength(1)
    })
  })

  describe('Recipe Management', () => {
    describe('List Recipes', () => {
      it('should list user recipes with pagination', async () => {
        const mockResponse = {
          recipes: [
            {
              id: 'recipe1',
              name: 'Basic Cleaning',
              description: 'Standard cleaning steps',
              user_id: 'user123',
              steps: [],
              created_at: '2024-01-01T00:00:00Z',
              updated_at: '2024-01-01T00:00:00Z',
              is_public: false,
              tags: ['cleaning'],
              usage_count: 5,
              rating: 4.5
            }
          ],
          total: 1,
          page: 1,
          per_page: 20
        }

        global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

        const result = await TransformationService.listRecipes(mockToken, 1, 20, true, ['cleaning'])

        expect(result.recipes).toHaveLength(1)
        expect(result.recipes[0].name).toBe('Basic Cleaning')
        
        // Check URL params
        const lastCall = (global.fetch as jest.Mock).mock.calls[(global.fetch as jest.Mock).mock.calls.length - 1]
        const url = lastCall[0] as string
        expect(url).toContain('page=1')
        expect(url).toContain('per_page=20')
        expect(url).toContain('include_public=true')
        expect(url).toContain('tags=cleaning')
      })

      it('should get popular recipes', async () => {
        const mockResponse = {
          recipes: [
            {
              id: 'popular1',
              name: 'Popular Pipeline',
              description: 'Most used pipeline',
              user_id: 'other_user',
              steps: [],
              created_at: '2024-01-01T00:00:00Z',
              updated_at: '2024-01-01T00:00:00Z',
              is_public: true,
              tags: ['popular'],
              usage_count: 100,
              rating: 4.8
            }
          ],
          total: 1,
          page: 1,
          per_page: 10
        }

        global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

        const result = await TransformationService.getPopularRecipes(mockToken, 5)

        expect(result.recipes[0].usage_count).toBe(100)
        expect(result.recipes[0].is_public).toBe(true)
      })
    })

    describe('Recipe CRUD', () => {
      it('should create a new recipe', async () => {
        const newRecipe = {
          name: 'My Custom Pipeline',
          description: 'Custom data cleaning steps',
          steps: [
            {
              type: 'trim_whitespace',
              parameters: { columns: [] },
              description: 'Clean all text'
            }
          ],
          is_public: false,
          tags: ['custom', 'cleaning']
        }

        const mockResponse = {
          id: 'new_recipe_id',
          ...newRecipe,
          user_id: 'user123',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          usage_count: 0,
          rating: 0,
          steps: [
            {
              step_id: 'step1',
              type: 'trim_whitespace',
              parameters: { columns: [] },
              description: 'Clean all text',
              order: 0
            }
          ]
        }

        global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

        const result = await TransformationService.createRecipe(newRecipe, mockToken)

        expect(result.id).toBe('new_recipe_id')
        expect(result.name).toBe('My Custom Pipeline')
      })

      it('should get a single recipe', async () => {
        const recipeId = 'recipe123'
        const mockResponse = {
          id: recipeId,
          name: 'Test Recipe',
          description: 'Test description',
          user_id: 'user123',
          steps: [],
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          is_public: false,
          tags: [],
          usage_count: 10,
          rating: 4.0
        }

        global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

        const result = await TransformationService.getRecipe(recipeId, mockToken)

        expect(result.id).toBe(recipeId)
        expect(global.fetch).toHaveBeenCalledWith(
          `${API_BASE_URL}/${API_VERSION}/transformations/recipes/${recipeId}`,
          expect.any(Object)
        )
      })

      it('should apply a recipe to dataset', async () => {
        const recipeId = 'recipe123'
        const mockResponse = {
          success: true,
          dataset_id: mockDatasetId,
          transformation_id: 'recipe_apply_123',
          affected_rows: 75,
          affected_columns: ['multiple'],
          execution_time_ms: 1000
        }

        global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

        const result = await TransformationService.applyRecipe(recipeId, mockDatasetId, mockToken)

        expect(result.success).toBe(true)
        expect(global.fetch).toHaveBeenCalledWith(
          `${API_BASE_URL}/${API_VERSION}/transformations/recipes/${recipeId}/apply`,
          expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({ dataset_id: mockDatasetId })
          })
        )
      })

      it('should delete a recipe', async () => {
        const recipeId = 'recipe123'
        global.fetch.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ message: 'Recipe deleted successfully' })
        } as Response)

        await TransformationService.deleteRecipe(recipeId, mockToken)

        expect(global.fetch).toHaveBeenCalledWith(
          `${API_BASE_URL}/${API_VERSION}/transformations/recipes/${recipeId}`,
          expect.objectContaining({
            method: 'DELETE'
          })
        )
      })
    })
  })

  describe('Error Handling', () => {
    it('should handle 401 unauthorized errors', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Invalid authentication token' })
      } as Response)

      await expect(
        TransformationService.getTransformationSuggestions(mockDatasetId, 'invalid-token')
      ).rejects.toThrow('Invalid authentication token')
    })

    it('should handle 403 forbidden errors', async () => {
      const recipeId = 'private_recipe'
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Access denied' })
      } as Response)

      await expect(
        TransformationService.getRecipe(recipeId, mockToken)
      ).rejects.toThrow('Access denied')
    })

    it('should handle 404 not found errors', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Dataset not found' })
      } as Response)

      await expect(
        TransformationService.getTransformationSuggestions('invalid_dataset', mockToken)
      ).rejects.toThrow('Dataset not found')
    })

    it('should handle network errors', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Network error'))

      await expect(
        TransformationService.listRecipes(mockToken)
      ).rejects.toThrow('Network error')
    })

    it('should handle empty error responses', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => { throw new Error('Invalid JSON') }
      } as Response)

      await expect(
        TransformationService.getTransformationSuggestions(mockDatasetId, mockToken)
      ).rejects.toThrow()
    })
  })

  describe('API Version Handling', () => {
    it('should use correct API version in URLs', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ recipes: [], total: 0, page: 1, per_page: 20 })
      } as Response)

      await TransformationService.listRecipes(mockToken)

      const lastCall = (global.fetch as jest.Mock).mock.calls[(global.fetch as jest.Mock).mock.calls.length - 1]
      const url = lastCall[0] as string
      expect(url).toContain('/api/v1/transformations')
    })
  })
})