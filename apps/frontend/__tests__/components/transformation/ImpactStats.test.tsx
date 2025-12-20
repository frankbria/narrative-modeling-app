import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ImpactStats } from '@/components/transformation/ImpactStats';

describe('ImpactStats Component', () => {
  // Basic mock data for tests
  const basicImpactStats = {
    rows_affected: 1250,
    values_changed: 3847,
    columns_affected: ['age', 'salary', 'department'],
    quality_score_before: 0.72,
    quality_score_after: 0.88,
  };

  describe('Rendering', () => {
    it('should render the component with title', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      expect(screen.getByText('Impact Statistics')).toBeInTheDocument();
    });

    it('should display rows affected metric', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      expect(screen.getByText('Rows Affected')).toBeInTheDocument();
      expect(screen.getByText('1,250')).toBeInTheDocument();
    });

    it('should display values changed metric', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      expect(screen.getByText('Values Changed')).toBeInTheDocument();
      expect(screen.getByText('3,847')).toBeInTheDocument();
    });

    it('should display columns affected metric', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      expect(screen.getByText('Columns Affected')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('should list affected columns', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      expect(screen.getByText(/age.*salary.*department/i)).toBeInTheDocument();
    });

    it('should display quality score comparison title', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      expect(
        screen.getByText('Quality Score Comparison')
      ).toBeInTheDocument();
    });

    it('should display before and after labels', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      const labels = screen.getAllByText(/Before|After/);
      expect(labels.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('Quality Score Display', () => {
    it('should display quality scores as percentages', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      expect(screen.getByText('72%')).toBeInTheDocument();
      expect(screen.getByText('88%')).toBeInTheDocument();
    });

    it('should show improvement badge when quality increases', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      expect(screen.getByText(/improvement/i)).toBeInTheDocument();
      // Quality change: 0.88 - 0.72 = 0.16 => 16.0%
      expect(screen.getByText(/16\.0%\s+improvement/i)).toBeInTheDocument();
    });

    it('should show degradation badge when quality decreases', () => {
      const degradedStats = {
        ...basicImpactStats,
        quality_score_before: 0.92,
        quality_score_after: 0.78,
      };

      render(<ImpactStats impactStats={degradedStats} />);
      expect(screen.getByText(/degradation/i)).toBeInTheDocument();
      // Quality change: 0.78 - 0.92 = -0.14 => 14.0%
      expect(screen.getByText(/14\.0%\s+degradation/i)).toBeInTheDocument();
    });

    it('should not show change badge when quality is unchanged', () => {
      const unchangedStats = {
        ...basicImpactStats,
        quality_score_before: 0.85,
        quality_score_after: 0.85,
      };

      render(<ImpactStats impactStats={unchangedStats} />);
      expect(screen.getByText(/unchanged/i)).toBeInTheDocument();
      expect(screen.queryByText(/improvement|degradation/)).not.toBeInTheDocument();
    });
  });

  describe('Number Formatting', () => {
    it('should format large numbers with comma separators', () => {
      const largeStats = {
        ...basicImpactStats,
        rows_affected: 1000000,
        values_changed: 5000000,
      };

      render(<ImpactStats impactStats={largeStats} />);
      expect(screen.getByText('1,000,000')).toBeInTheDocument();
      expect(screen.getByText('5,000,000')).toBeInTheDocument();
    });

    it('should handle small numbers correctly', () => {
      const smallStats = {
        ...basicImpactStats,
        rows_affected: 5,
        values_changed: 10,
      };

      render(<ImpactStats impactStats={smallStats} />);
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
    });
  });

  describe('Columns Affected', () => {
    it('should display correct count of affected columns', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      const columnElements = screen.getAllByText('3');
      expect(columnElements.length).toBeGreaterThan(0);
    });

    it('should display "none" when no columns affected', () => {
      const noColumnsStats = {
        ...basicImpactStats,
        columns_affected: [],
      };

      render(<ImpactStats impactStats={noColumnsStats} />);
      expect(screen.getByText('none')).toBeInTheDocument();
    });

    it('should display single column name', () => {
      const singleColumnStats = {
        ...basicImpactStats,
        columns_affected: ['email'],
      };

      render(<ImpactStats impactStats={singleColumnStats} />);
      expect(screen.getByText('email')).toBeInTheDocument();
    });

    it('should display multiple column names separated by commas', () => {
      const multiColumnStats = {
        ...basicImpactStats,
        columns_affected: ['col1', 'col2', 'col3', 'col4'],
      };

      render(<ImpactStats impactStats={multiColumnStats} />);
      expect(screen.getByText(/col1.*col2.*col3.*col4/)).toBeInTheDocument();
    });
  });

  describe('Value Distributions', () => {
    const statsWithDistributions = {
      ...basicImpactStats,
      value_distributions: {
        status: {
          before: {
            'Active': 3000,
            'Inactive': 1500,
            'Pending': 500,
          },
          after: {
            'Active': 3500,
            'Inactive': 1200,
            'Pending': 300,
          },
        },
        category: {
          before: {
            'A': 1500,
            'B': 2000,
            'C': 1500,
          },
          after: {
            'A': 1800,
            'B': 2100,
            'C': 1100,
          },
        },
      },
    };

    it('should display value distribution section when provided', () => {
      render(<ImpactStats impactStats={statsWithDistributions} />);
      expect(
        screen.getByText('Value Distribution Changes')
      ).toBeInTheDocument();
    });

    it('should not display distribution section when not provided', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      expect(
        screen.queryByText('Value Distribution Changes')
      ).not.toBeInTheDocument();
    });

    it('should be collapsed by default', () => {
      render(<ImpactStats impactStats={statsWithDistributions} />);
      expect(screen.queryByText('status')).not.toBeInTheDocument();
      expect(screen.queryByText('Active')).not.toBeInTheDocument();
    });

    it('should expand distribution details on button click', () => {
      render(<ImpactStats impactStats={statsWithDistributions} />);

      const expandButton = screen.getByText('Value Distribution Changes');
      fireEvent.click(expandButton);

      expect(screen.getByText('status')).toBeInTheDocument();
      // "Active" appears twice (before and after), so use getAllByText
      expect(screen.getAllByText('Active')).toHaveLength(2);
    });

    it('should collapse distribution details on second click', () => {
      render(<ImpactStats impactStats={statsWithDistributions} />);

      const expandButton = screen.getByText('Value Distribution Changes');

      fireEvent.click(expandButton);
      // "Active" appears twice (before and after), so use getAllByText
      expect(screen.getAllByText('Active')).toHaveLength(2);

      fireEvent.click(expandButton);
      expect(screen.queryByText('Active')).not.toBeInTheDocument();
    });

    it('should display before and after counts for distributions', () => {
      render(<ImpactStats impactStats={statsWithDistributions} />);

      const expandButton = screen.getByText('Value Distribution Changes');
      fireEvent.click(expandButton);

      expect(screen.getByText('3000')).toBeInTheDocument();
      expect(screen.getByText('3500')).toBeInTheDocument();
    });

    it('should show column names in expanded distributions', () => {
      render(<ImpactStats impactStats={statsWithDistributions} />);

      const expandButton = screen.getByText('Value Distribution Changes');
      fireEvent.click(expandButton);

      expect(screen.getByText('status')).toBeInTheDocument();
      expect(screen.getByText('category')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero affected rows', () => {
      const zeroStats = {
        ...basicImpactStats,
        rows_affected: 0,
      };

      render(<ImpactStats impactStats={zeroStats} />);
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('should handle perfect quality score (1.0)', () => {
      const perfectStats = {
        ...basicImpactStats,
        quality_score_after: 1.0,
      };

      render(<ImpactStats impactStats={perfectStats} />);
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('should handle zero quality score', () => {
      const zeroQualityStats = {
        ...basicImpactStats,
        quality_score_before: 0.0,
        quality_score_after: 0.5,
      };

      render(<ImpactStats impactStats={zeroQualityStats} />);
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('should handle empty distributions object', () => {
      const emptyDistributions = {
        ...basicImpactStats,
        value_distributions: {},
      };

      render(<ImpactStats impactStats={emptyDistributions} />);
      expect(
        screen.queryByText('Value Distribution Changes')
      ).not.toBeInTheDocument();
    });

    it('should handle very long column names', () => {
      const longNameStats = {
        ...basicImpactStats,
        columns_affected: [
          'very_long_column_name_that_might_be_truncated',
          'another_very_long_name',
        ],
      };

      render(<ImpactStats impactStats={longNameStats} />);
      expect(screen.getByText('2')).toBeInTheDocument();
    });
  });

  describe('Responsive Layout', () => {
    it('should render metrics in a grid', () => {
      const { container } = render(<ImpactStats impactStats={basicImpactStats} />);
      const gridElement = container.querySelector('.grid.grid-cols-1.md\\:grid-cols-3');
      expect(gridElement).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper heading structure', () => {
      render(<ImpactStats impactStats={basicImpactStats} />);
      const heading = screen.getByText('Impact Statistics');
      expect(heading.tagName).toBe('H3');
    });

    it('should have descriptive button text for expansion', () => {
      render(<ImpactStats impactStats={{
        ...basicImpactStats,
        value_distributions: {
          test: { before: { a: 1 }, after: { a: 2 } },
        },
      }} />);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('Value Distribution Changes');
    });
  });
});
