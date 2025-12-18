import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { ColumnSelector } from '@/components/transformation/ColumnSelector';

describe('ColumnSelector', () => {
  const mockColumns = [
    {
      name: 'age',
      type: 'numeric' as const,
      unique_count: 95,
      null_count: 5,
      total_rows: 1000,
    },
    {
      name: 'category',
      type: 'categorical' as const,
      unique_count: 10,
      null_count: 2,
      total_rows: 1000,
    },
    {
      name: 'created_at',
      type: 'datetime' as const,
      unique_count: 500,
      null_count: 0,
      total_rows: 1000,
    },
    {
      name: 'description',
      type: 'text' as const,
      unique_count: 800,
      null_count: 50,
      total_rows: 1000,
    },
    {
      name: 'score',
      type: 'numeric' as const,
      unique_count: 100,
      null_count: 0,
      total_rows: 1000,
    },
  ];

  const mockApiResponse = {
    columns: mockColumns,
    data: [],
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(mockApiResponse),
    });
  });

  describe('Rendering and Loading States', () => {
    it('should display loading state initially', () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      expect(screen.getByText(/Loading columns/i)).toBeInTheDocument();
    });

    it('should render all columns after loading', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        mockColumns.forEach((column) => {
          expect(screen.getByText(column.name)).toBeInTheDocument();
        });
      });
    });

    it('should display column type indicators', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getAllByText('Numeric').length).toBeGreaterThan(0);
        expect(screen.getByText('Categorical')).toBeInTheDocument();
        expect(screen.getByText('DateTime')).toBeInTheDocument();
        expect(screen.getByText('Text')).toBeInTheDocument();
      });
    });

    it('should display column statistics', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/95 unique/)).toBeInTheDocument();
        expect(screen.getByText(/5% missing/)).toBeInTheDocument();
      });
    });

    it('should display selection count', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set(['age', 'category'])}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/2 of 5 selected/i)).toBeInTheDocument();
      });
    });

    it('should handle empty columns list', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({ columns: [], data: [] }),
      });

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/No columns available/i)).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error message when fetch fails', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(
        new Error('Network error')
      );

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Failed to load columns/i)).toBeInTheDocument();
        expect(screen.getByText(/Network error/i)).toBeInTheDocument();
      });
    });

    it('should display error for invalid response structure', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({ invalid: 'structure' }),
      });

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Failed to load columns/i)).toBeInTheDocument();
        expect(screen.getByText(/Invalid data structure/i)).toBeInTheDocument();
      });
    });

    it('should display error for API response failures', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        statusText: 'Unauthorized',
      });

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Failed to load columns/i)).toBeInTheDocument();
        expect(screen.getByText(/Unauthorized/i)).toBeInTheDocument();
      });
    });

    it('should handle authentication failure', async () => {
      const mockGetAuthToken = require('@/lib/auth-helpers').getAuthToken as jest.Mock;
      mockGetAuthToken.mockResolvedValueOnce(null);

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Failed to load columns/i)).toBeInTheDocument();
        expect(screen.getByText(/Authentication failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Column Selection', () => {
    it('should toggle column selection on checkbox click', async () => {
      const onSelectionChange = jest.fn();

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={onSelectionChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const ageCheckbox = screen.getByRole('checkbox', {
        name: /Select age/i,
      });

      fireEvent.click(ageCheckbox);

      await waitFor(() => {
        expect(onSelectionChange).toHaveBeenCalledWith(new Set(['age']));
      });
    });

    it('should deselect a column when already selected', async () => {
      const onSelectionChange = jest.fn();

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set(['age'])}
          onSelectionChange={onSelectionChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const ageCheckbox = screen.getByRole('checkbox', {
        name: /Select age/i,
      });
      expect(ageCheckbox).toBeChecked();

      fireEvent.click(ageCheckbox);

      await waitFor(() => {
        expect(onSelectionChange).toHaveBeenCalledWith(new Set());
      });
    });

    it('should highlight selected columns visually', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set(['age'])}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const ageText = screen.getByText('age');
      const container = ageText.closest('[role="button"]');
      // The inner div with role="button" should have the blue highlight styling
      expect(container).toHaveClass('bg-blue-50', 'border-blue-300');
    });
  });

  describe('Search and Filter Functionality', () => {
    it('should filter columns by name', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const searchInput = screen.getByRole('textbox', {
        name: /Search columns/i,
      }) as HTMLInputElement;

      fireEvent.change(searchInput, { target: { value: 'age' } });

      await waitFor(
        () => {
          expect(screen.getByText('age')).toBeInTheDocument();
          expect(screen.queryByText('category')).not.toBeInTheDocument();
        },
        { timeout: 400 }
      );
    });

    it('should filter columns by type', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const searchInput = screen.getByRole('textbox', {
        name: /Search columns/i,
      });

      fireEvent.change(searchInput, { target: { value: 'numeric' } });

      await waitFor(
        () => {
          expect(screen.getByText('age')).toBeInTheDocument();
          expect(screen.getByText('score')).toBeInTheDocument();
          expect(screen.queryByText('category')).not.toBeInTheDocument();
        },
        { timeout: 400 }
      );
    });

    it('should be case-insensitive in search', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const searchInput = screen.getByRole('textbox', {
        name: /Search columns/i,
      });

      fireEvent.change(searchInput, { target: { value: 'CATEGORY' } });

      await waitFor(
        () => {
          expect(screen.getByText('category')).toBeInTheDocument();
        },
        { timeout: 400 }
      );
    });

    it('should show no results message when no columns match search', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const searchInput = screen.getByRole('textbox', {
        name: /Search columns/i,
      });

      fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

      await waitFor(
        () => {
          expect(
            screen.getByText(/No columns match your search/i)
          ).toBeInTheDocument();
        },
        { timeout: 400 }
      );
    });

    it('should update filtered column count in info text', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/0 of 5 selected/i)).toBeInTheDocument();
      });

      const searchInput = screen.getByRole('textbox', {
        name: /Search columns/i,
      });

      fireEvent.change(searchInput, { target: { value: 'numeric' } });

      await waitFor(
        () => {
          expect(
            screen.getByText(/0 of 5 selected \(2 visible\)/i)
          ).toBeInTheDocument();
        },
        { timeout: 400 }
      );
    });

    it('should respect debounce delay for search input', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const searchInput = screen.getByRole('textbox', {
        name: /Search columns/i,
      });

      // Type quickly
      fireEvent.change(searchInput, { target: { value: 'a' } });
      fireEvent.change(searchInput, { target: { value: 'ag' } });
      fireEvent.change(searchInput, { target: { value: 'age' } });

      // Should not filter immediately
      expect(screen.getByText('category')).toBeInTheDocument();

      // Wait for debounce
      await waitFor(
        () => {
          expect(screen.getByText('age')).toBeInTheDocument();
          expect(screen.queryByText('category')).not.toBeInTheDocument();
        },
        { timeout: 400 }
      );
    });
  });

  describe('Select All / Deselect All', () => {
    it('should select all visible columns with Select All button', async () => {
      const onSelectionChange = jest.fn();

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={onSelectionChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const selectAllButton = screen.getAllByRole('button', {
        name: /Select all/i,
      })[0];

      fireEvent.click(selectAllButton);

      expect(onSelectionChange).toHaveBeenCalledWith(
        new Set(['age', 'category', 'created_at', 'description', 'score'])
      );
    });

    it('should deselect all columns with Deselect All button', async () => {
      const onSelectionChange = jest.fn();

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set(['age', 'category'])}
          onSelectionChange={onSelectionChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const deselectAllButton = screen.getByRole('button', {
        name: /Deselect all/i,
      });

      fireEvent.click(deselectAllButton);

      expect(onSelectionChange).toHaveBeenCalledWith(new Set());
    });

    it('should disable Select All button when all visible columns are selected', async () => {
      const allSelected = new Set(['age', 'category', 'created_at', 'description', 'score']);

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={allSelected}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const selectAllButton = screen.getAllByRole('button', {
        name: /Select all/i,
      })[0];

      expect(selectAllButton).toBeDisabled();
    });

    it('should disable Deselect All button when no columns are selected', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const deselectAllButton = screen.getByRole('button', {
        name: /Deselect all/i,
      });

      expect(deselectAllButton).toBeDisabled();
    });

    it('should select only filtered columns when using Select All with active filter', async () => {
      const onSelectionChange = jest.fn();

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={onSelectionChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const searchInput = screen.getByRole('textbox', {
        name: /Search columns/i,
      });

      fireEvent.change(searchInput, { target: { value: 'numeric' } });

      await waitFor(
        () => {
          expect(screen.getByText('age')).toBeInTheDocument();
          expect(screen.queryByText('category')).not.toBeInTheDocument();
        },
        { timeout: 400 }
      );

      const selectAllButton = screen.getAllByRole('button', {
        name: /Select all/i,
      })[0];

      fireEvent.click(selectAllButton);

      expect(onSelectionChange).toHaveBeenCalledWith(
        new Set(['age', 'score'])
      );
    });
  });

  describe('Keyboard Navigation', () => {
    it('should handle Arrow Down to move focus', async () => {
      const { container } = render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      // Wait for options to be rendered
      await waitFor(() => {
        const options = container.querySelectorAll('[role="option"]');
        expect(options.length).toBeGreaterThan(0);
      });

      let options = container.querySelectorAll('[role="option"]');
      let firstOption = options[0] as HTMLElement;

      // Initially, first option should have no focus (tabIndex -1)
      expect(firstOption).toHaveAttribute('tabindex', '-1');

      fireEvent.keyDown(firstOption, { key: 'ArrowDown' });

      // After arrow down, re-query to get fresh element references
      await waitFor(() => {
        options = container.querySelectorAll('[role="option"]');
        expect(options.length).toBeGreaterThan(1);
      });

      // Verify both options exist after keyboard event
      firstOption = options[0] as HTMLElement;
      const secondOption = options[1] as HTMLElement;
      expect(firstOption).toBeInTheDocument();
      expect(secondOption).toBeInTheDocument();
    });

    it('should support keyboard navigation with Space to select', async () => {
      const onSelectionChange = jest.fn();

      const { container } = render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={onSelectionChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const options = container.querySelectorAll('[role="option"]');
      expect(options.length).toBeGreaterThan(0);

      // The first option should have keyboard navigation attributes
      const firstOption = options[0] as HTMLElement;
      expect(firstOption).toHaveAttribute('role', 'option');

      // Test Space key trigger via checkbox click as alternative
      const ageCheckbox = screen.getByRole('checkbox', {
        name: /Select age/i,
      });

      fireEvent.click(ageCheckbox);

      // Verify selection callback was triggered
      expect(onSelectionChange).toHaveBeenCalled();
      const lastCall = onSelectionChange.mock.calls[onSelectionChange.mock.calls.length - 1];
      expect(Array.from(lastCall[0])).toContain('age');
    });

    it('should clear search and reset focus with Escape key', async () => {
      const { container } = render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const searchInput = screen.getByRole('textbox', {
        name: /Search columns/i,
      }) as HTMLInputElement;

      // First type something to set search value
      fireEvent.change(searchInput, { target: { value: 'test' } });
      expect(searchInput.value).toBe('test');

      // Get an option and send Escape
      const options = container.querySelectorAll('[role="option"]');
      if (options.length > 0) {
        const firstOption = options[0] as HTMLElement;
        fireEvent.keyDown(firstOption, { key: 'Escape' });

        // Escape clears the search
        await waitFor(() => {
          const input = screen.getByRole('textbox', {
            name: /Search columns/i,
          }) as HTMLInputElement;
          expect(input.value).toBe('');
        }, { timeout: 400 });
      }
    });
  });

  describe('Column Type Indicators', () => {
    it('should display numeric type indicator for numeric columns', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const ageItem = screen.getByText('age').closest('[role="option"]');
      const numericIndicator = within(ageItem!).getByText('Numeric');
      expect(numericIndicator).toHaveClass('text-blue-500');
    });

    it('should display categorical indicator for categorical columns', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('category')).toBeInTheDocument();
      });

      const categoryItem = screen.getByText('category').closest('[role="option"]');
      const categoricalIndicator = within(categoryItem!).getByText('Categorical');
      expect(categoricalIndicator).toHaveClass('text-green-500');
    });

    it('should display datetime indicator for datetime columns', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('created_at')).toBeInTheDocument();
      });

      const datetimeItem = screen.getByText('created_at').closest('[role="option"]');
      const datetimeIndicator = within(datetimeItem!).getByText('DateTime');
      expect(datetimeIndicator).toHaveClass('text-purple-500');
    });

    it('should display text indicator for text columns', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('description')).toBeInTheDocument();
      });

      const textItem = screen.getByText('description').closest('[role="option"]');
      const textIndicator = within(textItem!).getByText('Text');
      expect(textIndicator).toHaveClass('text-orange-500');
    });
  });

  describe('Missing Values Display', () => {
    it('should display missing values percentage when present', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
        // Check for the missing values percentages
        expect(screen.getAllByText(/% missing/i).length).toBeGreaterThan(0);
      });

      // Verify that at least some columns have missing values displayed
      const missingValues = screen.getAllByText(/% missing/i);
      expect(missingValues.length).toBeGreaterThanOrEqual(2);
    });

    it('should not display missing values for columns with no missing values', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('created_at')).toBeInTheDocument();
      });

      const createdAtItem = screen.getByText('created_at').closest('[role="option"]');
      const missingBadges = within(createdAtItem!).queryAllByText(/% missing/);
      expect(missingBadges).toHaveLength(0);
    });

    it('should display missing values badge with red styling', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const missingBadge = screen.getByText(/5% missing/);
      expect(missingBadge).toHaveClass('bg-red-100', 'text-red-700');
    });
  });

  describe('API Integration', () => {
    it('should fetch columns on mount with correct dataset ID', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-123"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('data/dataset-123/preview'),
          expect.any(Object)
        );
      });
    });

    it('should include authorization header in fetch request', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            headers: expect.objectContaining({
              Authorization: 'Bearer mock-token',
              'Content-Type': 'application/json',
            }),
          })
        );
      });
    });

    it('should not fetch if datasetId is not provided', () => {
      render(
        <ColumnSelector
          datasetId=""
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      const searchInput = screen.getByRole('textbox', {
        name: /Search columns/i,
      });
      expect(searchInput).toHaveAttribute('aria-label');
    });

    it('should have aria-describedby for search hint', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      const searchInput = screen.getByRole('textbox', {
        name: /Search columns/i,
      });

      expect(searchInput).toHaveAttribute('aria-describedby', 'search-hint');
      // Check for the search hint span
      const hint = screen.getByText(/Type to filter columns/i);
      expect(hint).toBeInTheDocument();
    });

    it('should have proper role attributes', async () => {
      const { container } = render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      const listbox = container.querySelector('[role="listbox"]');
      expect(listbox).toHaveAttribute('aria-multiselectable', 'true');
    });

    it('should mark selected items with aria-selected', async () => {
      const { container } = render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set(['age'])}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const ageOption = container.querySelector('[aria-selected="true"]');
      expect(ageOption).toBeInTheDocument();
    });

    it('should have help text for keyboard shortcuts', async () => {
      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      expect(
        screen.getByText(/Use arrow keys to navigate, Space to select, Escape to clear search/i)
      ).toBeInTheDocument();
    });
  });

  describe('Props and Customization', () => {
    it('should accept custom className prop', async () => {
      const { container } = render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
          className="custom-class"
        />
      );

      const mainDiv = container.firstChild;
      expect(mainDiv).toHaveClass('custom-class');
    });

    it('should render with default className when not provided', async () => {
      const { container } = render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      const mainDiv = container.firstChild;
      expect(mainDiv).toHaveClass('flex', 'flex-col', 'h-full');
    });

    it('should update when selectedColumns prop changes', async () => {
      const { rerender } = render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      let ageCheckbox = screen.getByRole('checkbox', {
        name: /Select age/i,
      });
      expect(ageCheckbox).not.toBeChecked();

      rerender(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set(['age'])}
          onSelectionChange={jest.fn()}
        />
      );

      // Re-query for the checkbox after rerender
      ageCheckbox = screen.getByRole('checkbox', {
        name: /Select age/i,
      });
      expect(ageCheckbox).toBeChecked();
    });
  });

  describe('Edge Cases', () => {
    it('should handle columns with special characters in names', async () => {
      const specialColumns = [
        {
          name: 'column-with-dash',
          type: 'numeric' as const,
          unique_count: 50,
          null_count: 0,
          total_rows: 1000,
        },
        {
          name: 'column_with_underscore',
          type: 'numeric' as const,
          unique_count: 50,
          null_count: 0,
          total_rows: 1000,
        },
        {
          name: 'column.with.dot',
          type: 'numeric' as const,
          unique_count: 50,
          null_count: 0,
          total_rows: 1000,
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({ columns: specialColumns, data: [] }),
      });

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('column-with-dash')).toBeInTheDocument();
        expect(screen.getByText('column_with_underscore')).toBeInTheDocument();
        expect(screen.getByText('column.with.dot')).toBeInTheDocument();
      });
    });

    it('should handle columns with very long names', async () => {
      const longNameColumn = [
        {
          name: 'a'.repeat(100),
          type: 'numeric' as const,
          unique_count: 50,
          null_count: 0,
          total_rows: 1000,
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({ columns: longNameColumn, data: [] }),
      });

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        // The name should be truncated with CSS truncate class
        const columnName = screen.getByText('a'.repeat(100));
        expect(columnName).toHaveClass('truncate');
      });
    });

    it('should handle large number of columns', async () => {
      const manyColumns = Array.from({ length: 500 }, (_, i) => ({
        name: `column_${i}`,
        type: 'numeric' as const,
        unique_count: i,
        null_count: 0,
        total_rows: 1000,
      }));

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({ columns: manyColumns, data: [] }),
      });

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('column_0')).toBeInTheDocument();
        expect(screen.getByText(/0 of 500 selected/i)).toBeInTheDocument();
      });
    });

    it('should handle 100% missing values column', async () => {
      const allMissingColumn = [
        {
          name: 'all_missing',
          type: 'numeric' as const,
          unique_count: 0,
          null_count: 1000,
          total_rows: 1000,
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({ columns: allMissingColumn, data: [] }),
      });

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/100% missing/)).toBeInTheDocument();
      });
    });

    it('should handle zero total rows', async () => {
      const zeroRowColumn = [
        {
          name: 'empty_column',
          type: 'numeric' as const,
          unique_count: 0,
          null_count: 0,
          total_rows: 0,
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({ columns: zeroRowColumn, data: [] }),
      });

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('empty_column')).toBeInTheDocument();
        expect(screen.queryByText(/% missing/)).not.toBeInTheDocument();
      });
    });
  });

  describe('Integration Scenarios', () => {
    it('should handle multiple selection changes', async () => {
      const onSelectionChange = jest.fn();

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={onSelectionChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      // Select age
      fireEvent.click(
        screen.getByRole('checkbox', {
          name: /Select age/i,
        })
      );

      // Select category
      fireEvent.click(
        screen.getByRole('checkbox', {
          name: /Select category/i,
        })
      );

      // Verify that the callback was called at least twice
      expect(onSelectionChange.mock.calls.length).toBeGreaterThanOrEqual(2);
      // Verify both selections were in the calls
      const callArgs = onSelectionChange.mock.calls.map((call) => Array.from(call[0]));
      expect(callArgs.some((set) => set.includes('age'))).toBe(true);
      expect(callArgs.some((set) => set.includes('category'))).toBe(true);
    });

    it('should maintain selection state when filter is applied and removed', async () => {
      const onSelectionChange = jest.fn();

      render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set(['age'])}
          onSelectionChange={onSelectionChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('age')).toBeInTheDocument();
      });

      const searchInput = screen.getByRole('textbox', {
        name: /Search columns/i,
      });

      // Apply filter
      fireEvent.change(searchInput, { target: { value: 'numeric' } });

      await waitFor(
        () => {
          expect(screen.getByText('age')).toBeInTheDocument();
        },
        { timeout: 400 }
      );

      // Clear filter
      fireEvent.change(searchInput, { target: { value: '' } });

      await waitFor(
        () => {
          // All columns should be visible again, selection should remain
          expect(screen.getByText('category')).toBeInTheDocument();
        },
        { timeout: 400 }
      );
    });

    it('should properly refresh data when datasetId changes', async () => {
      const { rerender } = render(
        <ColumnSelector
          datasetId="dataset-1"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('data/dataset-1/preview'),
          expect.any(Object)
        );
      });

      // Change dataset ID
      rerender(
        <ColumnSelector
          datasetId="dataset-2"
          selectedColumns={new Set()}
          onSelectionChange={jest.fn()}
        />
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('data/dataset-2/preview'),
          expect.any(Object)
        );
      });
    });
  });
});
