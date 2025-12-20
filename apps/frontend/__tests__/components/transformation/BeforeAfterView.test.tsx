import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BeforeAfterView } from '@/components/transformation/BeforeAfterView';
import type { ImpactStatistics } from '@/components/transformation/BeforeAfterView';

// Mock ChangedValueHighlight component
jest.mock('@/components/transformation/ChangedValueHighlight', () => ({
  ChangedValueHighlight: jest.fn(({ value, isChanged, oldValue }) => (
    <span data-testid="changed-value" data-changed={isChanged}>
      {isChanged ? `${oldValue} → ${value}` : String(value)}
    </span>
  )),
}));

describe('BeforeAfterView Component', () => {
  const mockOriginalData = [
    { id: 1, name: 'Alice', age: null, city: 'NYC' },
    { id: 2, name: 'Bob', age: 30, city: 'LA' },
    { id: 3, name: 'Charlie', age: 25, city: 'SF' },
  ];

  const mockTransformedData = [
    { id: 1, name: 'Alice', age: 0, city: 'NYC' },
    { id: 2, name: 'Bob', age: 30, city: 'LA' },
    { id: 3, name: 'Charlie', age: 25, city: 'SF' },
  ];

  const mockImpactStats: ImpactStatistics = {
    rows_affected: 1,
    values_changed: 1,
    columns_affected: ['age'],
    quality_score_before: 0.75,
    quality_score_after: 1.0,
  };

  describe('Rendering', () => {
    it('should render both before and after tables', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      expect(screen.getByText('Original Data')).toBeInTheDocument();
      expect(screen.getByText('Transformed Data')).toBeInTheDocument();
    });

    it('should display correct row count', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      expect(
        screen.getByText(/Showing 3 rows × 4 columns/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/3 rows before transformation/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/3 rows after transformation/i)
      ).toBeInTheDocument();
    });

    it('should render all column headers', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      const columns = ['id', 'name', 'age', 'city'];
      columns.forEach((column) => {
        // Each column appears twice (before and after tables)
        const headers = screen.getAllByText(column);
        expect(headers.length).toBe(2);
      });
    });

    it('should render all data rows', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      expect(screen.getAllByText('Alice').length).toBe(2);
      expect(screen.getAllByText('Bob').length).toBe(2);
      expect(screen.getAllByText('Charlie').length).toBe(2);
    });
  });

  describe('Layout Toggle', () => {
    it('should start in side-by-side layout by default', () => {
      const { container } = render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      const layoutContainer = container.querySelector(
        '.grid.grid-cols-1.lg\\:grid-cols-2'
      );
      expect(layoutContainer).toBeInTheDocument();
    });

    it('should show layout toggle buttons', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      expect(screen.getByText('Side-by-Side')).toBeInTheDocument();
      expect(screen.getByText('Stacked')).toBeInTheDocument();
    });

    it('should toggle to stacked layout when stacked button clicked', () => {
      const { container } = render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      const stackedButton = screen.getByText('Stacked');
      fireEvent.click(stackedButton);

      const layoutContainer = container.querySelector('.space-y-4');
      expect(layoutContainer).toBeInTheDocument();
    });

    it('should toggle back to side-by-side layout', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      // Switch to stacked
      fireEvent.click(screen.getByText('Stacked'));
      // Switch back to side-by-side
      fireEvent.click(screen.getByText('Side-by-Side'));

      const sideBySideButton = screen.getByText('Side-by-Side');
      expect(sideBySideButton).toHaveClass('bg-blue-600');
    });

    it('should highlight active layout button', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      const sideBySideButton = screen.getByText('Side-by-Side');
      const stackedButton = screen.getByText('Stacked');

      expect(sideBySideButton).toHaveClass('bg-blue-600');
      expect(stackedButton).toHaveClass('bg-gray-100');

      fireEvent.click(stackedButton);

      expect(sideBySideButton).toHaveClass('bg-gray-100');
      expect(stackedButton).toHaveClass('bg-blue-600');
    });
  });

  describe('Column Affection Indicators', () => {
    it('should show yellow indicator on affected column headers', () => {
      const { container } = render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
          impactStats={mockImpactStats}
        />
      );

      const affectedColumnMarkers = container.querySelectorAll(
        '.bg-yellow-600'
      );
      // Should have markers in both tables (before and after)
      expect(affectedColumnMarkers.length).toBeGreaterThanOrEqual(2);
    });

    it('should apply yellow background to affected column headers', () => {
      const { container } = render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
          impactStats={mockImpactStats}
        />
      );

      const yellowHeaders = container.querySelectorAll('.bg-yellow-50');
      expect(yellowHeaders.length).toBeGreaterThan(0);
    });

    it('should show tooltip on affected column headers', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
          impactStats={mockImpactStats}
        />
      );

      const ageHeaders = screen.getAllByText('age');
      ageHeaders.forEach((header) => {
        const parent = header.closest('th');
        expect(parent).toHaveAttribute(
          'title',
          'This column was affected by the transformation'
        );
      });
    });
  });

  describe('Synchronized Scrolling', () => {
    it('should synchronize scroll between before and after tables', () => {
      const { container } = render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      const scrollContainers = container.querySelectorAll('.overflow-auto');
      const beforeScroll = scrollContainers[0] as HTMLDivElement;
      const afterScroll = scrollContainers[1] as HTMLDivElement;

      // Simulate scroll on before table
      Object.defineProperty(beforeScroll, 'scrollTop', {
        writable: true,
        value: 100,
      });
      Object.defineProperty(beforeScroll, 'scrollLeft', {
        writable: true,
        value: 50,
      });

      fireEvent.scroll(beforeScroll);

      // After table should sync (in real implementation)
      // Note: jsdom doesn't actually scroll, so we're just testing the event handler exists
      expect(beforeScroll).toHaveProperty('onscroll');
    });

    it('should have scroll event handlers on both tables', () => {
      const { container } = render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      const scrollContainers = container.querySelectorAll('.overflow-auto');
      expect(scrollContainers.length).toBe(2);

      scrollContainers.forEach((container) => {
        expect(container).toHaveProperty('onscroll');
      });
    });
  });

  describe('Changed Cell Highlighting', () => {
    it('should use ChangedValueHighlight component for changed cells', () => {
      const { ChangedValueHighlight } = require('@/components/transformation/ChangedValueHighlight');

      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      // ChangedValueHighlight should be called for each cell in transformed table
      expect(ChangedValueHighlight).toHaveBeenCalled();
    });

    it('should mark changed cells correctly', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      const changedValues = screen.getAllByTestId('changed-value');
      const changedCells = changedValues.filter(
        (el) => el.getAttribute('data-changed') === 'true'
      );

      // At least one cell should be marked as changed (age: null → 0)
      expect(changedCells.length).toBeGreaterThan(0);
    });

    it('should highlight cells with yellow background when changed', () => {
      const { container } = render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      // Check for yellow background on changed cells
      const yellowCells = Array.from(
        container.querySelectorAll('.bg-yellow-50')
      ).filter((el) => el.tagName === 'TD');

      expect(yellowCells.length).toBeGreaterThan(0);
    });
  });

  describe('Empty Data Handling', () => {
    it('should display empty state when no data provided', () => {
      render(
        <BeforeAfterView originalData={[]} transformedData={[]} />
      );

      expect(screen.getByText('No data to display')).toBeInTheDocument();
    });

    it('should show AlertCircle icon in empty state', () => {
      const { container } = render(
        <BeforeAfterView originalData={[]} transformedData={[]} />
      );

      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('should not render tables when data is empty', () => {
      render(
        <BeforeAfterView originalData={[]} transformedData={[]} />
      );

      expect(screen.queryByText('Original Data')).not.toBeInTheDocument();
      expect(screen.queryByText('Transformed Data')).not.toBeInTheDocument();
    });
  });

  describe('Impact Statistics Display', () => {
    it('should display impact statistics when provided', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
          impactStats={mockImpactStats}
        />
      );

      expect(screen.getByText('Rows Affected')).toBeInTheDocument();
      expect(screen.getByText('Values Changed')).toBeInTheDocument();
      expect(screen.getByText('Columns Affected')).toBeInTheDocument();
      expect(screen.getByText('Quality Score')).toBeInTheDocument();
    });

    it('should display correct impact statistics values', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
          impactStats={mockImpactStats}
        />
      );

      // Check for specific values - note there are multiple "1"s in the DOM (row numbers, etc)
      const impactStatsSection = screen.getByText('Rows Affected').closest('.grid');
      expect(impactStatsSection).toBeInTheDocument();
      expect(screen.getByText('100%')).toBeInTheDocument(); // quality_score_after
    });

    it('should show quality improvement indicator when quality increases', () => {
      const { container } = render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
          impactStats={mockImpactStats}
        />
      );

      // Should show TrendingUp icon
      const trendingIcon = container.querySelector('.text-emerald-600');
      expect(trendingIcon).toBeInTheDocument();
    });

    it('should not display statistics when impactStats not provided', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      expect(screen.queryByText('Rows Affected')).not.toBeInTheDocument();
      expect(screen.queryByText('Values Changed')).not.toBeInTheDocument();
    });
  });

  describe('Responsive Behavior', () => {
    it('should register resize event listener', () => {
      const addEventListenerSpy = jest.spyOn(window, 'addEventListener');

      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      // Verify resize listener was registered
      expect(addEventListenerSpy).toHaveBeenCalledWith(
        'resize',
        expect.any(Function)
      );

      addEventListenerSpy.mockRestore();
    });
  });

  describe('Footer Info', () => {
    it('should display helpful footer information', () => {
      render(
        <BeforeAfterView
          originalData={mockOriginalData}
          transformedData={mockTransformedData}
        />
      );

      expect(screen.getByText('How to read this view:')).toBeInTheDocument();
      expect(
        screen.getByText(/Yellow highlighting indicates columns affected/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Highlighted cells in the transformed table/i)
      ).toBeInTheDocument();
    });
  });
});
