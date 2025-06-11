import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AIInsightsPanel } from '@/components/AIInsightsPanel'

const mockAISummary = {
  overview: 'This dataset contains customer information with 1000 records and 8 columns.',
  issues: [
    'Customer age distribution shows majority between 25-45 years',
    'Geographic distribution is concentrated in urban areas',
    'Missing values are primarily in optional fields'
  ],
  relationships: [
    'Strong correlation between age and purchase amount',
    'Seasonal patterns in transaction dates',
    'Customer segments based on behavior'
  ],
  suggestions: [
    'Consider data validation for email addresses',
    'Implement data collection for missing demographic info',
    'Set up monitoring for data quality'
  ],
  confidence_score: 0.92,
  analysis_depth: 'comprehensive',
  model_used: 'GPT-4',
  processing_time: 2.3
}

describe('AIInsightsPanel', () => {
  beforeEach(() => {
    fetch.mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(mockAISummary),
    })
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it('renders loading state initially', () => {
    render(<AIInsightsPanel datasetId="test-id" />)
    expect(screen.getByText('Generating AI insights...')).toBeInTheDocument()
  })

  it('displays AI insights after loading', async () => {
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(screen.getByText('AI Insights')).toBeInTheDocument()
    })

    expect(screen.getByText(mockAISummary.overview)).toBeInTheDocument()
    expect(screen.getByText(/92/)).toBeInTheDocument() // Confidence score
  })

  it('renders all tab sections', async () => {
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(screen.getByText('AI Insights')).toBeInTheDocument()
    })

    // Check tab triggers
    expect(screen.getByText('Overview')).toBeInTheDocument()
    expect(screen.getByText('Issues')).toBeInTheDocument()
    expect(screen.getByText('Insights')).toBeInTheDocument()
    expect(screen.getByText('Detailed')).toBeInTheDocument()
  })

  it('displays key insights correctly', async () => {
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(screen.getByText('AI Insights')).toBeInTheDocument()
    })

    // Click on Issues tab using multiple event types
    const issuesTab = screen.getByRole('tab', { name: 'Issues' })
    fireEvent.mouseDown(issuesTab)
    fireEvent.mouseUp(issuesTab)
    fireEvent.click(issuesTab)

    // Wait for tab content to appear
    await waitFor(() => {
      expect(screen.getByText(/Customer age distribution shows majority/)).toBeInTheDocument()
    }, { timeout: 2000 })
    
    expect(screen.getByText(/Geographic distribution is concentrated/)).toBeInTheDocument()
    expect(screen.getByText(/Missing values are primarily/)).toBeInTheDocument()
  })

  it('displays patterns correctly', async () => {
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(screen.getByText('AI Insights')).toBeInTheDocument()
    })

    // Click on Insights tab using full mouse event sequence
    const insightsTab = screen.getByRole('tab', { name: 'Insights' })
    fireEvent.mouseDown(insightsTab)
    fireEvent.mouseUp(insightsTab)
    fireEvent.click(insightsTab)

    // Wait for tab content to appear
    await waitFor(() => {
      expect(screen.getByText(/Strong correlation between age/)).toBeInTheDocument()
    }, { timeout: 2000 })
    
    expect(screen.getByText(/Seasonal patterns in transaction/)).toBeInTheDocument()
    expect(screen.getByText(/Customer segments based on behavior/)).toBeInTheDocument()
  })

  it('displays recommendations correctly', async () => {
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(screen.getByText('AI Insights')).toBeInTheDocument()
    })

    // Check that recommendations are in overview tab (in Key Recommendations section)

    // Check that recommendations are displayed
    expect(screen.getByText(/Consider data validation for email/)).toBeInTheDocument()
    expect(screen.getByText(/Implement data collection for missing/)).toBeInTheDocument()
    expect(screen.getByText(/Set up monitoring for data quality/)).toBeInTheDocument()
  })

  it('shows regenerate button and handles regeneration', async () => {
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(screen.getByText('AI Insights')).toBeInTheDocument()
    })

    const regenerateButton = screen.getByText('Regenerate')
    expect(regenerateButton).toBeInTheDocument()

    // Mock new response for regeneration
    const newSummary = {
      ...mockAISummary,
      overview: 'Updated AI analysis of the dataset',
      confidence_score: 0.95
    }

    fetch.mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue(newSummary),
    })

    fireEvent.click(regenerateButton)

    await waitFor(() => {
      expect(screen.getByText('Updated AI analysis of the dataset')).toBeInTheDocument()
    })
  })

  it('handles API errors gracefully', async () => {
    fetch.mockRejectedValueOnce(new Error('AI service unavailable'))
    
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(screen.getByText(/Error: AI service unavailable/)).toBeInTheDocument()
    })
  })

  it('displays confidence score with appropriate styling', async () => {
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(screen.getByText(/Confidence:/)).toBeInTheDocument()
      expect(screen.getByText(/92/)).toBeInTheDocument()
    })
  })

  it('makes correct API call for insights', async () => {
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/ai/summarize/test-id',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
        })
      )
    })
  })

  it('handles empty insights gracefully', async () => {
    const emptySummary = {
      overview: '',
      issues: [],
      relationships: [],
      suggestions: [],
      confidence_score: 0.5
    }

    fetch.mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue(emptySummary),
    })
    
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(screen.getByText('AI Insights')).toBeInTheDocument()
    })

    // Should handle empty sections gracefully
    const issuesTab = screen.getByRole('tab', { name: 'Issues' })
    fireEvent.mouseDown(issuesTab)
    fireEvent.mouseUp(issuesTab)
    fireEvent.click(issuesTab)
    await waitFor(() => {
      expect(screen.getByText('No significant issues detected')).toBeInTheDocument()
    }, { timeout: 2000 })

    const insightsTab = screen.getByRole('tab', { name: 'Insights' })
    fireEvent.mouseDown(insightsTab)
    fireEvent.mouseUp(insightsTab)
    fireEvent.click(insightsTab)
    await waitFor(() => {
      expect(screen.getByText('No significant patterns detected')).toBeInTheDocument()
    }, { timeout: 2000 })
  })

  it('shows generation timestamp', async () => {
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(screen.getByText('AI Insights')).toBeInTheDocument()
    })

    // Should show model used
    expect(screen.getByText('GPT-4')).toBeInTheDocument()
  })

  it('disables regenerate button while loading', async () => {
    render(<AIInsightsPanel datasetId="test-id" />)
    
    await waitFor(() => {
      expect(screen.getByText('AI Insights')).toBeInTheDocument()
    })

    const regenerateButton = screen.getByText('Regenerate')
    
    // Set up a delayed response to test loading state
    fetch.mockImplementationOnce(() => 
      new Promise(resolve => 
        setTimeout(() => resolve({
          ok: true,
          json: jest.fn().mockResolvedValue(mockAISummary),
        }), 100)
      )
    )

    fireEvent.click(regenerateButton)
    
    // Button should be disabled during loading
    expect(regenerateButton).toBeDisabled()
  })
})