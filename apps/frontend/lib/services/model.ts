/**
 * Model training and management service
 */

import { getAuthToken } from '@/lib/auth-helpers'

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
  version?: string | number
}

export interface ModelComparisonEntry {
  algorithm: string
  cv_score?: number | null
  test_score?: number | null
  training_time?: number | null
}

export interface AlgorithmRecommendation {
  algorithm_name: string
  priority: number
  expected_performance: string
  training_time_estimate: string
  interpretability_score: number
  explanation: string
  pros: string[]
  cons: string[]
}

export type TrainingJobStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface TrainingStatus {
  model_id: string
  status: TrainingJobStatus
  progress: number // 0.0 - 1.0
  current_algorithm?: string | null
  completed_algorithms: number
  total_algorithms: number
  metrics: Record<string, unknown>
  model_comparison: ModelComparisonEntry[]
  algorithm_recommendations: AlgorithmRecommendation[]
  best_model_id?: string | null
  best_algorithm?: string | null
  explanation?: string | null
  error?: string | null
  current_stage?: string | null
  elapsed_seconds?: number | null
  estimated_remaining_seconds?: number | null
  cancellation_requested?: boolean
}

export interface TrainingJobSummary {
  model_id: string
  dataset_id: string
  target_column: string
  status: TrainingJobStatus
  progress_percentage: number // 0 - 100
  current_stage: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  best_algorithm: string | null
  best_score: number | null
  elapsed_seconds: number | null
}

export interface TrainingJobListResponse {
  jobs: TrainingJobSummary[]
  total_count: number
  limit: number
  skip: number
}

export interface ListTrainingJobsOptions {
  status?: TrainingJobStatus
  limit?: number
  skip?: number
}

export interface TrainingLogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error'
  message: string
  stage?: string | null
}

export interface TrainingLogsResponse {
  model_id: string
  logs: TrainingLogEntry[]
  total_count: number
  has_more: boolean
}

export interface GetTrainingLogsOptions {
  level?: 'info' | 'warning' | 'error'
  limit?: number
  skip?: number
}

export interface CancelTrainingResponse {
  model_id: string
  status: TrainingJobStatus
  cancellation_requested: boolean
  message: string
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

  /**
   * Fetch the status and results of an async training job.
   *
   * @param modelId - The id returned by {@link trainModel}.
   * @param token - Bearer token, or `null` to omit the Authorization header.
   * @returns The job status: progress while running; comparison, best model,
   *   explanation and recommendations when completed; or the error when failed.
   * @throws Error with the backend `detail` message on a non-OK response.
   */
  static async getTrainingStatus(
    modelId: string,
    token: string | null
  ): Promise<TrainingStatus> {
    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}/status`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to fetch training status')
    }

    return response.json()
  }

  /**
   * List training jobs for the current user, newest first.
   *
   * @param options - Optional `status` filter plus `limit`/`skip` pagination.
   * @param token - Bearer token, or `null` to omit the Authorization header.
   * @throws Error with the backend `detail` message on a non-OK response.
   */
  static async listTrainingJobs(
    options: ListTrainingJobsOptions | undefined,
    token: string | null
  ): Promise<TrainingJobListResponse> {
    const params = new URLSearchParams()
    if (options?.status) params.append('status', options.status)
    if (options?.limit !== undefined) params.append('limit', String(options.limit))
    if (options?.skip !== undefined) params.append('skip', String(options.skip))
    const query = params.toString()

    const response = await fetch(
      `${API_BASE_URL}/ml/jobs${query ? `?${query}` : ''}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to fetch training jobs')
    }

    return response.json()
  }

  /**
   * Fetch the persisted log entries for a training job, oldest first.
   *
   * @param modelId - The id returned by {@link trainModel}.
   * @param options - Optional `level` filter plus `limit`/`skip` pagination.
   * @param token - Bearer token, or `null` to omit the Authorization header.
   * @throws Error with the backend `detail` message on a non-OK response.
   */
  static async getTrainingLogs(
    modelId: string,
    options: GetTrainingLogsOptions | undefined,
    token: string | null
  ): Promise<TrainingLogsResponse> {
    const params = new URLSearchParams()
    if (options?.level) params.append('level', options.level)
    if (options?.limit !== undefined) params.append('limit', String(options.limit))
    if (options?.skip !== undefined) params.append('skip', String(options.skip))
    const query = params.toString()

    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}/logs${query ? `?${query}` : ''}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to fetch training logs')
    }

    return response.json()
  }

  /**
   * Request cancellation of a running training job. The current algorithm
   * finishes before the job stops.
   *
   * @param modelId - The id returned by {@link trainModel}.
   * @param token - Bearer token, or `null` to omit the Authorization header.
   * @throws Error with the backend `detail` message on a non-OK response
   *   (404 unknown job, 409 already terminal).
   */
  static async cancelTraining(
    modelId: string,
    token: string | null
  ): Promise<CancelTrainingResponse> {
    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}/cancel`,
      {
        method: 'POST',
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to cancel training')
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

/**
 * Instance-style facade over {@link ModelService} that resolves the auth token
 * automatically, matching the convention used by the other client services
 * (e.g. {@link abTestingService}).
 */
class ModelServiceClient {
  async listModels(datasetId?: string): Promise<ModelInfo[]> {
    const token = await getAuthToken()
    return ModelService.listModels(token, datasetId)
  }

  async getModel(modelId: string): Promise<ModelInfo> {
    const token = await getAuthToken()
    return ModelService.getModel(modelId, token)
  }

  /** Resolve the auth token automatically and fetch a training job's status. */
  async getTrainingStatus(modelId: string): Promise<TrainingStatus> {
    const token = await getAuthToken()
    return ModelService.getTrainingStatus(modelId, token)
  }

  /** Resolve the auth token automatically and list training jobs. */
  async listTrainingJobs(
    options?: ListTrainingJobsOptions
  ): Promise<TrainingJobListResponse> {
    const token = await getAuthToken()
    return ModelService.listTrainingJobs(options, token)
  }

  /** Resolve the auth token automatically and fetch a job's log entries. */
  async getTrainingLogs(
    modelId: string,
    options?: GetTrainingLogsOptions
  ): Promise<TrainingLogsResponse> {
    const token = await getAuthToken()
    return ModelService.getTrainingLogs(modelId, options, token)
  }

  /** Resolve the auth token automatically and request job cancellation. */
  async cancelTraining(modelId: string): Promise<CancelTrainingResponse> {
    const token = await getAuthToken()
    return ModelService.cancelTraining(modelId, token)
  }

  async trainModel(
    request: TrainModelRequest
  ): Promise<{ model_id: string; status: string; message: string }> {
    const token = await getAuthToken()
    return ModelService.trainModel(request, token)
  }

  async predict(
    modelId: string,
    request: PredictRequest
  ): Promise<PredictResponse> {
    const token = await getAuthToken()
    return ModelService.predict(modelId, request, token)
  }

  async deleteModel(modelId: string): Promise<void> {
    const token = await getAuthToken()
    return ModelService.deleteModel(modelId, token)
  }

  async deactivateModel(modelId: string): Promise<void> {
    const token = await getAuthToken()
    return ModelService.deactivateModel(modelId, token)
  }
}

export const modelService = new ModelServiceClient()
