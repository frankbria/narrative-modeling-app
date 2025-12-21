import { render, screen, fireEvent } from '@testing-library/react';
import { TransformationHistory } from '@/components/transformation/TransformationHistory';
import { HistoryEntry } from '@/lib/types/history';

describe('TransformationHistory', () => {
  const mockHistory: HistoryEntry[] = [
    {
      position: 0,
      transformationType: 'Remove Nulls',
      description: 'Removed null values from Age column',
      timestamp: new Date('2025-12-20T10:00:00Z').toISOString(),
      affectedColumns: ['Age'],
      rowsAffected: 150
    },
    {
      position: 1,
      transformationType: 'Normalize',
      description: 'Normalized Income column',
      timestamp: new Date('2025-12-20T10:05:00Z').toISOString(),
      affectedColumns: ['Income'],
      rowsAffected: 200
    },
    {
      position: 2,
      transformationType: 'One-Hot Encode',
      description: 'Encoded Category column',
      timestamp: new Date('2025-12-20T10:10:00Z').toISOString(),
      affectedColumns: ['Category'],
      rowsAffected: 200
    }
  ];

  const mockOnJumpToPosition = jest.fn();
  const mockOnClearHistory = jest.fn();

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should render history panel title', () => {
    render(
      <TransformationHistory
        datasetId="test-dataset"
        history={mockHistory}
        currentPosition={1}
        onJumpToPosition={mockOnJumpToPosition}
        onClearHistory={mockOnClearHistory}
      />
    );

    expect(screen.getByText('Transformation History')).toBeInTheDocument();
  });

  it('should render transformation count', () => {
    render(
      <TransformationHistory
        datasetId="test-dataset"
        history={mockHistory}
        currentPosition={1}
        onJumpToPosition={mockOnJumpToPosition}
        onClearHistory={mockOnClearHistory}
      />
    );

    expect(screen.getByText('3 transformations')).toBeInTheDocument();
  });

  it('should render singular transformation count', () => {
    render(
      <TransformationHistory
        datasetId="test-dataset"
        history={[mockHistory[0]]}
        currentPosition={0}
        onJumpToPosition={mockOnJumpToPosition}
        onClearHistory={mockOnClearHistory}
      />
    );

    expect(screen.getByText('1 transformation')).toBeInTheDocument();
  });

  it('should render all history items', () => {
    render(
      <TransformationHistory
        datasetId="test-dataset"
        history={mockHistory}
        currentPosition={1}
        onJumpToPosition={mockOnJumpToPosition}
        onClearHistory={mockOnClearHistory}
      />
    );

    expect(screen.getByText('Remove Nulls')).toBeInTheDocument();
    expect(screen.getByText('Normalize')).toBeInTheDocument();
    expect(screen.getByText('One-Hot Encode')).toBeInTheDocument();
  });

  it('should call onJumpToPosition when history item clicked', () => {
    render(
      <TransformationHistory
        datasetId="test-dataset"
        history={mockHistory}
        currentPosition={1}
        onJumpToPosition={mockOnJumpToPosition}
        onClearHistory={mockOnClearHistory}
      />
    );

    const firstItem = screen.getByText('Remove Nulls').closest('div');
    fireEvent.click(firstItem!);

    expect(mockOnJumpToPosition).toHaveBeenCalledWith(0);
  });

  it('should call onClearHistory when clear button clicked', () => {
    render(
      <TransformationHistory
        datasetId="test-dataset"
        history={mockHistory}
        currentPosition={1}
        onJumpToPosition={mockOnJumpToPosition}
        onClearHistory={mockOnClearHistory}
      />
    );

    const clearButton = screen.getByRole('button', { name: /clear history/i });
    fireEvent.click(clearButton);

    expect(mockOnClearHistory).toHaveBeenCalledTimes(1);
  });

  it('should not render clear button when history is empty', () => {
    render(
      <TransformationHistory
        datasetId="test-dataset"
        history={[]}
        currentPosition={0}
        onJumpToPosition={mockOnJumpToPosition}
        onClearHistory={mockOnClearHistory}
      />
    );

    expect(
      screen.queryByRole('button', { name: /clear history/i })
    ).not.toBeInTheDocument();
  });

  it('should highlight current position', () => {
    const { container } = render(
      <TransformationHistory
        datasetId="test-dataset"
        history={mockHistory}
        currentPosition={1}
        onJumpToPosition={mockOnJumpToPosition}
        onClearHistory={mockOnClearHistory}
      />
    );

    // Find the second item (position 1) and check if it has current styling
    const items = container.querySelectorAll('[class*="bg-primary"]');
    expect(items.length).toBeGreaterThan(0);
  });

  it('should render empty state when no history', () => {
    render(
      <TransformationHistory
        datasetId="test-dataset"
        history={[]}
        currentPosition={0}
        onJumpToPosition={mockOnJumpToPosition}
        onClearHistory={mockOnClearHistory}
      />
    );

    expect(screen.getByText('0 transformations')).toBeInTheDocument();
  });

  it('should pass correct position to onJumpToPosition for each item', () => {
    render(
      <TransformationHistory
        datasetId="test-dataset"
        history={mockHistory}
        currentPosition={1}
        onJumpToPosition={mockOnJumpToPosition}
        onClearHistory={mockOnClearHistory}
      />
    );

    // Click second item
    const secondItem = screen.getByText('Normalize').closest('div');
    fireEvent.click(secondItem!);
    expect(mockOnJumpToPosition).toHaveBeenCalledWith(1);

    // Click third item
    const thirdItem = screen.getByText('One-Hot Encode').closest('div');
    fireEvent.click(thirdItem!);
    expect(mockOnJumpToPosition).toHaveBeenCalledWith(2);
  });
});
