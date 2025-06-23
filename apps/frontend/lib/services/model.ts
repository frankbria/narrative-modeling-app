/**
 * Model training and management service
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

export interface TrainModelRequest {
  dataset_id: string
  target_column: string
  name?: string
  description?: string
  feature_config?: {
    handle_missing?: boolean
    scale_features?: boolean
    encode_categorical?: boolean
    create_interactions?: boolean
    select_features?: boolean
    max_features?: number
  }
  training_config?: {
    max_models?: number
    cv_folds?: number
    test_size?: number
  }
}

export interface ModelInfo {
  model_id: string
  name: string
  description?: string
  problem_type: string
  algorithm: string
  target_column: string
  cv_score: number
  test_score: number
  created_at: string
  last_used_at?: string
  is_active: boolean
  feature_names: string[]
  n_samples_train: number
  n_features: number
}

export interface PredictRequest {
  data: Record<string, any>[]
  include_probabilities?: boolean
}

export interface PredictResponse {
  predictions: any[]
  probabilities?: number[][]
  feature_names: string[]
  model_info: {
    model_id: string
    algorithm: string
    problem_type: string
    target_column: string
  }
}

export class ModelService {
  private static async getHeaders(token: string | null): Promise<HeadersInit> {
    return {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` })
    }
  }

  static async trainModel(
    request: TrainModelRequest,
    token: string | null
  ): Promise<{ model_id: string; status: string; message: string }> {
    const response = await fetch(`${API_BASE_URL}/ml/train`, {
      method: 'POST',
      headers: await this.getHeaders(token),
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to start model training')
    }

    return response.json()
  }

  static async listModels(
    token: string | null,
    datasetId?: string
  ): Promise<ModelInfo[]> {
    const params = new URLSearchParams()
    if (datasetId) params.append('dataset_id', datasetId)

    const response = await fetch(
      `${API_BASE_URL}/ml/?${params}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      throw new Error('Failed to fetch models')
    }

    return response.json()
  }

  static async getModel(
    modelId: string,
    token: string | null
  ): Promise<ModelInfo> {
    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      throw new Error('Failed to fetch model details')
    }

    return response.json()
  }

  static async predict(
    modelId: string,
    request: PredictRequest,
    token: string | null
  ): Promise<PredictResponse> {
    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}/predict`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify(request)
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Prediction failed')
    }

    return response.json()
  }

  static async deleteModel(
    modelId: string,
    token: string | null
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}`,
      {
        method: 'DELETE',
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      throw new Error('Failed to delete model')
    }
  }

  static async deactivateModel(
    modelId: string,
    token: string | null
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}/deactivate`,
      {
        method: 'PUT',
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      throw new Error('Failed to deactivate model')
    }
  }
}