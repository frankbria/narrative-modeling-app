import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import FunctionPalette from '@/components/feature-builder/FunctionPalette';

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  ChevronDown: () => <span data-testid="chevron-down">ChevronDown</span>,
  ChevronRight: () => <span data-testid="chevron-right">ChevronRight</span>,
}));

describe('FunctionPalette Component', () => {
  describe('Rendering', () => {
    it('should render Functions header', () => {
      render(<FunctionPalette />);

      expect(screen.getByText('Functions')).toBeInTheDocument();
    });

    it('should render all category headers', () => {
      render(<FunctionPalette />);

      expect(screen.getByText('mathematical')).toBeInTheDocument();
      expect(screen.getByText('statistical')).toBeInTheDocument();
      expect(screen.getByText('string')).toBeInTheDocument();
      expect(screen.getByText('date')).toBeInTheDocument();
      expect(screen.getByText('utility')).toBeInTheDocument();
    });

    it('should render mathematical functions when expanded (default)', () => {
      render(<FunctionPalette />);

      // Mathematical is expanded by default
      expect(screen.getByText('abs')).toBeInTheDocument();
      expect(screen.getByText('log')).toBeInTheDocument();
      expect(screen.getByText('log10')).toBeInTheDocument();
      expect(screen.getByText('sqrt')).toBeInTheDocument();
      expect(screen.getByText('exp')).toBeInTheDocument();
      expect(screen.getByText('round')).toBeInTheDocument();
      expect(screen.getByText('ceil')).toBeInTheDocument();
      expect(screen.getByText('floor')).toBeInTheDocument();
    });

    it('should be expanded by default with mathematical category open', () => {
      render(<FunctionPalette />);

      // Main section expanded (there are multiple chevron-down icons)
      expect(screen.getAllByTestId('chevron-down').length).toBeGreaterThan(0);
      // Mathematical functions visible
      expect(screen.getByText('sqrt')).toBeInTheDocument();
    });
  });

  describe('Category Toggle', () => {
    it('should expand statistical category when clicked', () => {
      render(<FunctionPalette />);

      // Statistical is collapsed by default
      expect(screen.queryByText('mean')).not.toBeInTheDocument();

      // Click statistical header
      const statisticalHeader = screen.getByText('statistical').closest('button');
      fireEvent.click(statisticalHeader!);

      // Now statistical functions should be visible
      expect(screen.getByText('mean')).toBeInTheDocument();
      expect(screen.getByText('median')).toBeInTheDocument();
      expect(screen.getByText('std')).toBeInTheDocument();
      expect(screen.getByText('min')).toBeInTheDocument();
      expect(screen.getByText('max')).toBeInTheDocument();
      expect(screen.getByText('sum')).toBeInTheDocument();
    });

    it('should expand string category when clicked', () => {
      render(<FunctionPalette />);

      // String is collapsed by default
      expect(screen.queryByText('upper')).not.toBeInTheDocument();

      // Click string header
      const stringHeader = screen.getByText('string').closest('button');
      fireEvent.click(stringHeader!);

      // Now string functions should be visible
      expect(screen.getByText('upper')).toBeInTheDocument();
      expect(screen.getByText('lower')).toBeInTheDocument();
      expect(screen.getByText('trim')).toBeInTheDocument();
      expect(screen.getByText('length')).toBeInTheDocument();
    });

    it('should expand date category when clicked', () => {
      render(<FunctionPalette />);

      // Date is collapsed by default
      expect(screen.queryByText('year')).not.toBeInTheDocument();

      // Click date header
      const dateHeader = screen.getByText('date').closest('button');
      fireEvent.click(dateHeader!);

      // Now date functions should be visible
      expect(screen.getByText('year')).toBeInTheDocument();
      expect(screen.getByText('month')).toBeInTheDocument();
      expect(screen.getByText('day')).toBeInTheDocument();
      expect(screen.getByText('hour')).toBeInTheDocument();
      expect(screen.getByText('weekday')).toBeInTheDocument();
    });

    it('should expand utility category when clicked', () => {
      render(<FunctionPalette />);

      // Utility is collapsed by default
      expect(screen.queryByText('toNum')).not.toBeInTheDocument();

      // Click utility header
      const utilityHeader = screen.getByText('utility').closest('button');
      fireEvent.click(utilityHeader!);

      // Now utility functions should be visible
      expect(screen.getByText('toNum')).toBeInTheDocument();
      expect(screen.getByText('toStr')).toBeInTheDocument();
      expect(screen.getByText('fillNull')).toBeInTheDocument();
      expect(screen.getByText('isNull')).toBeInTheDocument();
    });

    it('should collapse mathematical category when clicked', () => {
      render(<FunctionPalette />);

      // Mathematical is expanded by default
      expect(screen.getByText('sqrt')).toBeInTheDocument();

      // Click mathematical header
      const mathematicalHeader = screen.getByText('mathematical').closest('button');
      fireEvent.click(mathematicalHeader!);

      // Mathematical functions should be hidden
      expect(screen.queryByText('sqrt')).not.toBeInTheDocument();
    });

    it('should toggle category expansion independently', () => {
      render(<FunctionPalette />);

      // Expand statistical
      const statisticalHeader = screen.getByText('statistical').closest('button');
      fireEvent.click(statisticalHeader!);

      // Both mathematical and statistical should be visible
      expect(screen.getByText('sqrt')).toBeInTheDocument();
      expect(screen.getByText('mean')).toBeInTheDocument();

      // Collapse mathematical
      const mathematicalHeader = screen.getByText('mathematical').closest('button');
      fireEvent.click(mathematicalHeader!);

      // Only statistical should be visible
      expect(screen.queryByText('sqrt')).not.toBeInTheDocument();
      expect(screen.getByText('mean')).toBeInTheDocument();
    });
  });

  describe('Main Section Toggle', () => {
    it('should collapse entire section when main header clicked', () => {
      render(<FunctionPalette />);

      // Functions should be visible
      expect(screen.getByText('sqrt')).toBeInTheDocument();

      // Click main header
      const mainHeader = screen.getByText('Functions').closest('button');
      fireEvent.click(mainHeader!);

      // Nothing should be visible
      expect(screen.queryByText('sqrt')).not.toBeInTheDocument();
      expect(screen.queryByText('mathematical')).not.toBeInTheDocument();
    });

    it('should expand entire section when main header clicked again', () => {
      render(<FunctionPalette />);

      const mainHeader = screen.getByText('Functions').closest('button');
      fireEvent.click(mainHeader!); // collapse
      fireEvent.click(mainHeader!); // expand

      expect(screen.getByText('mathematical')).toBeInTheDocument();
      expect(screen.getByText('sqrt')).toBeInTheDocument();
    });
  });

  describe('Drag and Drop', () => {
    it('should set functions as draggable', () => {
      render(<FunctionPalette />);

      const sqrtFunction = screen.getByText('sqrt').closest('div[draggable]');
      expect(sqrtFunction).toHaveAttribute('draggable', 'true');
    });

    it('should set correct data on drag start for mathematical function', () => {
      render(<FunctionPalette />);

      const sqrtFunction = screen.getByText('sqrt').closest('div[draggable]');

      const mockDataTransfer = {
        setData: jest.fn(),
        effectAllowed: '',
      };

      fireEvent.dragStart(sqrtFunction!, {
        dataTransfer: mockDataTransfer,
      });

      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeType', 'function');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeValue', 'sqrt');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeLabel', 'sqrt');
    });

    it('should set correct data on drag start for statistical function', () => {
      render(<FunctionPalette />);

      // Expand statistical category
      const statisticalHeader = screen.getByText('statistical').closest('button');
      fireEvent.click(statisticalHeader!);

      const meanFunction = screen.getByText('mean').closest('div[draggable]');

      const mockDataTransfer = {
        setData: jest.fn(),
        effectAllowed: '',
      };

      fireEvent.dragStart(meanFunction!, {
        dataTransfer: mockDataTransfer,
      });

      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeType', 'function');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeValue', 'mean');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeLabel', 'mean');
    });

    it('should set correct data on drag start for utility function', () => {
      render(<FunctionPalette />);

      // Expand utility category
      const utilityHeader = screen.getByText('utility').closest('button');
      fireEvent.click(utilityHeader!);

      const fillNullFunction = screen.getByText('fillNull').closest('div[draggable]');

      const mockDataTransfer = {
        setData: jest.fn(),
        effectAllowed: '',
      };

      fireEvent.dragStart(fillNullFunction!, {
        dataTransfer: mockDataTransfer,
      });

      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeType', 'function');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeValue', 'fill_null');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeLabel', 'fillNull');
    });
  });

  describe('Tooltips', () => {
    it('should have tooltip with description for functions', () => {
      render(<FunctionPalette />);

      const sqrtFunction = screen.getByText('sqrt').closest('div[draggable]');
      expect(sqrtFunction).toHaveAttribute('title', 'Square root');
    });

    it('should have tooltip for round function', () => {
      render(<FunctionPalette />);

      const roundFunction = screen.getByText('round').closest('div[draggable]');
      expect(roundFunction).toHaveAttribute('title', 'Round to decimals');
    });

    it('should have tooltip for log function', () => {
      render(<FunctionPalette />);

      const logFunction = screen.getByText('log').closest('div[draggable]');
      expect(logFunction).toHaveAttribute('title', 'Natural logarithm');
    });
  });

  describe('Styling', () => {
    it('should have orange styling for functions', () => {
      render(<FunctionPalette />);

      const sqrtFunction = screen.getByText('sqrt').closest('div[draggable]');
      expect(sqrtFunction).toHaveClass('bg-orange-100');
      expect(sqrtFunction).toHaveClass('border-orange-200');
    });

    it('should have grid layout for functions', () => {
      render(<FunctionPalette />);

      // Find the grid container for mathematical functions
      const sqrtFunction = screen.getByText('sqrt').closest('div[draggable]');
      const gridContainer = sqrtFunction?.parentElement;
      expect(gridContainer).toHaveClass('grid');
      expect(gridContainer).toHaveClass('grid-cols-2');
    });

    it('should have monospace font for function labels', () => {
      render(<FunctionPalette />);

      const sqrtLabel = screen.getByText('sqrt');
      expect(sqrtLabel).toHaveClass('font-mono');
    });
  });
});
