/**
 * Model training and management service
 */

import { getAuthToken } from '@/lib/auth-helpers'
import type {
  ModelComparisonResponse,
  ModelEvaluationResponse,
  ModelVersionListResponse,
  PromoteVersionResponse,
  ShapSummaryResponse
} from '@/lib/types/evaluation'

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
  /** Single status, or a comma-separated list (e.g. 'completed,failed,cancelled'). */
  status?: TrainingJobStatus | string
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
  /** Request per-prediction feature-contribution breakdowns (#83). */
  include_explanations?: boolean
}

/** A single feature's contribution to a prediction (#83). */
export interface FeatureContribution {
  feature_name: string
  /** Signed contribution; positive raises the prediction. */
  contribution: number
  feature_value?: number | null
}

/** Per-prediction, model-native explanation (no SHAP — see #80/#83). */
export interface PredictionExplanation {
  top_features: FeatureContribution[]
  explanation_text: string
  /** linear_coefficients | tree_importance | stored_importance */
  method: string
}

export interface PredictResponse {
  predictions: any[]
  probabilities?: number[][]
  /** Per-record confidence (max class probability) for classification (#82). */
  confidence?: number[]
  /** Ordered class labels matching each probability vector (#82). */
  class_labels?: string[]
  feature_names: string[]
  model_info: {
    model_id: string
    algorithm: string
    problem_type: string
    target_column: string
  }
  /** Per-record low-confidence warning flags (#83). */
  low_confidence?: boolean[]
  /** Whether the model yields calibrated probabilities (#83). */
  is_calibrated?: boolean
  calibration_method?: string | null
  /** Threshold below which a prediction is flagged low-confidence (#83). */
  confidence_threshold?: number
  /** Symmetric regression prediction intervals [low, high] per record (#83). */
  prediction_intervals?: (number[] | null)[]
  /** Per-record explanations, present when include_explanations was set (#83). */
  explanations?: (PredictionExplanation | null)[]
}

/** A raw input feature the prediction form must collect (#82). */
export interface ModelFeatureDescriptor {
  name: string
  /** "number" for numeric inputs, "categorical" for a constrained choice. */
  type: string
  /** Allowed values for a categorical feature, when recoverable. */
  options?: string[] | null
}

/** Input schema used to auto-generate the single-prediction form (#82). */
export interface ModelFeaturesResponse {
  features: ModelFeatureDescriptor[]
  class_labels?: string[] | null
  problem_type: string
  target_column: string
}

/** Options for creating a batch prediction job (#82). */
export interface CreateBatchJobOptions {
  output_format?: 'csv' | 'json'
  include_probabilities?: boolean
  include_metadata?: boolean
  chunk_size?: number
}

/** A batch prediction job record returned by the batch endpoints (#82). */
export interface BatchJobResponse {
  job_id: string
  job_type: string
  status: string
  progress: Record<string, any>
  config: Record<string, any>
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  duration_seconds?: number | null
  error_message?: string | null
  results: Record<string, any>
  input_size_bytes?: number | null
  output_path?: string | null
}

/** Real-time batch job progress (#82). */
export interface BatchJobProgressResponse {
  job_id: string
  status: string
  percentage_complete: number
  processed_records: number
  total_records: number
  success_count: number
  error_count: number
  success_rate: number
  current_chunk: number
  total_chunks: number
  estimated_completion?: string | null
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

  /**
   * Fetch the full evaluation artifacts for a trained model (issue #79):
   * metrics, confusion matrix, ROC/PR curves, feature importance and the
   * AI-generated explanation. `partial: true` responses carry only the
   * scalar metrics stored at training time.
   *
   * @param modelId - The id returned by {@link trainModel}.
   * @param token - Bearer token, or `null` to omit the Authorization header.
   * @throws Error with the backend `detail` message on a non-OK response.
   */
  static async getEvaluation(
    modelId: string,
    token: string | null
  ): Promise<ModelEvaluationResponse> {
    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}/evaluation`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to fetch model evaluation')
    }

    return response.json()
  }

  /**
   * Compare 2-5 models trained on the same dataset (issue #79).
   *
   * @param modelIds - Ids of the models to compare.
   * @param token - Bearer token, or `null` to omit the Authorization header.
   * @throws Error with the backend `detail` message on a non-OK response.
   */
  static async compareModels(
    modelIds: string[],
    token: string | null
  ): Promise<ModelComparisonResponse> {
    const response = await fetch(
      `${API_BASE_URL}/ml/compare`,
      {
        method: 'POST',
        headers: await this.getHeaders(token),
        body: JSON.stringify({ model_ids: modelIds })
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to compare models')
    }

    return response.json()
  }

  /**
   * List a model's version history (issue #78). A version family is every model
   * trained on the same dataset under the same name, ordered oldest → newest.
   *
   * @throws Error with the backend `detail` message on a non-OK response.
   */
  static async getModelVersions(
    modelId: string,
    token: string | null
  ): Promise<ModelVersionListResponse> {
    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}/versions`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to fetch model versions')
    }

    return response.json()
  }

  /**
   * Promote a version to production, demoting its siblings (issue #78).
   * Rolling back is the same call applied to an older version.
   *
   * @throws Error with the backend `detail` message on a non-OK response.
   */
  static async promoteModelVersion(
    modelId: string,
    token: string | null
  ): Promise<PromoteVersionResponse> {
    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}/promote`,
      {
        method: 'POST',
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to promote model version')
    }

    return response.json()
  }

  /**
   * Fetch the SHAP summary (mean |SHAP| per feature + plain-language drivers)
   * for a model (issue #80). Degrades to `partial: true` for models trained
   * before #80 or whose algorithm isn't SHAP-supported.
   *
   * @throws Error with the backend `detail` message on a non-OK response.
   */
  static async getShapSummary(
    modelId: string,
    token: string | null
  ): Promise<ShapSummaryResponse> {
    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}/shap`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to fetch SHAP summary')
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

  /** Fetch the raw input feature schema for the prediction form (#82). */
  static async getModelFeatures(
    modelId: string,
    token: string | null
  ): Promise<ModelFeaturesResponse> {
    const response = await fetch(
      `${API_BASE_URL}/ml/${modelId}/features`,
      {
        method: 'GET',
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to load model features')
    }

    return response.json()
  }

  /** Create a batch prediction job from an uploaded CSV file (#82). */
  static async createBatchJob(
    modelId: string,
    file: File,
    options: CreateBatchJobOptions,
    token: string | null
  ): Promise<BatchJobResponse> {
    const form = new FormData()
    form.append('file', file)
    form.append('model_id', modelId)
    form.append('output_format', options.output_format ?? 'csv')
    form.append(
      'include_probabilities',
      String(options.include_probabilities ?? true)
    )
    form.append('include_metadata', String(options.include_metadata ?? false))
    if (options.chunk_size != null) {
      form.append('chunk_size', String(options.chunk_size))
    }

    // Note: no Content-Type header — the browser sets the multipart boundary.
    const response = await fetch(`${API_BASE_URL}/batch/jobs`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to create batch job')
    }

    return response.json()
  }

  /** Fetch a batch job's full record (#82). */
  static async getBatchJob(
    jobId: string,
    token: string | null
  ): Promise<BatchJobResponse> {
    const response = await fetch(`${API_BASE_URL}/batch/jobs/${jobId}`, {
      method: 'GET',
      headers: await this.getHeaders(token)
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to fetch batch job')
    }

    return response.json()
  }

  /** Poll a batch job's real-time progress (#82). */
  static async getBatchJobProgress(
    jobId: string,
    token: string | null
  ): Promise<BatchJobProgressResponse> {
    const response = await fetch(
      `${API_BASE_URL}/batch/jobs/${jobId}/progress`,
      {
        method: 'GET',
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to fetch batch progress')
    }

    return response.json()
  }

  /** Download a completed batch job's results as a Blob (#82). */
  static async downloadBatchResults(
    jobId: string,
    token: string | null
  ): Promise<Blob> {
    const response = await fetch(
      `${API_BASE_URL}/batch/jobs/${jobId}/download`,
      {
        method: 'GET',
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to download batch results')
    }

    return response.blob()
  }

  /** Cancel a pending or running batch job (#82). */
  static async cancelBatchJob(
    jobId: string,
    token: string | null
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/batch/jobs/${jobId}/cancel`,
      {
        method: 'POST',
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'Failed to cancel batch job')
    }
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

  /** Resolve the auth token automatically and fetch a model's evaluation. */
  async getEvaluation(modelId: string): Promise<ModelEvaluationResponse> {
    const token = await getAuthToken()
    return ModelService.getEvaluation(modelId, token)
  }

  /** Resolve the auth token automatically and compare models. */
  async compareModels(modelIds: string[]): Promise<ModelComparisonResponse> {
    const token = await getAuthToken()
    return ModelService.compareModels(modelIds, token)
  }

  /** Resolve the auth token automatically and fetch a model's SHAP summary. */
  async getShapSummary(modelId: string): Promise<ShapSummaryResponse> {
    const token = await getAuthToken()
    return ModelService.getShapSummary(modelId, token)
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

  /** Resolve the auth token automatically and fetch the input feature schema. */
  async getModelFeatures(modelId: string): Promise<ModelFeaturesResponse> {
    const token = await getAuthToken()
    return ModelService.getModelFeatures(modelId, token)
  }

  /** Resolve the auth token automatically and create a batch prediction job. */
  async createBatchJob(
    modelId: string,
    file: File,
    options: CreateBatchJobOptions = {}
  ): Promise<BatchJobResponse> {
    const token = await getAuthToken()
    return ModelService.createBatchJob(modelId, file, options, token)
  }

  /** Resolve the auth token automatically and fetch a batch job. */
  async getBatchJob(jobId: string): Promise<BatchJobResponse> {
    const token = await getAuthToken()
    return ModelService.getBatchJob(jobId, token)
  }

  /** Resolve the auth token automatically and poll batch job progress. */
  async getBatchJobProgress(jobId: string): Promise<BatchJobProgressResponse> {
    const token = await getAuthToken()
    return ModelService.getBatchJobProgress(jobId, token)
  }

  /** Resolve the auth token automatically and download batch results. */
  async downloadBatchResults(jobId: string): Promise<Blob> {
    const token = await getAuthToken()
    return ModelService.downloadBatchResults(jobId, token)
  }

  /** Resolve the auth token automatically and cancel a batch job. */
  async cancelBatchJob(jobId: string): Promise<void> {
    const token = await getAuthToken()
    return ModelService.cancelBatchJob(jobId, token)
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
