'use client'

import { useState, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import {
  DataIssuesService,
  DataIssue,
  DetectionSummary,
  DetectionOptions,
  FixPreviewResponse,
  FixApplicationResponse,
  BatchFixResponse,
} from '@/lib/services/data-issues'

interface UseDataIssuesState {
  issues: DataIssue[]
  summary: DetectionSummary | null
  selectedIssues: Set<string>
  isLoading: boolean
  isDetecting: boolean
  isApplying: boolean
  error: string | null
  recordId: string | null
}

interface UseDataIssuesReturn extends UseDataIssuesState {
  detectIssues: (options?: DetectionOptions) => Promise<void>
  refreshIssues: () => Promise<void>
  selectIssue: (issueId: string) => void
  deselectIssue: (issueId: string) => void
  selectAllIssues: () => void
  clearSelection: () => void
  previewFix: (issueId: string, fixId?: string) => Promise<FixPreviewResponse | null>
  applyFix: (issueId: string, fixId?: string) => Promise<FixApplicationResponse | null>
  batchApplyFixes: (autoSafeOnly?: boolean) => Promise<BatchFixResponse | null>
  getIssuesByType: (type: string) => DataIssue[]
  getIssuesBySeverity: (severity: string) => DataIssue[]
  getAutoFixableIssues: () => DataIssue[]
  clearError: () => void
}

export function useDataIssues(datasetId: string): UseDataIssuesReturn {
  const { data: session } = useSession()
  const token = (session as any)?.accessToken || null

  const [state, setState] = useState<UseDataIssuesState>({
    issues: [],
    summary: null,
    selectedIssues: new Set(),
    isLoading: false,
    isDetecting: false,
    isApplying: false,
    error: null,
    recordId: null,
  })

  const detectIssues = useCallback(async (options: DetectionOptions = {}) => {
    setState(prev => ({ ...prev, isDetecting: true, error: null }))

    try {
      const response = await DataIssuesService.detectIssues(datasetId, options, token)

      if (response.success) {
        setState(prev => ({
          ...prev,
          issues: response.issues,
          summary: response.summary,
          recordId: response.record_id || null,
          isDetecting: false,
          selectedIssues: new Set(),
        }))
      } else {
        setState(prev => ({
          ...prev,
          error: response.error || 'Detection failed',
          isDetecting: false,
        }))
      }
    } catch (err) {
      setState(prev => ({
        ...prev,
        error: err instanceof Error ? err.message : 'Detection failed',
        isDetecting: false,
      }))
    }
  }, [datasetId, token])

  const refreshIssues = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true, error: null }))

    try {
      const response = await DataIssuesService.getDatasetIssues(datasetId, token)

      if (response.success) {
        setState(prev => ({
          ...prev,
          issues: response.issues,
          summary: response.summary,
          recordId: response.record_id || null,
          isLoading: false,
        }))
      } else {
        setState(prev => ({
          ...prev,
          error: response.error || 'Failed to load issues',
          isLoading: false,
        }))
      }
    } catch (err) {
      // Might not have any cached results yet
      setState(prev => ({
        ...prev,
        isLoading: false,
      }))
    }
  }, [datasetId, token])

  const selectIssue = useCallback((issueId: string) => {
    setState(prev => {
      const newSelected = new Set(prev.selectedIssues)
      newSelected.add(issueId)
      return { ...prev, selectedIssues: newSelected }
    })
  }, [])

  const deselectIssue = useCallback((issueId: string) => {
    setState(prev => {
      const newSelected = new Set(prev.selectedIssues)
      newSelected.delete(issueId)
      return { ...prev, selectedIssues: newSelected }
    })
  }, [])

  const selectAllIssues = useCallback(() => {
    setState(prev => ({
      ...prev,
      selectedIssues: new Set(prev.issues.map(i => i.issue_id))
    }))
  }, [])

  const clearSelection = useCallback(() => {
    setState(prev => ({ ...prev, selectedIssues: new Set() }))
  }, [])

  const previewFix = useCallback(async (
    issueId: string,
    fixId?: string
  ): Promise<FixPreviewResponse | null> => {
    setState(prev => ({ ...prev, isLoading: true, error: null }))

    try {
      const response = await DataIssuesService.previewFix(
        datasetId,
        issueId,
        token,
        fixId
      )

      setState(prev => ({ ...prev, isLoading: false }))
      return response
    } catch (err) {
      setState(prev => ({
        ...prev,
        error: err instanceof Error ? err.message : 'Preview failed',
        isLoading: false,
      }))
      return null
    }
  }, [datasetId, token])

  const applyFix = useCallback(async (
    issueId: string,
    fixId?: string
  ): Promise<FixApplicationResponse | null> => {
    setState(prev => ({ ...prev, isApplying: true, error: null }))

    try {
      const response = await DataIssuesService.applyFix(
        datasetId,
        issueId,
        token,
        { fixId }
      )

      if (response.success) {
        // Remove the fixed issue from the list
        setState(prev => ({
          ...prev,
          issues: prev.issues.filter(i => i.issue_id !== issueId),
          selectedIssues: (() => {
            const newSelected = new Set(prev.selectedIssues)
            newSelected.delete(issueId)
            return newSelected
          })(),
          isApplying: false,
        }))
      } else {
        setState(prev => ({
          ...prev,
          error: response.error || 'Apply failed',
          isApplying: false,
        }))
      }

      return response
    } catch (err) {
      setState(prev => ({
        ...prev,
        error: err instanceof Error ? err.message : 'Apply failed',
        isApplying: false,
      }))
      return null
    }
  }, [datasetId, token])

  const batchApplyFixes = useCallback(async (
    autoSafeOnly: boolean = false
  ): Promise<BatchFixResponse | null> => {
    if (state.selectedIssues.size === 0) {
      setState(prev => ({ ...prev, error: 'No issues selected' }))
      return null
    }

    setState(prev => ({ ...prev, isApplying: true, error: null }))

    try {
      const response = await DataIssuesService.batchApplyFixes(
        datasetId,
        Array.from(state.selectedIssues),
        token,
        { autoApplySafe: autoSafeOnly }
      )

      if (response.success) {
        // Remove fixed issues from the list
        const fixedIds = new Set(
          response.results
            .filter(r => r.success)
            .map(r => r.issue_id)
        )

        setState(prev => ({
          ...prev,
          issues: prev.issues.filter(i => !fixedIds.has(i.issue_id)),
          selectedIssues: new Set(),
          isApplying: false,
        }))
      } else {
        setState(prev => ({
          ...prev,
          error: response.error || 'Batch fix failed',
          isApplying: false,
        }))
      }

      return response
    } catch (err) {
      setState(prev => ({
        ...prev,
        error: err instanceof Error ? err.message : 'Batch fix failed',
        isApplying: false,
      }))
      return null
    }
  }, [datasetId, token, state.selectedIssues])

  const getIssuesByType = useCallback((type: string): DataIssue[] => {
    return state.issues.filter(i => i.issue_type === type)
  }, [state.issues])

  const getIssuesBySeverity = useCallback((severity: string): DataIssue[] => {
    return state.issues.filter(i => i.severity === severity)
  }, [state.issues])

  const getAutoFixableIssues = useCallback((): DataIssue[] => {
    return state.issues.filter(i =>
      i.suggested_fixes.some(f => f.is_safe)
    )
  }, [state.issues])

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }))
  }, [])

  return {
    ...state,
    detectIssues,
    refreshIssues,
    selectIssue,
    deselectIssue,
    selectAllIssues,
    clearSelection,
    previewFix,
    applyFix,
    batchApplyFixes,
    getIssuesByType,
    getIssuesBySeverity,
    getAutoFixableIssues,
    clearError,
  }
}
