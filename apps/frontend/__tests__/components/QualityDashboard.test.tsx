import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { QualityDashboard } from '@/components/quality/QualityDashboard'
import { QualityService } from '@/lib/services/quality'
import type { QualityReportResponse, QualityTrendResponse } from '@/lib/types/quality'

jest.mock('@/lib/services/quality', () => ({
  QualityService: {
    getQualityReport: jest.fn(),
    getQualityTrend: jest.fn(),
  },
}))

// LineChart pulls in recharts — stub it so the test stays a unit test.
jest.mock('@/components/LineChart', () => ({
  LineChart: () => <div data-testid="line-chart" />,
}))

const mockService = QualityService as jest.Mocked<typeof QualityService>

function makeReport(overrides: Partial<QualityReportResponse> = {}): QualityReportResponse {
  return {
    file_id: 'file-1',
    filename: 'data.csv',
    score_0_100: 86.5,
    component_scores: { completeness: 90, validity: 80, consistency: 95, uniqueness: 100, accuracy: 80 },
    recommendations: ['Fix missing values'],
    actionable_recommendations: [
      {
        dimension: 'completeness',
        description: "Apply 'fill_missing' to age",
        transformation_type: 'fill_missing',
        affected_columns: ['age'],
        severity: 'high',
      },
    ],
    gates: [
      {
        gate_name: 'ML Training Ready',
        passed: true,
        actual_score: 86.5,
        required_score: 70,
        failing_dimensions: [],
        is_blocking: false,
      },
    ],
    critical_issue_count: 1,
    warning_count: 2,
    partial: false,
    ...overrides,
  }
}

function makeTrend(): QualityTrendResponse {
  return {
    dataset_id: 'ds-1',
    points: [
      { version_number: 2, created_at: '2026-01-01T00:00:00Z', score_before: 60, score_after: 80, improvement: 20, transformation: 'fill_missing' },
    ],
    overall_improvement: 20,
    best_score: 80,
    worst_score: 60,
  }
}

describe('QualityDashboard', () => {
  beforeEach(() => jest.clearAllMocks())

  it('renders the 0-100 score, gates, components and recommendations', async () => {
    mockService.getQualityReport.mockResolvedValue(makeReport())
    mockService.getQualityTrend.mockResolvedValue({ ...makeTrend(), points: [] })

    render(<QualityDashboard fileId="file-1" datasetId="ds-1" />)

    await waitFor(() => expect(screen.getByTestId('quality-dashboard')).toBeInTheDocument())
    expect(screen.getByTestId('quality-score')).toHaveTextContent('86.5')
    expect(screen.getByText('ML Training Ready')).toBeInTheDocument()
    expect(screen.getByTestId('component-completeness')).toBeInTheDocument()
    expect(screen.getByText("Apply 'fill_missing' to age")).toBeInTheDocument()
    expect(screen.getByText('fill_missing')).toBeInTheDocument()
  })

  it('renders the trend chart only when trend points exist', async () => {
    mockService.getQualityReport.mockResolvedValue(makeReport())
    mockService.getQualityTrend.mockResolvedValue(makeTrend())

    render(<QualityDashboard fileId="file-1" datasetId="ds-1" />)

    await waitFor(() => expect(screen.getByTestId('line-chart')).toBeInTheDocument())
  })

  it('shows an error state when the report fails to load', async () => {
    mockService.getQualityReport.mockRejectedValue(new Error('boom'))

    render(<QualityDashboard fileId="file-1" />)

    await waitFor(() => expect(screen.getByTestId('quality-dashboard-error')).toBeInTheDocument())
  })

  it('does not fetch the trend when no datasetId is provided', async () => {
    mockService.getQualityReport.mockResolvedValue(makeReport())

    render(<QualityDashboard fileId="file-1" />)

    await waitFor(() => expect(screen.getByTestId('quality-dashboard')).toBeInTheDocument())
    expect(mockService.getQualityTrend).not.toHaveBeenCalled()
  })
})
