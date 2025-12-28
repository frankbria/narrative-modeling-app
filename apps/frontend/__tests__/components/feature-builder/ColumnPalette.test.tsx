import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ColumnPalette from '@/components/feature-builder/ColumnPalette';

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  ChevronDown: () => <span data-testid="chevron-down">ChevronDown</span>,
  ChevronRight: () => <span data-testid="chevron-right">ChevronRight</span>,
  Search: () => <span data-testid="search-icon">Search</span>,
}));

describe('ColumnPalette Component', () => {
  const mockColumns = [
    { name: 'price', type: 'numeric', nullCount: 0, uniqueCount: 100 },
    { name: 'quantity', type: 'numeric', nullCount: 5, uniqueCount: 50 },
    { name: 'product_name', type: 'text', nullCount: 0, uniqueCount: 200 },
    { name: 'is_active', type: 'boolean', nullCount: 2, uniqueCount: 2 },
    { name: 'created_at', type: 'datetime', nullCount: 0, uniqueCount: 100 },
    { name: 'category', type: 'categorical', nullCount: 0, uniqueCount: 10 },
  ];

  describe('Rendering', () => {
    it('should render columns header with count', () => {
      render(<ColumnPalette columns={mockColumns} />);

      expect(screen.getByText('Columns (6)')).toBeInTheDocument();
    });

    it('should render all columns when expanded', () => {
      render(<ColumnPalette columns={mockColumns} />);

      expect(screen.getByText('price')).toBeInTheDocument();
      expect(screen.getByText('quantity')).toBeInTheDocument();
      expect(screen.getByText('product_name')).toBeInTheDocument();
      expect(screen.getByText('is_active')).toBeInTheDocument();
      expect(screen.getByText('created_at')).toBeInTheDocument();
      expect(screen.getByText('category')).toBeInTheDocument();
    });

    it('should group columns by type', () => {
      render(<ColumnPalette columns={mockColumns} />);

      // Check for type headers (uppercased)
      expect(screen.getByText(/numeric \(2\)/i)).toBeInTheDocument();
      expect(screen.getByText(/text \(1\)/i)).toBeInTheDocument();
      expect(screen.getByText(/boolean \(1\)/i)).toBeInTheDocument();
      expect(screen.getByText(/datetime \(1\)/i)).toBeInTheDocument();
      expect(screen.getByText(/categorical \(1\)/i)).toBeInTheDocument();
    });

    it('should display column types', () => {
      render(<ColumnPalette columns={mockColumns} />);

      // Each column shows its type
      expect(screen.getAllByText('numeric').length).toBe(2);
      expect(screen.getByText('text')).toBeInTheDocument();
      expect(screen.getByText('boolean')).toBeInTheDocument();
    });

    it('should display null count when present', () => {
      render(<ColumnPalette columns={mockColumns} />);

      expect(screen.getByText('(5 nulls)')).toBeInTheDocument();
      expect(screen.getByText('(2 nulls)')).toBeInTheDocument();
    });
  });

  describe('Collapse/Expand', () => {
    it('should be expanded by default', () => {
      render(<ColumnPalette columns={mockColumns} />);

      expect(screen.getByText('price')).toBeInTheDocument();
      expect(screen.getByTestId('chevron-down')).toBeInTheDocument();
    });

    it('should collapse when header clicked', () => {
      render(<ColumnPalette columns={mockColumns} />);

      const header = screen.getByText('Columns (6)').closest('button');
      fireEvent.click(header!);

      expect(screen.queryByText('price')).not.toBeInTheDocument();
      expect(screen.getByTestId('chevron-right')).toBeInTheDocument();
    });

    it('should expand again when header clicked twice', () => {
      render(<ColumnPalette columns={mockColumns} />);

      const header = screen.getByText('Columns (6)').closest('button');
      fireEvent.click(header!); // collapse
      fireEvent.click(header!); // expand

      expect(screen.getByText('price')).toBeInTheDocument();
    });
  });

  describe('Search Functionality', () => {
    it('should render search input', () => {
      render(<ColumnPalette columns={mockColumns} />);

      expect(screen.getByPlaceholderText('Search columns...')).toBeInTheDocument();
    });

    it('should filter columns when searching', () => {
      render(<ColumnPalette columns={mockColumns} />);

      const searchInput = screen.getByPlaceholderText('Search columns...');
      fireEvent.change(searchInput, { target: { value: 'price' } });

      expect(screen.getByText('price')).toBeInTheDocument();
      expect(screen.queryByText('quantity')).not.toBeInTheDocument();
      expect(screen.queryByText('product_name')).not.toBeInTheDocument();
    });

    it('should be case-insensitive when searching', () => {
      render(<ColumnPalette columns={mockColumns} />);

      const searchInput = screen.getByPlaceholderText('Search columns...');
      fireEvent.change(searchInput, { target: { value: 'PRICE' } });

      expect(screen.getByText('price')).toBeInTheDocument();
    });

    it('should show no results message when search has no matches', () => {
      render(<ColumnPalette columns={mockColumns} />);

      const searchInput = screen.getByPlaceholderText('Search columns...');
      fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

      expect(screen.getByText('No columns match your search')).toBeInTheDocument();
    });

    it('should show all columns when search is cleared', () => {
      render(<ColumnPalette columns={mockColumns} />);

      const searchInput = screen.getByPlaceholderText('Search columns...');
      fireEvent.change(searchInput, { target: { value: 'price' } });
      fireEvent.change(searchInput, { target: { value: '' } });

      expect(screen.getByText('price')).toBeInTheDocument();
      expect(screen.getByText('quantity')).toBeInTheDocument();
    });
  });

  describe('Drag and Drop', () => {
    it('should set column as draggable', () => {
      render(<ColumnPalette columns={mockColumns} />);

      const priceColumn = screen.getByText('price').closest('div[draggable]');
      expect(priceColumn).toHaveAttribute('draggable', 'true');
    });

    it('should set correct data on drag start', () => {
      render(<ColumnPalette columns={mockColumns} />);

      const priceColumn = screen.getByText('price').closest('div[draggable]');

      const mockDataTransfer = {
        setData: jest.fn(),
        effectAllowed: '',
      };

      fireEvent.dragStart(priceColumn!, {
        dataTransfer: mockDataTransfer,
      });

      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeType', 'column');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeValue', 'price');
      expect(mockDataTransfer.setData).toHaveBeenCalledWith('nodeLabel', 'price');
    });
  });

  describe('Type-based Styling', () => {
    it('should apply blue styling for numeric columns', () => {
      render(<ColumnPalette columns={[{ name: 'price', type: 'numeric' }]} />);

      const column = screen.getByText('price').closest('div[draggable]');
      expect(column).toHaveClass('bg-blue-100');
    });

    it('should apply green styling for text columns', () => {
      render(<ColumnPalette columns={[{ name: 'name', type: 'text' }]} />);

      const column = screen.getByText('name').closest('div[draggable]');
      expect(column).toHaveClass('bg-green-100');
    });

    it('should apply purple styling for boolean columns', () => {
      render(<ColumnPalette columns={[{ name: 'active', type: 'boolean' }]} />);

      const column = screen.getByText('active').closest('div[draggable]');
      expect(column).toHaveClass('bg-purple-100');
    });

    it('should apply orange styling for datetime columns', () => {
      render(<ColumnPalette columns={[{ name: 'date', type: 'datetime' }]} />);

      const column = screen.getByText('date').closest('div[draggable]');
      expect(column).toHaveClass('bg-orange-100');
    });

    it('should apply pink styling for categorical columns', () => {
      render(<ColumnPalette columns={[{ name: 'cat', type: 'categorical' }]} />);

      const column = screen.getByText('cat').closest('div[draggable]');
      expect(column).toHaveClass('bg-pink-100');
    });

    it('should apply default gray styling for unknown types', () => {
      render(<ColumnPalette columns={[{ name: 'unknown', type: 'custom' }]} />);

      const column = screen.getByText('unknown').closest('div[draggable]');
      expect(column).toHaveClass('bg-gray-100');
    });
  });

  describe('Empty State', () => {
    it('should render header with zero count when empty', () => {
      render(<ColumnPalette columns={[]} />);

      expect(screen.getByText('Columns (0)')).toBeInTheDocument();
    });

    it('should not display any column items when empty', () => {
      render(<ColumnPalette columns={[]} />);

      // Search should still be visible when expanded
      expect(screen.getByPlaceholderText('Search columns...')).toBeInTheDocument();
    });
  });
});
