import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DataPreviewTable } from '@/components/DataPreviewTable'

// Mock data
const mockPreviewData = {
  data: [
    { id: 1, name: 'John', age: 30, city: 'New York' },
    { id: 2, name: 'Jane', age: 25, city: 'Los Angeles' },
    { id: 3, name: 'Bob', age: 35, city: 'Chicago' },
  ],
  total_rows: 100,
  columns: ['id', 'name', 'age', 'city'],
  offset: 0,
  rows: 3,
}

const mockOnExport = jest.fn()

describe('DataPreviewTable', () => {
  beforeEach(() => {
    fetch.mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(mockPreviewData),
    })
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it('renders loading state initially', () => {
    render(<DataPreviewTable datasetId="test-id" onExport={mockOnExport} />)
    expect(screen.getByText('Loading preview data...')).toBeInTheDocument()
  })

  it('renders table with data after loading', async () => {
    render(<DataPreviewTable datasetId="test-id" onExport={mockOnExport} />)
    
    await waitFor(() => {
      expect(screen.getByText('Data Preview')).toBeInTheDocument()
    })

    // Check if table headers are rendered
    expect(screen.getByText('id')).toBeInTheDocument()
    expect(screen.getByText('name')).toBeInTheDocument()
    expect(screen.getByText('age')).toBeInTheDocument()
    expect(screen.getByText('city')).toBeInTheDocument()

    // Check if data rows are rendered
    expect(screen.getByText('John')).toBeInTheDocument()
    expect(screen.getByText('Jane')).toBeInTheDocument()
    expect(screen.getByText('Bob')).toBeInTheDocument()
  })

  it('displays correct row count information', async () => {
    render(<DataPreviewTable datasetId="test-id" onExport={mockOnExport} />)
    
    await waitFor(() => {
      expect(screen.getByText(/Showing 1-3 of 100 rows/)).toBeInTheDocument()
    })
  })

  it('handles pagination controls', async () => {
    render(<DataPreviewTable datasetId="test-id" onExport={mockOnExport} />)
    
    await waitFor(() => {
      expect(screen.getByText('Data Preview')).toBeInTheDocument()
    })

    // Check if pagination controls are present
    const nextButton = screen.getByText('Next')
    const prevButton = screen.getByText('Previous')
    
    expect(nextButton).toBeInTheDocument()
    expect(prevButton).toBeInTheDocument()
    expect(prevButton).toBeDisabled() // Should be disabled on first page
  })

  it('calls export function when export button is clicked', async () => {
    render(<DataPreviewTable datasetId="test-id" onExport={mockOnExport} />)
    
    await waitFor(() => {
      expect(screen.getByText('Data Preview')).toBeInTheDocument()
    })

    const exportButton = screen.getByText('Export')
    fireEvent.click(exportButton)
    
    expect(mockOnExport).toHaveBeenCalledTimes(1)
  })

  it('handles API errors gracefully', async () => {
    fetch.mockRejectedValueOnce(new Error('API Error'))
    
    render(<DataPreviewTable datasetId="test-id" onExport={mockOnExport} />)
    
    await waitFor(() => {
      expect(screen.getByText(/Error: API Error/)).toBeInTheDocument()
    })
  })

  it('makes correct API call with pagination parameters', async () => {
    render(<DataPreviewTable datasetId="test-id" onExport={mockOnExport} />)
    
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/data/test-id/preview?rows=50&offset=0',
        expect.objectContaining({
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
        })
      )
    })
  })

  it('updates data when pagination changes', async () => {
    const page2Data = {
      data: [
        { id: 11, name: 'Alice', age: 28, city: 'Boston' },
        { id: 12, name: 'Charlie', age: 32, city: 'Seattle' },
      ],
      total_rows: 100,
      columns: ['id', 'name', 'age', 'city'],
    }

    render(<DataPreviewTable datasetId="test-id" onExport={mockOnExport} />)
    
    await waitFor(() => {
      expect(screen.getByText('John')).toBeInTheDocument()
    })

    // Mock API response for page 2
    fetch.mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue(page2Data),
    })

    // Click next button
    const nextButton = screen.getByText('Next')
    fireEvent.click(nextButton)

    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument()
    })

    // Verify the API was called with correct offset
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/data/test-id/preview?rows=50&offset=50',
      expect.objectContaining({
        credentials: 'include',
      })
    )
  })
})