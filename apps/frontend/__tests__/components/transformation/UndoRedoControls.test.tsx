import { render, screen, fireEvent } from '@testing-library/react';
import { UndoRedoControls } from '@/components/transformation/UndoRedoControls';

describe('UndoRedoControls', () => {
  const mockOnUndo = jest.fn();
  const mockOnRedo = jest.fn();

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should disable undo button when canUndo is false', () => {
    render(
      <UndoRedoControls
        canUndo={false}
        canRedo={true}
        onUndo={mockOnUndo}
        onRedo={mockOnRedo}
      />
    );

    const undoButton = screen.getByRole('button', { name: /undo/i });
    expect(undoButton).toBeDisabled();
  });

  it('should disable redo button when canRedo is false', () => {
    render(
      <UndoRedoControls
        canUndo={true}
        canRedo={false}
        onUndo={mockOnUndo}
        onRedo={mockOnRedo}
      />
    );

    const redoButton = screen.getByRole('button', { name: /redo/i });
    expect(redoButton).toBeDisabled();
  });

  it('should call onUndo when undo button clicked', () => {
    render(
      <UndoRedoControls
        canUndo={true}
        canRedo={true}
        onUndo={mockOnUndo}
        onRedo={mockOnRedo}
      />
    );

    const undoButton = screen.getByRole('button', { name: /undo/i });
    fireEvent.click(undoButton);

    expect(mockOnUndo).toHaveBeenCalledTimes(1);
    expect(mockOnRedo).not.toHaveBeenCalled();
  });

  it('should call onRedo when redo button clicked', () => {
    render(
      <UndoRedoControls
        canUndo={true}
        canRedo={true}
        onUndo={mockOnUndo}
        onRedo={mockOnRedo}
      />
    );

    const redoButton = screen.getByRole('button', { name: /redo/i });
    fireEvent.click(redoButton);

    expect(mockOnRedo).toHaveBeenCalledTimes(1);
    expect(mockOnUndo).not.toHaveBeenCalled();
  });

  it('should show loading state', () => {
    render(
      <UndoRedoControls
        canUndo={true}
        canRedo={true}
        onUndo={mockOnUndo}
        onRedo={mockOnRedo}
        loading={true}
      />
    );

    const undoButton = screen.getByRole('button', { name: /undo/i });
    const redoButton = screen.getByRole('button', { name: /redo/i });

    expect(undoButton).toBeDisabled();
    expect(redoButton).toBeDisabled();
  });

  it('should enable undo button when canUndo is true and not loading', () => {
    render(
      <UndoRedoControls
        canUndo={true}
        canRedo={false}
        onUndo={mockOnUndo}
        onRedo={mockOnRedo}
        loading={false}
      />
    );

    const undoButton = screen.getByRole('button', { name: /undo/i });
    expect(undoButton).not.toBeDisabled();
  });

  it('should enable redo button when canRedo is true and not loading', () => {
    render(
      <UndoRedoControls
        canUndo={false}
        canRedo={true}
        onUndo={mockOnUndo}
        onRedo={mockOnRedo}
        loading={false}
      />
    );

    const redoButton = screen.getByRole('button', { name: /redo/i });
    expect(redoButton).not.toBeDisabled();
  });

  it('should render undo icon', () => {
    const { container } = render(
      <UndoRedoControls
        canUndo={true}
        canRedo={true}
        onUndo={mockOnUndo}
        onRedo={mockOnRedo}
      />
    );

    // Check that SVG icons are present
    const svgs = container.querySelectorAll('svg');
    expect(svgs.length).toBeGreaterThanOrEqual(2); // At least undo and redo icons
  });

  it('should not call handlers when buttons are disabled', () => {
    render(
      <UndoRedoControls
        canUndo={false}
        canRedo={false}
        onUndo={mockOnUndo}
        onRedo={mockOnRedo}
      />
    );

    const undoButton = screen.getByRole('button', { name: /undo/i });
    const redoButton = screen.getByRole('button', { name: /redo/i });

    fireEvent.click(undoButton);
    fireEvent.click(redoButton);

    expect(mockOnUndo).not.toHaveBeenCalled();
    expect(mockOnRedo).not.toHaveBeenCalled();
  });
});
