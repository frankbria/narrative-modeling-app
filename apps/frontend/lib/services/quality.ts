/**
 * Quality scoring API client (issue #102).
 */

import { getAuthToken } from '@/lib/auth-helpers'
import type {
  QualityReportResponse,
  QualityTrendResponse,
} from '@/lib/types/quality'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

async function authHeaders(): Promise<HeadersInit> {
  const token = await getAuthToken()
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  }
}

export const QualityService = {
  /** Consolidated quality report (score, components, recommendations, gates). */
  async getQualityReport(fileId: string): Promise<QualityReportResponse> {
    const response = await fetch(
      `${API_BASE_URL}/data/${encodeURIComponent(fileId)}/quality-report`,
      { headers: await authHeaders() }
    )
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(error.detail || 'Failed to load quality report')
    }
    return response.json()
  },

  /** Quality trend across dataset versions. Returns empty points when none exist. */
  async getQualityTrend(datasetId: string): Promise<QualityTrendResponse> {
    const response = await fetch(
      `${API_BASE_URL}/datasets/${encodeURIComponent(datasetId)}/quality-trend`,
      { headers: await authHeaders() }
    )
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(error.detail || 'Failed to load quality trend')
    }
    return response.json()
  },
}
