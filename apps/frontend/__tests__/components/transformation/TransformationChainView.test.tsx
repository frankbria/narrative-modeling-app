import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  TransformationChainView,
  TransformationStep,
} from '@/components/transformation/TransformationChainView';

describe('TransformationChainView', () => {
  const mockTransformations: TransformationStep[] = [
    {
      id: '1',
      type: 'remove_duplicates',
      label: 'Remove Duplicates',
      parameters: { keep: 'first' },
    },
    {
      id: '2',
      type: 'fill_missing',
      label: 'Fill Missing Values',
      parameters: { method: 'mean', columns: ['age', 'salary'] },
    },
    {
      id: '3',
      type: 'scale',
      label: 'Scale Values',
      parameters: { method: 'minmax', columns: ['age'] },
    },
  ];

  const mockHandlers = {
    onReorder: jest.fn(),
    onEdit: jest.fn(),
    onDelete: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render empty state when no transformations provided', () => {
      render(
        <TransformationChainView
          transformations={[]}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      expect(
        screen.getByText(/No transformations added yet/i)
      ).toBeInTheDocument();
    });

    it('should render all transformation steps', () => {
      render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      mockTransformations.forEach((step) => {
        expect(screen.getByText(step.label)).toBeInTheDocument();
      });
    });

    it('should display step type and parameters', () => {
      render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      expect(screen.getByText(/Type: remove_duplicates/)).toBeInTheDocument();
    });

    it('should render visual connectors between steps', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const connectors = container.querySelectorAll('.h-4.bg-border');
      // Should have n-1 connectors for n steps
      expect(connectors.length).toBe(mockTransformations.length - 1);
    });

    it('should display step position info for accessibility', () => {
      render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      // Check for aria-posinset attributes
      const cards = screen.getAllByRole('listitem');
      expect(cards).toHaveLength(mockTransformations.length);
      cards.forEach((card, index) => {
        expect(card).toHaveAttribute('aria-posinset', (index + 1).toString());
      });
    });
  });

  describe('Expand/Collapse Functionality', () => {
    it('should collapse step details by default', () => {
      render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      // Parameters should not be visible initially
      expect(screen.queryByText('Parameters:')).not.toBeInTheDocument();
    });

    it('should expand step details when expand button clicked', () => {
      render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const expandButtons = screen.getAllByRole('button', {
        name: /expand step/i,
      });

      fireEvent.click(expandButtons[0]);

      expect(screen.getByText('Parameters:')).toBeInTheDocument();
      expect(screen.getByText(/keep:/i)).toBeInTheDocument();
    });

    it('should collapse step details when collapse button clicked', () => {
      render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const expandButtons = screen.getAllByRole('button', {
        name: /expand step/i,
      });

      fireEvent.click(expandButtons[0]);
      expect(screen.getByText('Parameters:')).toBeInTheDocument();

      const collapseButton = screen.getByRole('button', {
        name: /collapse step 1/i,
      });
      fireEvent.click(collapseButton);

      expect(screen.queryByText(/keep:/i)).not.toBeInTheDocument();
    });
  });

  describe('Button Actions', () => {
    it('should call onEdit when edit button clicked', () => {
      render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const editButtons = screen.getAllByRole('button', {
        name: /edit step/i,
      });

      fireEvent.click(editButtons[0]);

      expect(mockHandlers.onEdit).toHaveBeenCalledWith(0);
    });

    it('should call onDelete when delete button clicked', () => {
      render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const deleteButtons = screen.getAllByRole('button', {
        name: /delete step/i,
      });

      fireEvent.click(deleteButtons[0]);

      expect(mockHandlers.onDelete).toHaveBeenCalledWith(0);
    });

    it('should disable move up button for first step', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const moveUpButtons = container.querySelectorAll('button[aria-label*="Move step"][aria-label*="up"]');
      const firstMoveUpButton = moveUpButtons[0] as HTMLElement;

      expect(firstMoveUpButton).toBeDisabled();
    });

    it('should disable move down button for last step', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const moveDownButtons = container.querySelectorAll('button[aria-label*="Move step"][aria-label*="down"]');
      const lastMoveDownButton = moveDownButtons[moveDownButtons.length - 1] as HTMLElement;

      expect(lastMoveDownButton).toBeDisabled();
    });

    it('should call onReorder when move up button clicked', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      // Find move up buttons - the second one should be enabled (not first)
      const moveUpButtons = container.querySelectorAll('button[aria-label*="Move step"][aria-label*="up"]');
      const secondMoveUpButton = moveUpButtons[1] as HTMLElement;

      fireEvent.click(secondMoveUpButton);

      expect(mockHandlers.onReorder).toHaveBeenCalledWith(1, 0);
    });

    it('should call onReorder when move down button clicked', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      // Find move down buttons - first one should be enabled (not last)
      const moveDownButtons = container.querySelectorAll('button[aria-label*="Move step"][aria-label*="down"]');
      const firstMoveDownButton = moveDownButtons[0] as HTMLElement;

      fireEvent.click(firstMoveDownButton);

      expect(mockHandlers.onReorder).toHaveBeenCalledWith(0, 1);
    });
  });

  describe('Keyboard Navigation', () => {
    it('should handle Alt+ArrowUp to move step up', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const cards = container.querySelectorAll('[role="listitem"]');
      const secondCard = cards[1] as HTMLElement;

      fireEvent.keyDown(secondCard, {
        key: 'ArrowUp',
        altKey: true,
      });

      expect(mockHandlers.onReorder).toHaveBeenCalledWith(1, 0);
    });

    it('should handle Alt+ArrowDown to move step down', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const cards = container.querySelectorAll('[role="listitem"]');
      const firstCard = cards[0] as HTMLElement;

      fireEvent.keyDown(firstCard, {
        key: 'ArrowDown',
        altKey: true,
      });

      expect(mockHandlers.onReorder).toHaveBeenCalledWith(0, 1);
    });

    it('should handle Delete key to remove step', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const cards = container.querySelectorAll('[role="listitem"]');
      const firstCard = cards[0] as HTMLElement;

      fireEvent.keyDown(firstCard, {
        key: 'Delete',
      });

      expect(mockHandlers.onDelete).toHaveBeenCalledWith(0);
    });

    it('should handle Enter key to edit step', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const cards = container.querySelectorAll('[role="listitem"]');
      const firstCard = cards[0] as HTMLElement;

      fireEvent.keyDown(firstCard, {
        key: 'Enter',
      });

      expect(mockHandlers.onEdit).toHaveBeenCalledWith(0);
    });

    it('should not move up if already at first position', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const cards = container.querySelectorAll('[role="listitem"]');
      const firstCard = cards[0] as HTMLElement;

      fireEvent.keyDown(firstCard, {
        key: 'ArrowUp',
        altKey: true,
      });

      expect(mockHandlers.onReorder).not.toHaveBeenCalled();
    });

    it('should not move down if already at last position', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const cards = container.querySelectorAll('[role="listitem"]');
      const lastCard = cards[cards.length - 1] as HTMLElement;

      fireEvent.keyDown(lastCard, {
        key: 'ArrowDown',
        altKey: true,
      });

      expect(mockHandlers.onReorder).not.toHaveBeenCalled();
    });
  });

  describe('Drag and Drop', () => {
    it('should have proper drag visual feedback', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const cards = container.querySelectorAll('[role="listitem"]');
      const firstCard = cards[0] as HTMLElement;

      // Check for cursor-move class
      expect(firstCard).toHaveClass('cursor-move');
      expect(firstCard).toHaveAttribute('draggable', 'true');
    });

    it('should have drag handler attributes', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const cards = container.querySelectorAll('[role="listitem"]');
      cards.forEach((card) => {
        expect(card).toHaveAttribute('draggable', 'true');
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const list = screen.getByRole('list');
      expect(list).toHaveAttribute(
        'aria-label',
        'Transformation pipeline steps'
      );
    });

    it('should have aria-setsize on list items', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const cards = container.querySelectorAll('[role="listitem"]');
      cards.forEach((card) => {
        expect(card).toHaveAttribute(
          'aria-setsize',
          mockTransformations.length.toString()
        );
      });
    });

    it('should announce button actions with aria-keyshortcuts', () => {
      render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const editButtons = screen.getAllByRole('button', {
        name: /edit step/i,
      });

      expect(editButtons[0]).toHaveAttribute('aria-keyshortcuts', 'Enter');
    });

    it('should have screen reader status region', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const statusRegions = container.querySelectorAll('[role="status"]');
      expect(statusRegions.length).toBeGreaterThan(0);
    });

    it('should have proper focus styling', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const cards = container.querySelectorAll('[role="listitem"]');
      cards.forEach((card) => {
        expect(card).toHaveClass('focus:ring-2', 'focus:ring-blue-500');
      });
    });
  });

  describe('CSS Classes and Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
          className="custom-class"
        />
      );

      const mainDiv = container.firstChild;
      expect(mainDiv).toHaveClass('custom-class');
    });

    it('should render with proper touch-friendly button sizes', () => {
      render(
        <TransformationChainView
          transformations={mockTransformations}
          onReorder={mockHandlers.onReorder}
          onEdit={mockHandlers.onEdit}
          onDelete={mockHandlers.onDelete}
        />
      );

      const moveButtons = screen.getAllByRole('button', {
        name: /move/i,
      });

      moveButtons.forEach((button) => {
        expect(button).toHaveClass('h-8', 'w-8', 'p-0');
      });
    });
  });
});
