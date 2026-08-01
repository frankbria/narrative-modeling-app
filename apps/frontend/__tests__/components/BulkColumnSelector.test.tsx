/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { BulkColumnSelector } from '@/components/transformation/BulkColumnSelector';
import type { ColumnMetadata } from '@/lib/services/transformation';

// react-window is mocked project-wide by __mocks__/react-window.tsx, which jest
// applies automatically. The local override here duplicated it against the v1
// API (children/itemCount/itemSize) and so kept these tests green after the
// component moved to v2 — removed so this suite exercises the same v2-shaped
// mock as everything else (#390).
// Mock useDebounce hook
jest.mock('@/lib/hooks/useDebounce', () => ({
  useDebounce: (value: string) => value,
}));

const mockColumns: ColumnMetadata[] = [
  {
    column_name: 'age',
    field_type: 'numeric',
    missing_values: 5,
    unique_values: 50,
    is_constant: false,
    is_high_cardinality: false,
  },
  {
    column_name: 'name',
    field_type: 'text',
    missing_values: 0,
    unique_values: 100,
    is_constant: false,
    is_high_cardinality: true,
  },
  {
    column_name: 'salary',
    field_type: 'numeric',
    missing_values: 10,
    unique_values: 200,
    is_constant: false,
    is_high_cardinality: false,
  },
  {
    column_name: 'created_at',
    field_type: 'datetime',
    missing_values: 0,
    unique_values: 1000,
    is_constant: false,
    is_high_cardinality: true,
  },
  {
    column_name: 'constant_value',
    field_type: 'text',
    missing_values: 0,
    unique_values: 1,
    is_constant: true,
    is_high_cardinality: false,
  },
];

describe('BulkColumnSelector', () => {
  const mockOnSelectionChange = jest.fn();

  beforeEach(() => {
    mockOnSelectionChange.mockClear();
  });

  it('renders the component with columns', () => {
    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    expect(screen.getByText('Select Columns for Bulk Operation')).toBeInTheDocument();
    expect(screen.getByText('age')).toBeInTheDocument();
    expect(screen.getByText('name')).toBeInTheDocument();
    expect(screen.getByText('salary')).toBeInTheDocument();
  });

  it('displays column count correctly', () => {
    const selectedColumns = new Set(['age', 'name']);

    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={selectedColumns}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    expect(screen.getByText(/2 of 5 selected/)).toBeInTheDocument();
  });

  it('calls onSelectionChange when a column is clicked', async () => {
    const user = userEvent.setup();

    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    const ageColumn = screen.getByText('age').closest('div[role="button"]');
    if (ageColumn) {
      await user.click(ageColumn);
    }

    expect(mockOnSelectionChange).toHaveBeenCalledWith(new Set(['age']));
  });

  it('deselects a column when clicked again', async () => {
    const user = userEvent.setup();
    const selectedColumns = new Set(['age']);

    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={selectedColumns}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    const ageColumn = screen.getByText('age').closest('div[role="button"]');
    if (ageColumn) {
      await user.click(ageColumn);
    }

    expect(mockOnSelectionChange).toHaveBeenCalledWith(new Set());
  });

  it('handles Select All button', async () => {
    const user = userEvent.setup();

    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    const selectAllButton = screen.getByRole('button', { name: /^select all/i });
    await user.click(selectAllButton);

    expect(mockOnSelectionChange).toHaveBeenCalledWith(
      new Set(['age', 'name', 'salary', 'created_at', 'constant_value'])
    );
  });

  it('handles Deselect All button', async () => {
    const user = userEvent.setup();
    const selectedColumns = new Set(['age', 'name', 'salary']);

    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={selectedColumns}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    const deselectAllButton = screen.getByRole('button', { name: /deselect all/i });
    await user.click(deselectAllButton);

    expect(mockOnSelectionChange).toHaveBeenCalledWith(new Set());
  });

  it('filters columns by search term', async () => {
    const user = userEvent.setup();

    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    const searchInput = screen.getByPlaceholderText('Search by name or type...');
    await user.type(searchInput, 'age');

    // After search, only "age" should be visible in the filtered list
    expect(screen.getByText('age')).toBeInTheDocument();
    expect(screen.getByText(/1 visible/)).toBeInTheDocument();
  });

  it('displays missing values indicator', () => {
    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    // Age has 5 missing values
    expect(screen.getByText('5 missing')).toBeInTheDocument();
    // Salary has 10 missing values
    expect(screen.getByText('10 missing')).toBeInTheDocument();
  });

  it('displays constant column indicator', () => {
    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    expect(screen.getByText('Constant')).toBeInTheDocument();
  });

  it('displays high cardinality indicator', () => {
    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    const highCardinalityBadges = screen.getAllByText('High Cardinality');
    expect(highCardinalityBadges.length).toBe(2); // name and created_at
  });

  it('displays loading state', () => {
    render(
      <BulkColumnSelector
        columns={[]}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
        isLoading={true}
      />
    );

    expect(screen.getByText('Loading columns...')).toBeInTheDocument();
  });

  it('displays error state', () => {
    render(
      <BulkColumnSelector
        columns={[]}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
        error="Network error: unable to fetch column metadata"
      />
    );

    expect(screen.getByText('Network error: unable to fetch column metadata')).toBeInTheDocument();
  });

  it('displays empty state when no columns', () => {
    render(
      <BulkColumnSelector
        columns={[]}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    expect(screen.getByText('No columns available')).toBeInTheDocument();
  });

  it('displays type-specific icons', () => {
    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    // Use getAllByText since there are multiple numeric columns (age, salary)
    expect(screen.getAllByText('Numeric').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Text').length).toBeGreaterThan(0);
    expect(screen.getByText('DateTime')).toBeInTheDocument();
  });

  it('disables Select All when all columns are selected', () => {
    const allSelected = new Set(mockColumns.map(c => c.column_name));

    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={allSelected}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    const selectAllButton = screen.getByRole('button', { name: /^select all/i });
    expect(selectAllButton).toBeDisabled();
  });

  it('disables Deselect All when no columns are selected', () => {
    render(
      <BulkColumnSelector
        columns={mockColumns}
        selectedColumns={new Set()}
        onSelectionChange={mockOnSelectionChange}
      />
    );

    const deselectAllButton = screen.getByRole('button', { name: /deselect all/i });
    expect(deselectAllButton).toBeDisabled();
  });
});
