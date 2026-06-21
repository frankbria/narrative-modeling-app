import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ModelVersions } from '@/components/ModelVersions'
import { ModelService } from '@/lib/services/model'
import type { ModelVersionListResponse } from '@/lib/types/evaluation'

jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('token'),
}))

jest.mock('@/lib/services/model', () => ({
  ModelService: {
    getModelVersions: jest.fn(),
    promoteModelVersion: jest.fn(),
    compareModels: jest.fn(),
  },
}))

const mockService = ModelService as jest.Mocked<typeof ModelService>

function makeVersions(): ModelVersionListResponse {
  return {
    model_id: 'v2',
    dataset_id: 'ds-1',
    name: 'Churn',
    total: 2,
    production_model_id: 'v2',
    versions: [
      {
        model_id: 'v1',
        version_number: 1,
        name: 'Churn',
        algorithm: 'Random Forest',
        problem_type: 'binary_classification',
        cv_score: 0.81,
        test_score: 0.79,
        is_production: false,
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        promoted_at: null,
        dataset_id: 'ds-1',
        dataset_version_id: 'dv-1',
        parent_model_id: null,
        feature_names: ['a', 'b'],
        environment_metadata: { python: '3.13' },
        version_notes: null,
      },
      {
        model_id: 'v2',
        version_number: 2,
        name: 'Churn',
        algorithm: 'XGBoost',
        problem_type: 'binary_classification',
        cv_score: 0.88,
        test_score: 0.86,
        is_production: true,
        is_active: true,
        created_at: '2026-02-01T00:00:00Z',
        promoted_at: '2026-02-02T00:00:00Z',
        dataset_id: 'ds-1',
        dataset_version_id: 'dv-2',
        parent_model_id: 'v1',
        feature_names: ['a', 'b', 'c'],
        environment_metadata: { python: '3.13' },
        version_notes: null,
      },
    ],
  }
}

describe('ModelVersions', () => {
  beforeEach(() => jest.clearAllMocks())

  it('renders the version family with a production badge', async () => {
    mockService.getModelVersions.mockResolvedValue(makeVersions())
    render(<ModelVersions modelId="v2" />)

    expect(await screen.findByText('Version History')).toBeInTheDocument()
    expect(screen.getByText('v1')).toBeInTheDocument()
    expect(screen.getByText('v2')).toBeInTheDocument()
    expect(screen.getByText('Production')).toBeInTheDocument()
    // Lineage: feature counts shown.
    expect(screen.getByText('Random Forest')).toBeInTheDocument()
  })

  it('promotes an older version (rollback) and refetches', async () => {
    mockService.getModelVersions.mockResolvedValue(makeVersions())
    mockService.promoteModelVersion.mockResolvedValue({
      model_id: 'v1',
      is_production: true,
      promoted_at: '2026-03-01T00:00:00Z',
      demoted_model_ids: ['v2'],
    })
    render(<ModelVersions modelId="v2" />)

    const promoteBtn = await screen.findByTestId('promote-v1')
    fireEvent.click(promoteBtn)

    await waitFor(() =>
      expect(mockService.promoteModelVersion).toHaveBeenCalledWith('v1', 'token')
    )
    // Reloads versions after promote (initial + post-promote).
    await waitFor(() =>
      expect(mockService.getModelVersions).toHaveBeenCalledTimes(2)
    )
  })

  it('compares 2 selected versions side by side', async () => {
    mockService.getModelVersions.mockResolvedValue(makeVersions())
    mockService.compareModels.mockResolvedValue({
      problem_type: 'binary_classification',
      dataset_id: 'ds-1',
      models: [
        { model_id: 'v1', name: 'Churn', algorithm: 'Random Forest', problem_type: 'binary_classification', cv_score: 0.81, test_score: 0.79, metrics: {}, created_at: null },
        { model_id: 'v2', name: 'Churn', algorithm: 'XGBoost', problem_type: 'binary_classification', cv_score: 0.88, test_score: 0.86, metrics: {}, created_at: null },
      ],
    })
    render(<ModelVersions modelId="v2" />)

    await screen.findByText('Version History')
    fireEvent.click(screen.getByLabelText('Select version 1'))
    fireEvent.click(screen.getByLabelText('Select version 2'))
    fireEvent.click(screen.getByTestId('compare-versions'))

    await waitFor(() =>
      expect(mockService.compareModels).toHaveBeenCalledWith(['v1', 'v2'], 'token')
    )
    expect(await screen.findByText('Side-by-side comparison')).toBeInTheDocument()
  })

  it('shows an error when loading fails', async () => {
    mockService.getModelVersions.mockRejectedValue(new Error('boom'))
    render(<ModelVersions modelId="v2" />)
    expect(await screen.findByText('boom')).toBeInTheDocument()
  })
})
