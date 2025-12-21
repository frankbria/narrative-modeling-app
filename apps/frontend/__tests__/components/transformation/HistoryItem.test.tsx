import { render, screen, fireEvent } from '@testing-library/react';
import { HistoryItem } from '@/components/transformation/HistoryItem';
import { HistoryEntry } from '@/lib/types/history';

describe('HistoryItem', () => {
  const mockEntry: HistoryEntry = {
    position: 1,
    transformationType: 'Remove Nulls',
    description: 'Removed null values from Age column',
    timestamp: new Date('2025-12-20T10:00:00Z').toISOString(),
    affectedColumns: ['Age', 'Income'],
    rowsAffected: 150
  };

  const mockOnClick = jest.fn();

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should render transformation type', () => {
    render(
      <HistoryItem entry={mockEntry} isCurrent={false} onClick={mockOnClick} />
    );

    expect(screen.getByText('Remove Nulls')).toBeInTheDocument();
  });

  it('should render description', () => {
    render(
      <HistoryItem entry={mockEntry} isCurrent={false} onClick={mockOnClick} />
    );

    expect(
      screen.getByText('Removed null values from Age column')
    ).toBeInTheDocument();
  });

  it('should render affected columns as badges', () => {
    render(
      <HistoryItem entry={mockEntry} isCurrent={false} onClick={mockOnClick} />
    );

    expect(screen.getByText('Age')).toBeInTheDocument();
    expect(screen.getByText('Income')).toBeInTheDocument();
  });

  it('should render rows affected', () => {
    render(
      <HistoryItem entry={mockEntry} isCurrent={false} onClick={mockOnClick} />
    );

    expect(screen.getByText('150 rows affected')).toBeInTheDocument();
  });

  it('should render relative timestamp', () => {
    render(
      <HistoryItem entry={mockEntry} isCurrent={false} onClick={mockOnClick} />
    );

    // Since the timestamp is in the past, it should show "ago"
    expect(screen.getByText(/ago$/)).toBeInTheDocument();
  });

  it('should call onClick when clicked', () => {
    render(
      <HistoryItem entry={mockEntry} isCurrent={false} onClick={mockOnClick} />
    );

    const item = screen.getByText('Remove Nulls').closest('div');
    fireEvent.click(item!);

    expect(mockOnClick).toHaveBeenCalledTimes(1);
  });

  it('should highlight when current', () => {
    const { container } = render(
      <HistoryItem entry={mockEntry} isCurrent={true} onClick={mockOnClick} />
    );

    const item = container.firstChild as HTMLElement;
    expect(item.className).toContain('bg-primary');
    expect(item.className).toContain('border-primary');
  });

  it('should not highlight when not current', () => {
    const { container } = render(
      <HistoryItem entry={mockEntry} isCurrent={false} onClick={mockOnClick} />
    );

    const item = container.firstChild as HTMLElement;
    expect(item.className).toContain('bg-muted');
    expect(item.className).not.toContain('border-primary');
  });

  it('should render without rows affected if not provided', () => {
    const entryWithoutRows: HistoryEntry = {
      ...mockEntry,
      rowsAffected: undefined
    };

    render(
      <HistoryItem
        entry={entryWithoutRows}
        isCurrent={false}
        onClick={mockOnClick}
      />
    );

    expect(screen.queryByText(/rows affected/)).not.toBeInTheDocument();
  });

  it('should render with empty affected columns', () => {
    const entryWithoutColumns: HistoryEntry = {
      ...mockEntry,
      affectedColumns: []
    };

    render(
      <HistoryItem
        entry={entryWithoutColumns}
        isCurrent={false}
        onClick={mockOnClick}
      />
    );

    expect(screen.queryByText('Age')).not.toBeInTheDocument();
    expect(screen.queryByText('Income')).not.toBeInTheDocument();
  });

  it('should have hover effect styling', () => {
    const { container } = render(
      <HistoryItem entry={mockEntry} isCurrent={false} onClick={mockOnClick} />
    );

    const item = container.firstChild as HTMLElement;
    expect(item.className).toContain('cursor-pointer');
    expect(item.className).toContain('hover:');
  });
});
