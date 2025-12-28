import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import FeatureList from '@/components/feature-builder/FeatureList';

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  Pencil: () => <span data-testid="pencil-icon">Pencil</span>,
  Trash2: () => <span data-testid="trash-icon">Trash</span>,
  Copy: () => <span data-testid="copy-icon">Copy</span>,
  Check: () => <span data-testid="check-icon">Check</span>,
  AlertCircle: () => <span data-testid="alert-icon">AlertCircle</span>,
  Plus: () => <span data-testid="plus-icon">Plus</span>,
  Search: () => <span data-testid="search-icon">Search</span>,
  Tag: () => <span data-testid="tag-icon">Tag</span>,
}));

// Mock constants
jest.mock('@/lib/constants', () => ({
  API_URL: 'http://localhost:8000/api/v1',
}));

// Mock auth helpers (already done in jest.setup.js but making explicit here)
jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('mock-token'),
}));

describe('FeatureList Component', () => {
  const mockFeatures = [
    {
      id: '1',
      feature_id: 'feat-1',
      name: 'price_per_unit',
      description: 'Price divided by quantity',
      formula_string: 'price / quantity',
      tags: ['pricing', 'calculated'],
      is_valid: true,
      created_at: '2024-01-15T10:00:00Z',
      updated_at: '2024-01-15T10:00:00Z',
    },
    {
      id: '2',
      feature_id: 'feat-2',
      name: 'total_value',
      description: 'Total monetary value',
      formula_string: 'price * quantity',
      tags: ['financial'],
      is_valid: true,
      created_at: '2024-01-16T10:00:00Z',
      updated_at: '2024-01-16T10:00:00Z',
    },
    {
      id: '3',
      feature_id: 'feat-3',
      name: 'profit_margin',
      description: null,
      formula_string: '(price - cost) / price',
      tags: [],
      is_valid: false,
      created_at: '2024-01-17T10:00:00Z',
      updated_at: '2024-01-17T10:00:00Z',
    },
  ];

  const mockProps = {
    datasetId: 'test-dataset-id',
    onEdit: jest.fn(),
    onCreate: jest.fn(),
    onApply: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
    global.confirm = jest.fn(() => true);
    global.alert = jest.fn();
  });

  describe('Loading State', () => {
    it('should show loading message initially', () => {
      (global.fetch as jest.Mock).mockImplementation(() => new Promise(() => {})); // Never resolves

      render(<FeatureList {...mockProps} />);

      expect(screen.getByText('Loading features...')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should show error message when fetch fails', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load features')).toBeInTheDocument();
      });
    });

    it('should show retry button on error', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('Retry')).toBeInTheDocument();
      });
    });

    it('should retry loading when Retry button clicked', async () => {
      (global.fetch as jest.Mock)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ features: mockFeatures }),
        });

      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('Retry')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Retry'));

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no features', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ features: [] }),
      });

      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('No features yet')).toBeInTheDocument();
        expect(screen.getByText('Create your first feature using the builder')).toBeInTheDocument();
      });
    });
  });

  describe('Feature List Display', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ features: mockFeatures }),
      });
    });

    it('should display all features', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
        expect(screen.getByText('total_value')).toBeInTheDocument();
        expect(screen.getByText('profit_margin')).toBeInTheDocument();
      });
    });

    it('should display feature count in header', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('Saved Features (3)')).toBeInTheDocument();
      });
    });

    it('should display feature descriptions', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('Price divided by quantity')).toBeInTheDocument();
        expect(screen.getByText('Total monetary value')).toBeInTheDocument();
      });
    });

    it('should display formula strings', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price / quantity')).toBeInTheDocument();
        expect(screen.getByText('price * quantity')).toBeInTheDocument();
      });
    });

    it('should display feature tags', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        // Tags appear in both filter buttons and feature cards, so use getAllByText
        expect(screen.getAllByText('pricing').length).toBeGreaterThan(0);
        expect(screen.getAllByText('calculated').length).toBeGreaterThan(0);
        expect(screen.getAllByText('financial').length).toBeGreaterThan(0);
      });
    });

    it('should show valid icon for valid features', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        const checkIcons = screen.getAllByTestId('check-icon');
        expect(checkIcons.length).toBe(2); // price_per_unit and total_value are valid
      });
    });

    it('should show warning icon for invalid features', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        // profit_margin is invalid
        const alertIcons = screen.getAllByTestId('alert-icon');
        expect(alertIcons.length).toBe(1);
      });
    });
  });

  describe('Search Functionality', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ features: mockFeatures }),
      });
    });

    it('should filter features by name', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search features...');
      fireEvent.change(searchInput, { target: { value: 'price' } });

      expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      expect(screen.queryByText('profit_margin')).not.toBeInTheDocument();
    });

    it('should filter features by description', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search features...');
      fireEvent.change(searchInput, { target: { value: 'monetary' } });

      expect(screen.getByText('total_value')).toBeInTheDocument();
      expect(screen.queryByText('price_per_unit')).not.toBeInTheDocument();
    });

    it('should show no results message when search has no matches', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search features...');
      fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

      expect(screen.getByText('No features match your search')).toBeInTheDocument();
    });
  });

  describe('Tag Filtering', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ features: mockFeatures }),
      });
    });

    it('should display tag filter buttons', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        // Tag filter buttons should exist
        const tagButtons = screen.getAllByRole('button');
        expect(tagButtons.length).toBeGreaterThan(0);
      });
    });

    it('should filter features by tag when clicked', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });

      // Find and click the 'pricing' tag filter
      const tagFilters = screen.getAllByText('pricing');
      const filterButton = tagFilters.find(el => el.closest('button'));
      if (filterButton) {
        fireEvent.click(filterButton.closest('button')!);
      }

      expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      expect(screen.queryByText('total_value')).not.toBeInTheDocument();
    });
  });

  describe('Feature Actions', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ features: mockFeatures }),
      });
    });

    it('should call onEdit when Edit button clicked', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });

      const editButtons = screen.getAllByTestId('pencil-icon');
      fireEvent.click(editButtons[0].closest('button')!);

      expect(mockProps.onEdit).toHaveBeenCalledWith(mockFeatures[0]);
    });

    it('should call onCreate when New Feature button clicked', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('New Feature')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('New Feature'));

      expect(mockProps.onCreate).toHaveBeenCalled();
    });

    it('should call onApply when Apply button clicked', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });

      const applyButtons = screen.getAllByText('Apply');
      fireEvent.click(applyButtons[0]);

      expect(mockProps.onApply).toHaveBeenCalledWith('feat-1');
    });

    it('should not show Apply button when onApply is not provided', async () => {
      render(<FeatureList {...mockProps} onApply={undefined} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });

      expect(screen.queryByText('Apply')).not.toBeInTheDocument();
    });
  });

  describe('Delete Feature', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ features: mockFeatures }),
      });
    });

    it('should confirm before deleting', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByTestId('trash-icon');
      fireEvent.click(deleteButtons[0].closest('button')!);

      expect(global.confirm).toHaveBeenCalledWith('Are you sure you want to delete this feature?');
    });

    it('should not delete if user cancels confirmation', async () => {
      (global.confirm as jest.Mock).mockReturnValue(false);

      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByTestId('trash-icon');
      fireEvent.click(deleteButtons[0].closest('button')!);

      // Should still be in the list
      expect(screen.getByText('price_per_unit')).toBeInTheDocument();
    });

    it('should remove feature from list on successful delete', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ features: mockFeatures }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({}),
        });

      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByTestId('trash-icon');
      fireEvent.click(deleteButtons[0].closest('button')!);

      await waitFor(() => {
        expect(screen.queryByText('price_per_unit')).not.toBeInTheDocument();
      });
    });
  });

  describe('Duplicate Feature', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ features: mockFeatures }),
        });
    });

    it('should fetch full feature details before duplicating', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockFeatures[0]),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ ...mockFeatures[0], name: 'price_per_unit_copy' }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ features: [...mockFeatures, { ...mockFeatures[0], name: 'price_per_unit_copy' }] }),
        });

      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('price_per_unit')).toBeInTheDocument();
      });

      const copyButtons = screen.getAllByTestId('copy-icon');
      fireEvent.click(copyButtons[0].closest('button')!);

      await waitFor(() => {
        // Verify fetch was called for getting feature details
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/features/feat-1'),
          expect.any(Object)
        );
      });
    });
  });

  describe('Date Formatting', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ features: mockFeatures }),
      });
    });

    it('should display formatted creation dates', async () => {
      render(<FeatureList {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText(/Jan 15, 2024/)).toBeInTheDocument();
        expect(screen.getByText(/Jan 16, 2024/)).toBeInTheDocument();
      });
    });
  });
});
