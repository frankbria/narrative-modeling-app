import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import FeaturePreview from '@/components/feature-builder/FeaturePreview';

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  AlertCircle: () => <span data-testid="alert-icon">AlertCircle</span>,
  CheckCircle: () => <span data-testid="check-icon">CheckCircle</span>,
  AlertTriangle: () => <span data-testid="warning-icon">AlertTriangle</span>,
  BarChart2: () => <span data-testid="chart-icon">BarChart2</span>,
  Table: () => <span data-testid="table-icon">Table</span>,
  Loader2: () => <span data-testid="loader-icon">Loader</span>,
}));

describe('FeaturePreview Component', () => {
  const mockStatistics = {
    mean: 50.5,
    median: 48.0,
    std: 15.2,
    min: 10.0,
    max: 100.0,
    null_count: 5,
    unique_count: 85,
    total_count: 100,
  };

  const mockDistribution = [
    { bin_start: 0, bin_end: 20, count: 15, label: '0-20' },
    { bin_start: 20, bin_end: 40, count: 25, label: '20-40' },
    { bin_start: 40, bin_end: 60, count: 35, label: '40-60' },
    { bin_start: 60, bin_end: 80, count: 15, label: '60-80' },
    { bin_start: 80, bin_end: 100, count: 10, label: '80-100' },
  ];

  const mockSampleData = [
    { price: 100, quantity: 5, _computed_feature: 500 },
    { price: 50, quantity: 10, _computed_feature: 500 },
    { price: 200, quantity: 2, _computed_feature: 400 },
  ];

  const mockPreview = {
    success: true,
    values: [500, 500, 400, 300, 200],
    statistics: mockStatistics,
    distribution: mockDistribution,
    formula: 'price * quantity',
    input_columns: ['price', 'quantity'],
    inferred_type: 'numeric',
    sample_data: mockSampleData,
    error: null,
    warnings: [],
  };

  const mockValidationResult = {
    is_valid: true,
    errors: [],
    warnings: [],
    inferred_type: 'numeric',
    potential_issues: [],
  };

  describe('Loading State', () => {
    it('should show loading spinner when loading', () => {
      render(<FeaturePreview preview={null} loading={true} validationResult={null} />);

      expect(screen.getByTestId('loader-icon')).toBeInTheDocument();
      expect(screen.getByText('Computing preview...')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no preview or validation', () => {
      render(<FeaturePreview preview={null} loading={false} validationResult={null} />);

      expect(screen.getByText('No Preview Yet')).toBeInTheDocument();
      expect(screen.getByText('Click Preview to see the computed feature values')).toBeInTheDocument();
      expect(screen.getByTestId('chart-icon')).toBeInTheDocument();
    });
  });

  describe('Validation Display', () => {
    it('should show valid status when expression is valid', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={mockValidationResult}
        />
      );

      expect(screen.getByText('Valid Expression')).toBeInTheDocument();
      expect(screen.getByTestId('check-icon')).toBeInTheDocument();
    });

    it('should show invalid status when expression is invalid', () => {
      const invalidValidation = {
        ...mockValidationResult,
        is_valid: false,
        errors: ['Column "missing" does not exist'],
      };

      render(
        <FeaturePreview
          preview={null}
          loading={false}
          validationResult={invalidValidation}
        />
      );

      expect(screen.getByText('Invalid Expression')).toBeInTheDocument();
      expect(screen.getByText('Column "missing" does not exist')).toBeInTheDocument();
    });

    it('should show warnings when present', () => {
      const validationWithWarnings = {
        ...mockValidationResult,
        warnings: ['Division by zero possible'],
      };

      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={validationWithWarnings}
        />
      );

      expect(screen.getByText('Division by zero possible')).toBeInTheDocument();
    });
  });

  describe('Error Display', () => {
    it('should show error message when preview fails', () => {
      const failedPreview = {
        ...mockPreview,
        success: false,
        error: 'Failed to compute feature',
      };

      render(
        <FeaturePreview
          preview={failedPreview}
          loading={false}
          validationResult={null}
        />
      );

      expect(screen.getByText('Preview Failed')).toBeInTheDocument();
      expect(screen.getByText('Failed to compute feature')).toBeInTheDocument();
    });

    it('should show warnings from preview', () => {
      const previewWithWarnings = {
        ...mockPreview,
        warnings: ['5 null values in result', 'Some values are very large'],
      };

      render(
        <FeaturePreview
          preview={previewWithWarnings}
          loading={false}
          validationResult={null}
        />
      );

      expect(screen.getByText('Warnings')).toBeInTheDocument();
      expect(screen.getByText('5 null values in result')).toBeInTheDocument();
      expect(screen.getByText('Some values are very large')).toBeInTheDocument();
    });
  });

  describe('Formula Display', () => {
    it('should display the formula', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      expect(screen.getByText('Formula')).toBeInTheDocument();
      expect(screen.getByText('price * quantity')).toBeInTheDocument();
    });
  });

  describe('View Mode Tabs', () => {
    it('should show statistics tab by default', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      expect(screen.getByText('Statistics')).toBeInTheDocument();
      expect(screen.getByText('Distribution')).toBeInTheDocument();
      expect(screen.getByText('Table')).toBeInTheDocument();
    });

    it('should show statistics content by default', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      expect(screen.getByText('Mean')).toBeInTheDocument();
      // The formatNumber function formats to 4 decimal places for non-integers
      expect(screen.getByText('50.5000')).toBeInTheDocument();
      expect(screen.getByText('Median')).toBeInTheDocument();
      expect(screen.getByText('48')).toBeInTheDocument();
    });

    it('should switch to distribution view when clicked', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      const distributionTab = screen.getByText('Distribution');
      fireEvent.click(distributionTab);

      // Should show distribution bins
      expect(screen.getByText('0-20')).toBeInTheDocument();
      expect(screen.getByText('20-40')).toBeInTheDocument();
      expect(screen.getByText('40-60')).toBeInTheDocument();
    });

    it('should switch to table view when clicked', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      const tableTab = screen.getByText('Table');
      fireEvent.click(tableTab);

      // Should show table headers
      expect(screen.getByText('price')).toBeInTheDocument();
      expect(screen.getByText('quantity')).toBeInTheDocument();
      expect(screen.getByText('Result')).toBeInTheDocument();
    });
  });

  describe('Statistics View', () => {
    it('should display all statistics', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      expect(screen.getByText('Mean')).toBeInTheDocument();
      expect(screen.getByText('Median')).toBeInTheDocument();
      expect(screen.getByText('Std Dev')).toBeInTheDocument();
      expect(screen.getByText('Min / Max')).toBeInTheDocument();
      expect(screen.getByText('Null Count')).toBeInTheDocument();
      expect(screen.getByText('Unique')).toBeInTheDocument();
    });

    it('should display sample values', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      expect(screen.getByText('Sample Values')).toBeInTheDocument();
      // There are multiple 500 values in the sample, so use getAllByText
      expect(screen.getAllByText('500').length).toBeGreaterThan(0);
    });

    it('should format numbers correctly', () => {
      const previewWithDecimals = {
        ...mockPreview,
        statistics: {
          ...mockStatistics,
          mean: 50.12345678,
          std: 15.2,
        },
      };

      render(
        <FeaturePreview
          preview={previewWithDecimals}
          loading={false}
          validationResult={null}
        />
      );

      // Should be formatted to 4 decimal places
      expect(screen.getByText('50.1235')).toBeInTheDocument();
    });

    it('should display dash for null statistics', () => {
      const previewWithNullStats = {
        ...mockPreview,
        statistics: {
          ...mockStatistics,
          mean: null,
          median: null,
        },
      };

      render(
        <FeaturePreview
          preview={previewWithNullStats}
          loading={false}
          validationResult={null}
        />
      );

      // Find the Mean section and verify it has "-"
      const meanLabel = screen.getByText('Mean');
      const meanContainer = meanLabel.closest('div')?.parentElement;
      expect(meanContainer).toHaveTextContent('Mean');
      expect(meanContainer).toHaveTextContent('-');
    });
  });

  describe('Distribution View', () => {
    it('should display all distribution bins', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      fireEvent.click(screen.getByText('Distribution'));

      expect(screen.getByText('0-20')).toBeInTheDocument();
      expect(screen.getByText('20-40')).toBeInTheDocument();
      expect(screen.getByText('40-60')).toBeInTheDocument();
      expect(screen.getByText('60-80')).toBeInTheDocument();
      expect(screen.getByText('80-100')).toBeInTheDocument();
    });

    it('should display bin counts', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      fireEvent.click(screen.getByText('Distribution'));

      // Use getAllByText since some counts may appear multiple times (15 appears in 0-20 and 60-80)
      expect(screen.getAllByText('15').length).toBeGreaterThan(0);
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('35')).toBeInTheDocument();
    });

    it('should show message when no distribution data', () => {
      const previewWithoutDistribution = {
        ...mockPreview,
        distribution: [],
      };

      render(
        <FeaturePreview
          preview={previewWithoutDistribution}
          loading={false}
          validationResult={null}
        />
      );

      fireEvent.click(screen.getByText('Distribution'));

      expect(screen.getByText('No distribution data available')).toBeInTheDocument();
    });
  });

  describe('Table View', () => {
    it('should display sample data in table format', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      fireEvent.click(screen.getByText('Table'));

      // Check headers
      expect(screen.getByText('price')).toBeInTheDocument();
      expect(screen.getByText('quantity')).toBeInTheDocument();
      expect(screen.getByText('Result')).toBeInTheDocument();

      // Check values
      expect(screen.getByText('100')).toBeInTheDocument();
      expect(screen.getByText('50')).toBeInTheDocument();
    });

    it('should show message when no sample data', () => {
      const previewWithoutSampleData = {
        ...mockPreview,
        sample_data: null,
      };

      render(
        <FeaturePreview
          preview={previewWithoutSampleData}
          loading={false}
          validationResult={null}
        />
      );

      fireEvent.click(screen.getByText('Table'));

      expect(screen.getByText('No sample data available')).toBeInTheDocument();
    });

    it('should display null values correctly', () => {
      const previewWithNulls = {
        ...mockPreview,
        sample_data: [
          { price: 100, quantity: null, _computed_feature: null },
        ],
      };

      render(
        <FeaturePreview
          preview={previewWithNulls}
          loading={false}
          validationResult={null}
        />
      );

      fireEvent.click(screen.getByText('Table'));

      expect(screen.getAllByText('null').length).toBeGreaterThan(0);
    });
  });

  describe('Tab Styling', () => {
    it('should highlight active tab', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      const statisticsTab = screen.getByText('Statistics');
      expect(statisticsTab).toHaveClass('border-blue-600');
      expect(statisticsTab).toHaveClass('text-blue-600');
    });

    it('should change active tab styling when clicked', () => {
      render(
        <FeaturePreview
          preview={mockPreview}
          loading={false}
          validationResult={null}
        />
      );

      const distributionTab = screen.getByText('Distribution');
      fireEvent.click(distributionTab);

      expect(distributionTab).toHaveClass('border-blue-600');
      expect(distributionTab).toHaveClass('text-blue-600');
    });
  });
});
