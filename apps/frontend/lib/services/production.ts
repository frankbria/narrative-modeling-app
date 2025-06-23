/**
 * Production API service for model deployment and API key management
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

export interface CreateAPIKeyRequest {
  name: string
  description?: string
  model_ids?: string[]
  rate_limit?: number
  expires_in_days?: number
}

export interface APIKeyResponse {
  key_id: string
  api_key: string
  name: string
  created_at: string
  expires_at?: string
  rate_limit: number
  model_ids: string[]
}

export interface APIKeyInfo {
  key_id: string
  name: string
  description?: string
  created_at: string
  expires_at?: string
  last_used_at?: string
  total_requests: number
  rate_limit: number
  is_active: boolean
}

export interface ModelMetrics {
  model_id: string
  model_name: string
  total_predictions: number
  avg_latency_ms: number
  predictions_per_hour: number
  avg_confidence: number
  error_rate: number
  time_window_hours: number
  last_prediction_at?: string
}

export interface UsageStats {
  total_models: number
  active_models: number
  total_predictions_24h: number
  total_api_keys: number
  active_api_keys: number
  models: Array<{
    model_id: string
    name: string
    is_active: boolean
    predictions_24h: number
    avg_latency_ms: number
    last_used_at?: string
  }>
}

export interface APIKeyUsage {
  api_key_id: string
  name: string
  total_requests: number
  requests_last_24h: number
  rate_limit: number
  usage_percentage: number
  models_accessed: string[]
}

export class ProductionService {
  private static async getHeaders(token: string | null): Promise<HeadersInit> {
    return {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` })
    }
  }

  // API Key Management
  static async createAPIKey(
    request: CreateAPIKeyRequest,
    token: string | null
  ): Promise<APIKeyResponse> {
    const response = await fetch(`${API_BASE_URL}/production/api-keys`, {
      method: 'POST',
      headers: await this.getHeaders(token),
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to create API key')
    }

    return response.json()
  }

  static async listAPIKeys(token: string | null): Promise<APIKeyInfo[]> {
    const response = await fetch(`${API_BASE_URL}/production/api-keys`, {
      headers: await this.getHeaders(token)
    })

    if (!response.ok) {
      throw new Error('Failed to fetch API keys')
    }

    return response.json()
  }

  static async revokeAPIKey(keyId: string, token: string | null): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/production/api-keys/${keyId}`, {
      method: 'DELETE',
      headers: await this.getHeaders(token)
    })

    if (!response.ok) {
      throw new Error('Failed to revoke API key')
    }
  }

  // Monitoring
  static async getModelMetrics(
    modelId: string,
    hours: number,
    token: string | null
  ): Promise<ModelMetrics> {
    const response = await fetch(
      `${API_BASE_URL}/monitoring/models/${modelId}/metrics?hours=${hours}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      throw new Error('Failed to fetch model metrics')
    }

    return response.json()
  }

  static async getUsageOverview(token: string | null): Promise<UsageStats> {
    const response = await fetch(`${API_BASE_URL}/monitoring/overview`, {
      headers: await this.getHeaders(token)
    })

    if (!response.ok) {
      throw new Error('Failed to fetch usage overview')
    }

    return response.json()
  }

  static async getAPIKeyUsage(token: string | null): Promise<APIKeyUsage[]> {
    const response = await fetch(`${API_BASE_URL}/monitoring/api-keys/usage`, {
      headers: await this.getHeaders(token)
    })

    if (!response.ok) {
      throw new Error('Failed to fetch API key usage')
    }

    return response.json()
  }

  static async getPredictionLogs(
    modelId: string,
    limit: number,
    token: string | null
  ): Promise<{
    model_id: string
    logs: Array<{
      prediction_id: string
      timestamp: string
      prediction: any
      probability?: number
      latency_ms: number
      api_key_id?: string
    }>
    count: number
    limit: number
  }> {
    const response = await fetch(
      `${API_BASE_URL}/monitoring/models/${modelId}/logs?limit=${limit}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      throw new Error('Failed to fetch prediction logs')
    }

    return response.json()
  }

  static async getPredictionDistribution(
    modelId: string,
    hours: number,
    token: string | null
  ): Promise<{
    model_id: string
    distribution: Record<string, number>
    total: number
    unique_values: number
    most_common?: string
    least_common?: string
  }> {
    const response = await fetch(
      `${API_BASE_URL}/monitoring/models/${modelId}/distribution?hours=${hours}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      throw new Error('Failed to fetch prediction distribution')
    }

    return response.json()
  }
}