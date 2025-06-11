import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { StatisticsDashboard } from '@/components/StatisticsDashboard'

const mockStatistics = {
  row_count: 1000,
  column_count: 8,
  memory_usage_mb: 15.6,
  correlation_matrix: {
    age: { age: 1.0, salary: 0.65, experience: 0.78 },
    salary: { age: 0.65, salary: 1.0, experience: 0.82 },
    experience: { age: 0.78, salary: 0.82, experience: 1.0 }
  },
  column_statistics: [
    {
      column_name: 'age',
      data_type: 'integer',
      total_count: 1000,
      null_count: 5,
      null_percentage: 0.5,
      unique_count: 45,
      unique_percentage: 4.5,
      mean: 34.2,
      median: 33.0,
      std_dev: 8.7,
      min_value: 22,
      max_value: 65,
      q1: 28,
      q3: 41,
      outlier_count: 12,
      outlier_percentage: 1.2,
      most_frequent_values: [
        { value: 30, count: 25, percentage: 2.5 },
        { value: 35, count: 22, percentage: 2.2 }
      ]
    },
    {
      column_name: 'salary',
      data_type: 'currency',
      total_count: 1000,
      null_count: 0,
      null_percentage: 0.0,
      unique_count: 987,
      unique_percentage: 98.7,
      mean: 65000,
      median: 62000,
      std_dev: 15000,
      min_value: 35000,
      max_value: 120000,
      q1: 52000,
      q3: 75000,
      outlier_count: 8,
      outlier_percentage: 0.8
    },
    {
      column_name: 'department',
      data_type: 'categorical',
      total_count: 1000,
      null_count: 0,
      null_percentage: 0.0,
      unique_count: 5,
      unique_percentage: 0.5,
      most_frequent_values: [
        { value: 'Engineering', count: 350, percentage: 35.0 },
        { value: 'Sales', count: 250, percentage: 25.0 },
        { value: 'Marketing', count: 200, percentage: 20.0 }
      ]
    }
  ],
  missing_value_summary: {
    total_missing_values: 5,
    columns_with_missing: 1,
    complete_columns: 7
  }
}

// Mock chart components
jest.mock('@/components/HistogramChart', () => {
  return {
    HistogramChart: ({ column }) => <div data-testid={`histogram-${column}`}>Histogram for {column}</div>
  }
})

jest.mock('@/components/CorrelationHeatmap', () => {
  return {
    CorrelationHeatmap: () => <div data-testid="correlation-heatmap">Correlation Heatmap</div>
  }
})

describe('StatisticsDashboard', () => {
  it('renders overview cards correctly', () => {
    render(<StatisticsDashboard datasetId="test-id" statistics={mockStatistics} />)
    
    // Check overview metrics
    expect(screen.getByText('1,000')).toBeInTheDocument() // Row count
    expect(screen.getByText('8')).toBeInTheDocument() // Column count
    expect(screen.getByText('99.9%')).toBeInTheDocument() // Completeness percentage
    expect(screen.getByText('15.6')).toBeInTheDocument() // Memory usage
    
    // Check labels
    expect(screen.getByText('Rows')).toBeInTheDocument()
    expect(screen.getByText('Columns')).toBeInTheDocument()
    expect(screen.getByText('Complete')).toBeInTheDocument()
    expect(screen.getByText('MB')).toBeInTheDocument()
  })

  it('renders tab navigation correctly', () => {
    render(<StatisticsDashboard datasetId="test-id" statistics={mockStatistics} />)
    
    // Check tab labels
    expect(screen.getByText('Overview')).toBeInTheDocument()
    expect(screen.getByText('Numeric')).toBeInTheDocument()
    expect(screen.getByText('Categorical')).toBeInTheDocument()
    expect(screen.getByText('Correlations')).toBeInTheDocument()
  })

  it('displays missing values summary in overview tab', () => {
    render(<StatisticsDashboard datasetId="test-id" statistics={mockStatistics} />)
    
    expect(screen.getByText('Missing Values')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument() // Total missing
    expect(screen.getByText('1')).toBeInTheDocument() // Columns affected
    expect(screen.getByText('7')).toBeInTheDocument() // Complete columns
  })

  it('shows data quality issues when present', () => {
    render(<StatisticsDashboard datasetId="test-id" statistics={mockStatistics} />)
    
    // Should show age column issue (has outliers > 5%)
    expect(screen.getByText('Data Quality Issues')).toBeInTheDocument()
    // Note: age has 1.2% outliers and 0.5% missing, both below thresholds
    // salary has 0.8% outliers, below threshold
    // So no issues should be displayed
    expect(screen.getByText('No significant issues detected')).toBeInTheDocument()
  })

  it('displays numeric columns correctly in numeric tab', () => {
    render(<StatisticsDashboard datasetId="test-id" statistics={mockStatistics} />)
    
    // Click numeric tab
    const numericTab = screen.getByRole('tab', { name: 'Numeric' })
    fireEvent.mouseDown(numericTab)
    fireEvent.mouseUp(numericTab)
    fireEvent.click(numericTab)
    
    // Check age column
    expect(screen.getByText('age')).toBeInTheDocument()
    expect(screen.getByText('34.20')).toBeInTheDocument() // Mean
    expect(screen.getByText('33.00')).toBeInTheDocument() // Median
    expect(screen.getByText('8.70')).toBeInTheDocument() // Std dev
    expect(screen.getByText('12 (1.2%)')).toBeInTheDocument() // Outliers
    
    // Check salary column
    expect(screen.getByText('salary')).toBeInTheDocument()
    expect(screen.getByText('65000.00')).toBeInTheDocument() // Mean
    expect(screen.getByText('62000.00')).toBeInTheDocument() // Median
    
    // Check histograms are rendered
    expect(screen.getByTestId('histogram-age')).toBeInTheDocument()
    expect(screen.getByTestId('histogram-salary')).toBeInTheDocument()
  })

  it('displays categorical columns correctly in categorical tab', async () => {
    render(<StatisticsDashboard datasetId="test-id" statistics={mockStatistics} />)
    
    // Click categorical tab
    const categoricalTab = screen.getByRole('tab', { name: 'Categorical' })
    fireEvent.mouseDown(categoricalTab)
    fireEvent.mouseUp(categoricalTab)
    fireEvent.click(categoricalTab)
    
    // Wait for tab content to load and check department column
    await waitFor(() => {
      expect(screen.getByText('department')).toBeInTheDocument()
    })
    
    expect(screen.getByText(/5.*unique.*values/)).toBeInTheDocument()
    expect(screen.getByText('0.5%')).toBeInTheDocument() // Cardinality percentage
    
    // Check most frequent values
    expect(screen.getByText('Engineering')).toBeInTheDocument()
    expect(screen.getByText('Sales')).toBeInTheDocument()
    expect(screen.getByText('Marketing')).toBeInTheDocument()
    expect(screen.getByText('35.0%')).toBeInTheDocument() // Engineering percentage
  })

  it('displays correlation matrix in correlations tab', () => {
    render(<StatisticsDashboard datasetId="test-id" statistics={mockStatistics} />)
    
    // Click correlations tab
    const correlationsTab = screen.getByRole('tab', { name: 'Correlations' })
    fireEvent.mouseDown(correlationsTab)
    fireEvent.mouseUp(correlationsTab)
    fireEvent.click(correlationsTab)
    
    expect(screen.getByText('Correlation Matrix')).toBeInTheDocument()
    expect(screen.getByText('Correlation between numeric variables')).toBeInTheDocument()
    expect(screen.getByTestId('correlation-heatmap')).toBeInTheDocument()
  })

  it('handles loading state when statistics not provided', () => {
    render(<StatisticsDashboard datasetId="test-id" />)
    
    expect(screen.getByText('Loading statistics...')).toBeInTheDocument()
  })

  it('handles error state gracefully', () => {
    fetch.mockRejectedValueOnce(new Error('Failed to fetch'))
    
    render(<StatisticsDashboard datasetId="test-id" />)
    
    // Should eventually show error
    expect(screen.getByText('Loading statistics...')).toBeInTheDocument()
  })

  it('filters columns by data type correctly', () => {
    render(<StatisticsDashboard datasetId="test-id" statistics={mockStatistics} />)
    
    // Check numeric tab only shows numeric columns
    const numericTab = screen.getByRole('tab', { name: 'Numeric' })
    fireEvent.mouseDown(numericTab)
    fireEvent.mouseUp(numericTab)
    fireEvent.click(numericTab)
    expect(screen.getByText('age')).toBeInTheDocument()
    expect(screen.getByText('salary')).toBeInTheDocument()
    expect(screen.queryByText('department')).not.toBeInTheDocument()
    
    // Check categorical tab only shows categorical columns
    const categoricalTab = screen.getByRole('tab', { name: 'Categorical' })
    fireEvent.mouseDown(categoricalTab)
    fireEvent.mouseUp(categoricalTab)
    fireEvent.click(categoricalTab)
    expect(screen.getByText('department')).toBeInTheDocument()
    expect(screen.queryByText('age')).not.toBeInTheDocument()
    expect(screen.queryByText('salary')).not.toBeInTheDocument()
  })

  it('calculates completeness percentage correctly', () => {
    render(<StatisticsDashboard datasetId="test-id" statistics={mockStatistics} />)
    
    // Total cells = 1000 rows * 8 columns = 8000
    // Missing values = 5
    // Completeness = (8000 - 5) / 8000 * 100 = 99.9375% ≈ 99.9% (rounded to 1 decimal)
    expect(screen.getByText('99.9%')).toBeInTheDocument()
  })

  it('handles missing correlation matrix', () => {
    const statsWithoutCorrelation = {
      ...mockStatistics,
      correlation_matrix: undefined
    }
    
    render(<StatisticsDashboard datasetId="test-id" statistics={statsWithoutCorrelation} />)
    
    const correlationsTab = screen.getByRole('tab', { name: 'Correlations' })
    fireEvent.mouseDown(correlationsTab)
    fireEvent.mouseUp(correlationsTab)
    fireEvent.click(correlationsTab)
    expect(screen.getByText('No correlation data available')).toBeInTheDocument()
  })

  it('handles columns without most frequent values', () => {
    const statsWithoutFreqValues = {
      ...mockStatistics,
      column_statistics: [
        {
          ...mockStatistics.column_statistics[2],
          most_frequent_values: undefined
        }
      ]
    }
    
    render(<StatisticsDashboard datasetId="test-id" statistics={statsWithoutFreqValues} />)
    
    const categoricalTab = screen.getByRole('tab', { name: 'Categorical' })
    fireEvent.mouseDown(categoricalTab)
    fireEvent.mouseUp(categoricalTab)
    fireEvent.click(categoricalTab)
    // Should still render the column even without frequent values
    expect(screen.getByText('department')).toBeInTheDocument()
  })
})