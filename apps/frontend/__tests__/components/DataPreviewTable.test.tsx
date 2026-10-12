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
    ;(global.fetch as jest.Mock).mockResolvedValue({
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
    ;(global.fetch as jest.Mock).mockRejectedValueOnce(new Error('API Error'))
    
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
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
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

  describe('a file too large to count exactly (#720)', () => {
    const lineCounted = {
      ...mockPreviewData,
      total_rows: 1203441,
      approximate_total_rows: true,
      warning: 'File too large to cache; only the requested rows were read.',
    }

    beforeEach(() => {
      ;(global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue(lineCounted),
      })
    })

    it('says the row total and the page count are approximate', async () => {
      render(<DataPreviewTable datasetId="test-id" />)

      expect(await screen.findByText('Showing 1-3 of about 1203441 rows')).toBeInTheDocument()
      expect(screen.getByText('Page 1 of about 24069')).toBeInTheDocument()
    })

    it('keeps the pager when the estimate ran a page past the end', async () => {
      ;(global.fetch as jest.Mock)
        .mockResolvedValueOnce({ ok: true, json: jest.fn().mockResolvedValue(lineCounted) })
        .mockResolvedValueOnce({
          ok: true,
          json: jest.fn().mockResolvedValue({ ...lineCounted, data: [], rows: 0, offset: 50 }),
        })
      render(<DataPreviewTable datasetId="test-id" />)

      fireEvent.click(await screen.findByText('Next'))

      expect(await screen.findByText('No more rows: the total was an estimate')).toBeInTheDocument()
      expect(screen.queryByText('No data available')).not.toBeInTheDocument()
      fireEvent.click(screen.getByText('Previous'))
      expect(await screen.findByText('Showing 1-3 of about 1203441 rows')).toBeInTheDocument()
    })

    it('shows why', async () => {
      render(<DataPreviewTable datasetId="test-id" />)

      expect(await screen.findByText(lineCounted.warning)).toBeInTheDocument()
    })
  })

  it('goes forward and back a page', async () => {
    render(<DataPreviewTable datasetId="test-id" />)

    fireEvent.click(await screen.findByText('Next'))
    expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Previous'))

    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
  })

  it('states an exact total as exact', async () => {
    render(<DataPreviewTable datasetId="test-id" />)

    expect(await screen.findByText('Showing 1-3 of 100 rows')).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    expect(screen.queryByText(/about/)).not.toBeInTheDocument()
  })
})
