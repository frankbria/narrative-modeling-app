import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import OperationPalette from '@/components/feature-builder/OperationPalette';

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  ChevronDown: () => <span data-testid="chevron-down">ChevronDown</span>,
  ChevronRight: () => <span data-testid="chevron-right">ChevronRight</span>,
}));

describe('OperationPalette Component', () => {
  describe('Rendering', () => {
    it('should render Operations header', () => {
      render(<OperationPalette />);

      expect(screen.getByText('Operations')).toBeInTheDocument();
    });

    it('should render category headers', () => {
      render(<OperationPalette />);

      expect(screen.getByText('arithmetic')).toBeInTheDocument();
      expect(screen.getByText('comparison')).toBeInTheDocument();
      expect(screen.getByText('logical')).toBeInTheDocument();
    });

    it('should render arithmetic operations when expanded', () => {
      render(<OperationPalette />);

      // Arithmetic is expanded by default
      expect(screen.getByText('+')).toBeInTheDocument();
      expect(screen.getByText('-')).toBeInTheDocument();
      expect(screen.getByText('*')).toBeInTheDocument();
      expect(screen.getByText('/')).toBeInTheDocument();
      expect(screen.getByText('%')).toBeInTheDocument();
      expect(screen.getByText('^')).toBeInTheDocument();
    });

    it('should be expanded by default with arithmetic category open', () => {
      render(<OperationPalette />);

      // Main section expanded (there are multiple chevron-down icons)
      expect(screen.getAllByTestId('chevron-down').length).toBeGreaterThan(0);
      // Arithmetic operations visible
      expect(screen.getByText('+')).toBeInTheDocument();
    });
  });

  describe('Category Toggle', () => {
    it('should expand comparison category when clicked', () => {
      render(<OperationPalette />);

      // Comparison is collapsed by default
      expect(screen.queryByText('==')).not.toBeInTheDocument();

      // Click comparison header
      const comparisonHeader = screen.getByText('comparison').closest('button');
      fireEvent.click(comparisonHeader!);

      // Now comparison operations should be visible
      expect(screen.getByText('==')).toBeInTheDocument();
      expect(screen.getByText('!=')).toBeInTheDocument();
      expect(screen.getByText('>')).toBeInTheDocument();
      expect(screen.getByText('<')).toBeInTheDocument();
      expect(screen.getByText('>=')).toBeInTheDocument();
      expect(screen.getByText('<=')).toBeInTheDocument();
    });

    it('should expand logical category when clicked', () => {
      render(<OperationPalette />);

      // Logical is collapsed by default
      expect(screen.queryByText('AND')).not.toBeInTheDocument();

      // Click logical header
      const logicalHeader = screen.getByText('logical').closest('button');
      fireEvent.click(logicalHeader!);

      // Now logical operations should be visible
      expect(screen.getByText('AND')).toBeInTheDocument();
      expect(screen.getByText('OR')).toBeInTheDocument();
      expect(screen.getByText('NOT')).toBeInTheDocument();
    });

    it('should collapse arithmetic category when clicked', () => {
      render(<OperationPalette />);

      // Arithmetic is expanded by default
      expect(screen.getByText('+')).toBeInTheDocument();

      // Click arithmetic header
      const arithmeticHeader = screen.getByText('arithmetic').closest('button');
      fireEvent.click(arithmeticHeader!);

      // Arithmetic operations should be hidden
      expect(screen.queryByText('+')).not.toBeInTheDocument();
    });

    it('should toggle category expansion independently', () => {
      render(<OperationPalette />);

      // Expand comparison
      const comparisonHeader = screen.getByText('comparison').closest('button');
      fireEvent.click(comparisonHeader!);

      // Both arithmetic and comparison should be visible
      expect(screen.getByText('+')).toBeInTheDocument();
      expect(screen.getByText('==')).toBeInTheDocument();

      // Collapse arithmetic
      const arithmeticHeader = screen.getByText('arithmetic').closest('button');
      fireEvent.click(arithmeticHeader!);

      // Only comparison should be visible
      expect(screen.queryByText('+')).not.toBeInTheDocument();
      expect(screen.getByText('==')).toBeInTheDocument();
    });
  });

  describe('Main Section Toggle', () => {
    it('should collapse entire section when main header clicked', () => {
      render(<OperationPalette />);

      // Operations should be visible
      expect(screen.getByText('+')).toBeInTheDocument();

      // Click main header
      const mainHeader = screen.getByText('Operations').closest('button');
      fireEvent.click(mainHeader!);

      // Nothing should be visible
      expect(screen.queryByText('+')).not.toBeInTheDocument();
      expect(screen.queryByText('arithmetic')).not.toBeInTheDocument();
    });

    it('should expand entire section when main header clicked again', () => {
      render(<OperationPalette />);

      const mainHeader = screen.getByText('Operations').closest('button');
      fireEvent.click(mainHeader!); // collapse
      fireEvent.click(mainHeader!); // expand

      expect(screen.getByText('arithmetic')).toBeInTheDocument();
      expect(screen.getByText('+')).toBeInTheDocument();
    });
  });

  describe('Drag and Drop', () => {
    it('should set operations as draggable', () => {
      render(<OperationPalette />);

      const addOperation = screen.getByText('+').closest('div[draggable]');
      expect(addOperation).toHaveAttribute('draggable', 'true');
    });

    it('should set correct data on drag start for add operation', () => {
      render(<OperationPalette />);

      const addOperation = screen.getByText('+').closest('div[draggable]');

      const mockDataTransfer = {
        setData: jest.fn(),
        effectAllowed: '',
      };

      fireEvent.dragStart(addOperation!, {
        dataTransfer: mockDataTransfer,
      });

      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeType', 'operation');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeValue', 'add');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeLabel', '+');
    });

    it('should set correct data on drag start for comparison operation', () => {
      render(<OperationPalette />);

      // Expand comparison category
      const comparisonHeader = screen.getByText('comparison').closest('button');
      fireEvent.click(comparisonHeader!);

      const greaterThanOperation = screen.getByText('>').closest('div[draggable]');

      const mockDataTransfer = {
        setData: jest.fn(),
        effectAllowed: '',
      };

      fireEvent.dragStart(greaterThanOperation!, {
        dataTransfer: mockDataTransfer,
      });

      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeType', 'operation');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeValue', 'greater_than');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeLabel', '>');
    });

    it('should set correct data on drag start for logical operation', () => {
      render(<OperationPalette />);

      // Expand logical category
      const logicalHeader = screen.getByText('logical').closest('button');
      fireEvent.click(logicalHeader!);

      const andOperation = screen.getByText('AND').closest('div[draggable]');

      const mockDataTransfer = {
        setData: jest.fn(),
        effectAllowed: '',
      };

      fireEvent.dragStart(andOperation!, {
        dataTransfer: mockDataTransfer,
      });

      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeType', 'operation');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeValue', 'and');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeLabel', 'AND');
    });
  });

  describe('Tooltips', () => {
    it('should have tooltip with description for operations', () => {
      render(<OperationPalette />);

      const addOperation = screen.getByText('+').closest('div[draggable]');
      expect(addOperation).toHaveAttribute('title', 'Add two values');
    });

    it('should have tooltip for subtract operation', () => {
      render(<OperationPalette />);

      const subtractOperation = screen.getByText('-').closest('div[draggable]');
      expect(subtractOperation).toHaveAttribute('title', 'Subtract values');
    });
  });

  describe('Styling', () => {
    it('should have green styling for operations', () => {
      render(<OperationPalette />);

      const addOperation = screen.getByText('+').closest('div[draggable]');
      expect(addOperation).toHaveClass('bg-green-100');
      expect(addOperation).toHaveClass('border-green-200');
    });

    it('should have grid layout for operations', () => {
      render(<OperationPalette />);

      // Find the grid container for arithmetic operations
      const addOperation = screen.getByText('+').closest('div[draggable]');
      const gridContainer = addOperation?.parentElement;
      expect(gridContainer).toHaveClass('grid');
      expect(gridContainer).toHaveClass('grid-cols-3');
    });
  });
});
