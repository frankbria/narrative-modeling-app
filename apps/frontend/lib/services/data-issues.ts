/**
 * Data Issues API service for issue detection and fix suggestions
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

// Types

export interface DetectionOptions {
  include_ai_analysis?: boolean
  check_missing_values?: boolean
  check_duplicates?: boolean
  check_outliers?: boolean
  check_inconsistencies?: boolean
  check_type_mismatches?: boolean
  outlier_method?: 'iqr' | 'zscore'
  outlier_threshold?: number
  columns?: string[]
  sample_size?: number
}

export interface SuggestedFix {
  fix_id: string
  transformation_type: string
  parameters: Record<string, any>
  explanation: string
  ai_generated: boolean
  confidence_score: number
  estimated_rows_affected: number
  estimated_data_loss: number
  is_safe: boolean
}

export interface DataIssue {
  issue_id: string
  issue_type: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  affected_column: string | null
  affected_columns: string[]
  affected_rows: number
  affected_percentage: number
  description: string
  impact: string
  suggested_fixes: SuggestedFix[]
  ai_generated: boolean
  ai_explanation: string | null
  detected_at: string
  example_values: any[]
}

export interface DetectionSummary {
  total_issues: number
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  ai_detected_count: number
  auto_fixable_count: number
  detection_time_ms: number
  columns_analyzed: number
  rows_analyzed: number
}

export interface IssueDetectionResponse {
  success: boolean
  dataset_id: string
  issues: DataIssue[]
  summary: DetectionSummary
  record_id?: string
  error?: string
}

export interface FixPreviewResponse {
  success: boolean
  issue_id: string
  fix_id: string
  preview_data_before?: Record<string, any>[]
  preview_data_after?: Record<string, any>[]
  affected_rows: number
  affected_columns: string[]
  estimated_data_loss: number
  warnings: string[]
  error?: string
}

export interface FixApplicationResponse {
  success: boolean
  dataset_id: string
  issue_id: string
  fix_id: string
  transformation_id?: string
  affected_rows: number
  affected_columns: string[]
  execution_time_ms: number
  new_version_id?: string
  error?: string
  warnings: string[]
}

export interface BatchFixResult {
  issue_id: string
  fix_id: string
  success: boolean
  affected_rows: number
  error?: string
}

export interface BatchFixResponse {
  success: boolean
  dataset_id: string
  total_fixes: number
  successful_fixes: number
  failed_fixes: number
  results: BatchFixResult[]
  total_rows_affected: number
  execution_time_ms: number
  new_version_id?: string
  error?: string
  warnings: string[]
}

export interface IssueHistoryRecord {
  record_id: string
  dataset_id: string
  detected_at: string
  summary: DetectionSummary
  issues_count: number
  applied_fixes_count: number
}

export interface IssueHistoryListResponse {
  records: IssueHistoryRecord[]
  total: number
  page: number
  per_page: number
}

// API Service Class

export class DataIssuesService {
  private static async getHeaders(token: string | null): Promise<HeadersInit> {
    return {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` })
    }
  }

  /**
   * Detect data quality issues in a dataset
   */
  static async detectIssues(
    datasetId: string,
    options: DetectionOptions = {},
    token: string | null
  ): Promise<IssueDetectionResponse> {
    const response = await fetch(`${API_BASE_URL}/data-issues/detect`, {
      method: 'POST',
      headers: await this.getHeaders(token),
      body: JSON.stringify({
        dataset_id: datasetId,
        options
      })
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Detection failed' }))
      throw new Error(error.detail || 'Issue detection failed')
    }

    return response.json()
  }

  /**
   * Get cached detection results for a dataset
   */
  static async getDatasetIssues(
    datasetId: string,
    token: string | null,
    options?: {
      includeAi?: boolean
      severity?: 'critical' | 'high' | 'medium' | 'low'
    }
  ): Promise<IssueDetectionResponse> {
    const params = new URLSearchParams()
    if (options?.includeAi !== undefined) {
      params.append('include_ai', options.includeAi.toString())
    }
    if (options?.severity) {
      params.append('severity', options.severity)
    }

    const response = await fetch(
      `${API_BASE_URL}/data-issues/${datasetId}/issues?${params}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to get issues' }))
      throw new Error(error.detail || 'Failed to get issues')
    }

    return response.json()
  }

  /**
   * Preview a suggested fix before applying
   */
  static async previewFix(
    datasetId: string,
    issueId: string,
    token: string | null,
    fixId?: string,
    previewRows: number = 100
  ): Promise<FixPreviewResponse> {
    const response = await fetch(`${API_BASE_URL}/data-issues/preview-fix`, {
      method: 'POST',
      headers: await this.getHeaders(token),
      body: JSON.stringify({
        dataset_id: datasetId,
        issue_id: issueId,
        fix_id: fixId,
        preview_rows: previewRows
      })
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Preview failed' }))
      throw new Error(error.detail || 'Fix preview failed')
    }

    return response.json()
  }

  /**
   * Apply a fix to resolve an issue
   */
  static async applyFix(
    datasetId: string,
    issueId: string,
    token: string | null,
    options?: {
      fixId?: string
      previewMode?: boolean
      saveAsNewVersion?: boolean
    }
  ): Promise<FixApplicationResponse> {
    const response = await fetch(`${API_BASE_URL}/data-issues/apply-fix`, {
      method: 'POST',
      headers: await this.getHeaders(token),
      body: JSON.stringify({
        dataset_id: datasetId,
        issue_id: issueId,
        fix_id: options?.fixId,
        preview_mode: options?.previewMode ?? false,
        save_as_new_version: options?.saveAsNewVersion ?? true
      })
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Apply failed' }))
      throw new Error(error.detail || 'Apply fix failed')
    }

    return response.json()
  }

  /**
   * Apply multiple fixes in batch
   */
  static async batchApplyFixes(
    datasetId: string,
    issueIds: string[],
    token: string | null,
    options?: {
      autoApplySafe?: boolean
      stopOnError?: boolean
      previewMode?: boolean
    }
  ): Promise<BatchFixResponse> {
    const response = await fetch(`${API_BASE_URL}/data-issues/batch-fix`, {
      method: 'POST',
      headers: await this.getHeaders(token),
      body: JSON.stringify({
        dataset_id: datasetId,
        issue_ids: issueIds,
        auto_apply_safe: options?.autoApplySafe ?? false,
        stop_on_error: options?.stopOnError ?? true,
        preview_mode: options?.previewMode ?? false
      })
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Batch fix failed' }))
      throw new Error(error.detail || 'Batch fix failed')
    }

    return response.json()
  }

  /**
   * Get issue detection history for a dataset
   */
  static async getIssueHistory(
    datasetId: string,
    token: string | null,
    page: number = 1,
    perPage: number = 20
  ): Promise<IssueHistoryListResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      per_page: perPage.toString()
    })

    const response = await fetch(
      `${API_BASE_URL}/data-issues/${datasetId}/history?${params}`,
      {
        headers: await this.getHeaders(token)
      }
    )

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to get history' }))
      throw new Error(error.detail || 'Failed to get history')
    }

    return response.json()
  }
}

// Utility functions

export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'text-red-700 bg-red-100'
    case 'high':
      return 'text-orange-700 bg-orange-100'
    case 'medium':
      return 'text-yellow-700 bg-yellow-100'
    case 'low':
      return 'text-blue-700 bg-blue-100'
    default:
      return 'text-gray-700 bg-gray-100'
  }
}

export function getSeverityBadgeVariant(severity: string): 'destructive' | 'secondary' | 'outline' | 'default' {
  switch (severity) {
    case 'critical':
      return 'destructive'
    case 'high':
      return 'destructive'
    case 'medium':
      return 'secondary'
    case 'low':
      return 'outline'
    default:
      return 'default'
  }
}

export function getIssueTypeLabel(issueType: string): string {
  const labels: Record<string, string> = {
    missing_values: 'Missing Values',
    outliers: 'Outliers',
    inconsistent_format: 'Inconsistent Format',
    duplicates: 'Duplicates',
    invalid_values: 'Invalid Values',
    type_mismatch: 'Type Mismatch',
    inconsistent_casing: 'Inconsistent Casing',
    whitespace_issues: 'Whitespace Issues',
    date_format_issues: 'Date Format Issues',
    numeric_string_mismatch: 'Numeric/String Mismatch'
  }
  return labels[issueType] || issueType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}
