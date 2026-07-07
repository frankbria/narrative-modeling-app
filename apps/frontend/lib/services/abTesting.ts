/**
 * A/B Testing service for experiment management
 */

import { getAuthToken } from '@/lib/auth-helpers';

// Absolute backend base URL (includes /api/v1). A relative URL would resolve
// against the frontend origin, which has no rewrite to the backend (issue #262).
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface Variant {
  variant_id: string;
  model_id: string;
  name: string;
  description?: string;
  traffic_percentage: number;
  total_predictions: number;
  error_count: number;
  custom_metrics: Record<string, number>;
  status: 'active' | 'paused' | 'completed';
}

export interface ABTest {
  experiment_id: string;
  name: string;
  description?: string;
  status: 'draft' | 'running' | 'paused' | 'completed' | 'archived';
  variants: Variant[];
  primary_metric: string;
  secondary_metrics: string[];
  min_sample_size: number;
  confidence_level: number;
  test_duration_hours?: number;
  created_at: string;
  started_at?: string;
  ended_at?: string;
  winner_variant_id?: string;
  statistical_significance?: number;
  lift_percentage?: number;
}

export interface CreateExperimentRequest {
  name: string;
  description?: string;
  model_ids: string[];
  primary_metric: string;
  secondary_metrics?: string[];
  traffic_split?: number[];
  min_sample_size?: number;
  confidence_level?: number;
  test_duration_hours?: number;
}

export interface VariantAssignment {
  experiment_id: string;
  variant_id: string;
  variant_name: string;
  model_id: string;
}

export interface ExperimentMetrics {
  experiment_id: string;
  name: string;
  status: string;
  duration?: number;
  total_predictions: number;
  variants: Array<{
    variant_id: string;
    name: string;
    model_id: string;
    traffic_percentage: number;
    total_predictions: number;
    error_rate: number;
    avg_latency_ms: number;
    custom_metrics: Record<string, number>;
  }>;
  comparison?: {
    variant_a_rate: number;
    variant_b_rate: number;
    lift_percentage: number;
    p_value: number;
    is_significant: boolean;
    confidence_level: number;
  };
}

class ABTestingService {
  private baseUrl = `${API_BASE_URL}/ab-testing`;

  /** Build auth headers from the backend-verifiable NextAuth JWT (issue #262). */
  private async authHeaders(json = false): Promise<HeadersInit> {
    const token = await getAuthToken();
    return {
      ...(json && { 'Content-Type': 'application/json' }),
      ...(token && { Authorization: `Bearer ${token}` }),
    };
  }

  async createExperiment(request: CreateExperimentRequest): Promise<ABTest> {
    const response = await fetch(`${this.baseUrl}/experiments`, {
      method: 'POST',
      headers: await this.authHeaders(true),
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error('Failed to create experiment');
    }

    return response.json();
  }

  async listExperiments(status?: string): Promise<ABTest[]> {
    const url = new URL(`${this.baseUrl}/experiments`);
    if (status) {
      url.searchParams.append('status', status);
    }

    const response = await fetch(url.toString(), {
      headers: await this.authHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to list experiments');
    }

    return response.json();
  }

  async getExperiment(experimentId: string): Promise<ABTest> {
    const response = await fetch(`${this.baseUrl}/experiments/${experimentId}`, {
      headers: await this.authHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to get experiment');
    }

    return response.json();
  }

  async startExperiment(experimentId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/experiments/${experimentId}/start`, {
      method: 'POST',
      headers: await this.authHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to start experiment');
    }
  }

  async pauseExperiment(experimentId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/experiments/${experimentId}/pause`, {
      method: 'POST',
      headers: await this.authHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to pause experiment');
    }
  }

  async completeExperiment(experimentId: string): Promise<{
    winner_variant_id: string;
    statistical_significance: number;
    lift_percentage: number;
  }> {
    const response = await fetch(`${this.baseUrl}/experiments/${experimentId}/complete`, {
      method: 'POST',
      headers: await this.authHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to complete experiment');
    }

    return response.json();
  }

  async getVariantAssignment(experimentId: string, userIdentifier: string): Promise<VariantAssignment> {
    const url = new URL(`${this.baseUrl}/experiments/${experimentId}/assign-variant`);
    url.searchParams.append('user_identifier', userIdentifier);

    const response = await fetch(url.toString(), {
      headers: await this.authHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to get variant assignment');
    }

    return response.json();
  }

  async getExperimentMetrics(experimentId: string): Promise<ExperimentMetrics> {
    const response = await fetch(`${this.baseUrl}/experiments/${experimentId}/metrics`, {
      headers: await this.authHeaders(),
    });

    if (!response.ok) {
      throw new Error('Failed to get experiment metrics');
    }

    return response.json();
  }

  async trackPrediction(
    experimentId: string,
    variantId: string,
    latencyMs: number,
    success: boolean = true,
    customMetrics?: Record<string, number>
  ): Promise<void> {
    const response = await fetch(`${this.baseUrl}/track-prediction`, {
      method: 'POST',
      headers: await this.authHeaders(true),
      body: JSON.stringify({
        experiment_id: experimentId,
        variant_id: variantId,
        latency_ms: latencyMs,
        success,
        custom_metrics: customMetrics,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to track prediction');
    }
  }
}

export const abTestingService = new ABTestingService();