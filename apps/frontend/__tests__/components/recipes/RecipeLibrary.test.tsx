import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RecipeLibrary } from '@/components/recipes/RecipeLibrary';
import { Recipe, TransformationService } from '@/lib/services/transformation';
import { useSession } from 'next-auth/react';
import { getAuthToken } from '@/lib/auth-helpers';

// Mock dependencies
jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));
jest.mock('@/lib/auth-helpers');
jest.mock('@/lib/services/transformation');

// Mock RecipeCard component
jest.mock('@/components/recipes/RecipeCard', () => ({
  RecipeCard: ({ recipe, onApply, onDuplicate, onDelete }: any) => (
    <div data-testid={`recipe-card-${recipe.id}`}>
      <h3>{recipe.name}</h3>
      <button onClick={() => onApply?.(recipe)}>Apply</button>
      <button onClick={() => onDuplicate?.(recipe)}>Duplicate</button>
      <button onClick={() => onDelete?.(recipe)}>Delete</button>
    </div>
  ),
}));

describe('RecipeLibrary', () => {
  const mockRecipes: Recipe[] = [
    {
      id: 'recipe-1',
      name: 'Data Cleaning Recipe',
      description: 'Clean and preprocess data',
      user_id: 'user-1',
      steps: [{ step_id: 'step-1', type: 'remove_duplicates', parameters: {}, description: 'Remove duplicates', order: 0 }],
      tags: ['cleaning', 'preprocessing'],
      version: 1,
      created_at: '2024-01-15T10:00:00Z',
      updated_at: '2024-01-15T10:00:00Z',
      is_public: true,
      usage_count: 10,
      rating: 4.5,
    },
    {
      id: 'recipe-2',
      name: 'Feature Engineering',
      description: 'Create new features',
      user_id: 'user-1',
      steps: [{ step_id: 'step-1', type: 'encode', parameters: {}, description: 'Encode', order: 0 }],
      tags: ['feature-engineering'],
      version: 1,
      created_at: '2024-01-14T10:00:00Z',
      updated_at: '2024-01-14T10:00:00Z',
      is_public: false,
      usage_count: 5,
      rating: 4.0,
    },
    {
      id: 'recipe-3',
      name: 'Anomaly Detection Prep',
      description: 'Prepare data for anomaly detection',
      user_id: 'user-1',
      steps: [{ step_id: 'step-1', type: 'scale', parameters: {}, description: 'Scale', order: 0 }],
      tags: ['preprocessing', 'scaling'],
      version: 1,
      created_at: '2024-01-13T10:00:00Z',
      updated_at: '2024-01-13T10:00:00Z',
      is_public: true,
      usage_count: 15,
      rating: 4.8,
    },
  ];

  const mockSession = {
    user: { id: 'user-1', email: 'test@example.com' },
    expires: '2024-12-31',
  };

  const mockHandlers = {
    onApplyRecipe: jest.fn(),
    onCreateNew: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (useSession as jest.Mock).mockReturnValue({ data: mockSession, status: 'authenticated' });
    (getAuthToken as jest.Mock).mockResolvedValue('mock-token');
    (TransformationService.listRecipes as jest.Mock).mockResolvedValue({
      recipes: mockRecipes,
      total: 3,
      page: 1,
      per_page: 12,
    });
    (TransformationService.duplicateRecipe as jest.Mock).mockResolvedValue({
      id: 'recipe-4',
      name: 'Data Cleaning Recipe (Copy)',
    });
    (TransformationService.deleteRecipe as jest.Mock).mockResolvedValue({ success: true });
  });

  describe('Rendering', () => {
    it('should render recipe library with title and description', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      expect(screen.getByText('Recipe Library')).toBeInTheDocument();
      expect(screen.getByText('Browse and apply transformation recipes')).toBeInTheDocument();
    });

    it('should show loading state initially', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      // Wait for the useEffect to trigger and call listRecipes
      await waitFor(() => {
        expect(TransformationService.listRecipes).toHaveBeenCalled();
      });
    });

    it('should load and display recipes', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      expect(screen.getByText('Feature Engineering')).toBeInTheDocument();
      expect(screen.getByText('Anomaly Detection Prep')).toBeInTheDocument();
    });

    it('gives the icon-only view-mode toggles accessible names (issue #282)', () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);
      const grid = screen.getByRole('button', { name: 'Grid view' });
      const list = screen.getByRole('button', { name: 'List view' });
      // Default view is grid.
      expect(grid).toHaveAttribute('aria-pressed', 'true');
      expect(list).toHaveAttribute('aria-pressed', 'false');
    });

    it('should display create button when showCreateButton is true', () => {
      render(
        <RecipeLibrary
          onApplyRecipe={mockHandlers.onApplyRecipe}
          onCreateNew={mockHandlers.onCreateNew}
          showCreateButton={true}
        />
      );

      expect(screen.getByRole('button', { name: /create new recipe/i })).toBeInTheDocument();
    });

    it('should not display create button when showCreateButton is false', () => {
      render(
        <RecipeLibrary
          onApplyRecipe={mockHandlers.onApplyRecipe}
          showCreateButton={false}
        />
      );

      expect(screen.queryByRole('button', { name: /create new recipe/i })).not.toBeInTheDocument();
    });
  });

  describe('Search Functionality', () => {
    it('should filter recipes by name', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search recipes...');

      fireEvent.change(searchInput, { target: { value: 'Feature' } });

      await waitFor(() => {
        expect(screen.queryByText('Data Cleaning Recipe')).not.toBeInTheDocument();
        expect(screen.getByText('Feature Engineering')).toBeInTheDocument();
        expect(screen.queryByText('Anomaly Detection Prep')).not.toBeInTheDocument();
      });
    });

    it('should filter recipes by description', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search recipes...');

      fireEvent.change(searchInput, { target: { value: 'anomaly' } });

      await waitFor(() => {
        expect(screen.queryByText('Data Cleaning Recipe')).not.toBeInTheDocument();
        expect(screen.getByText('Anomaly Detection Prep')).toBeInTheDocument();
      });
    });

    it('should filter recipes by tags', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search recipes...');

      fireEvent.change(searchInput, { target: { value: 'cleaning' } });

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
        expect(screen.queryByText('Feature Engineering')).not.toBeInTheDocument();
      });
    });

    it('should show empty state when no results match search', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search recipes...');

      fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

      await waitFor(() => {
        expect(screen.getByText('No recipes found')).toBeInTheDocument();
        expect(screen.getByText('Try adjusting your search filters')).toBeInTheDocument();
      });
    });
  });

  describe('Tag Filtering', () => {
    it('should display all available tags', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('cleaning')).toBeInTheDocument();
        expect(screen.getByText('preprocessing')).toBeInTheDocument();
        expect(screen.getByText('feature-engineering')).toBeInTheDocument();
        expect(screen.getByText('scaling')).toBeInTheDocument();
      });
    });

    it('should filter recipes when tag is selected', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('cleaning')).toBeInTheDocument();
      });

      const cleaningTag = screen.getByText('cleaning');

      fireEvent.click(cleaningTag);

      await waitFor(() => {
        expect(TransformationService.listRecipes).toHaveBeenCalledWith(
          'mock-token',
          1,
          12,
          true,
          ['cleaning']
        );
      });
    });

    it('should toggle tag selection', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('cleaning')).toBeInTheDocument();
      });

      const cleaningTag = screen.getByText('cleaning');

      // Select tag
      fireEvent.click(cleaningTag);

      await waitFor(() => {
        expect(TransformationService.listRecipes).toHaveBeenCalledWith(
          'mock-token',
          1,
          12,
          true,
          ['cleaning']
        );
      });

      // Deselect tag
      fireEvent.click(cleaningTag);

      await waitFor(() => {
        expect(TransformationService.listRecipes).toHaveBeenCalledWith(
          'mock-token',
          1,
          12,
          true,
          undefined
        );
      });
    });
  });

  describe('Sorting', () => {
    it('should sort by most recent by default', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        const recipeCards = screen.getAllByTestId(/recipe-card/);
        expect(recipeCards[0]).toHaveAttribute('data-testid', 'recipe-card-recipe-1');
      });
    });

    it('should sort by popularity', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      // Click the select trigger to open the dropdown
      const sortSelect = screen.getByRole('combobox');
      fireEvent.click(sortSelect);

      // Wait for the dropdown to open and click the "Most Popular" option
      await waitFor(() => {
        const popularOption = screen.getByText('Most Popular');
        expect(popularOption).toBeInTheDocument();
      });

      const popularOption = screen.getByText('Most Popular');
      fireEvent.click(popularOption);

      // Wait for recipes to be sorted by popularity (recipe-3 has highest usage_count: 15)
      await waitFor(() => {
        const recipeCards = screen.getAllByTestId(/recipe-card/);
        expect(recipeCards[0]).toHaveAttribute('data-testid', 'recipe-card-recipe-3');
      });
    });

    it('should sort by name alphabetically', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      // Click the select trigger to open the dropdown
      const sortSelect = screen.getByRole('combobox');
      fireEvent.click(sortSelect);

      // Wait for the dropdown to open and click the "Name (A-Z)" option
      await waitFor(() => {
        const nameOption = screen.getByText('Name (A-Z)');
        expect(nameOption).toBeInTheDocument();
      });

      const nameOption = screen.getByText('Name (A-Z)');
      fireEvent.click(nameOption);

      // Wait for recipes to be sorted by name (Anomaly Detection Prep comes first alphabetically)
      await waitFor(() => {
        const recipeCards = screen.getAllByTestId(/recipe-card/);
        expect(recipeCards[0]).toHaveAttribute('data-testid', 'recipe-card-recipe-3');
      });
    });
  });

  describe('View Mode Toggle', () => {
    it('should default to grid view', async () => {
      const { container } = render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const gridContainer = container.querySelector('.grid');
      expect(gridContainer).toBeInTheDocument();
    });

    it('should switch to list view', async () => {
      const { container } = render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const viewButtons = screen.getAllByRole('button');
      const listViewButton = viewButtons.find(btn => btn.querySelector('svg'));

      if (listViewButton) {
        fireEvent.click(listViewButton);
      }

      await waitFor(() => {
        const listContainer = container.querySelector('.space-y-4');
        expect(listContainer).toBeInTheDocument();
      });
    });
  });

  describe('Recipe Actions', () => {
    it('should call onApplyRecipe when apply button is clicked', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const applyButtons = screen.getAllByRole('button', { name: /apply/i });

      fireEvent.click(applyButtons[0]);

      expect(mockHandlers.onApplyRecipe).toHaveBeenCalledWith(mockRecipes[0]);
    });

    it('should duplicate recipe successfully', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const duplicateButtons = screen.getAllByRole('button', { name: /duplicate/i });

      fireEvent.click(duplicateButtons[0]);

      await waitFor(() => {
        expect(TransformationService.duplicateRecipe).toHaveBeenCalledWith(
          'recipe-1',
          'Data Cleaning Recipe (Copy)',
          'mock-token'
        );
      });

      expect(TransformationService.listRecipes).toHaveBeenCalledTimes(2);
    });

    it('should delete recipe successfully', async () => {
      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
      fireEvent.click(deleteButtons[0]);

      await waitFor(() => {
        expect(TransformationService.deleteRecipe).toHaveBeenCalledWith(
          'recipe-1',
          'mock-token'
        );
      });

      expect(TransformationService.listRecipes).toHaveBeenCalledTimes(2);
    });

    it('should display error when duplicate fails', async () => {
      (TransformationService.duplicateRecipe as jest.Mock).mockRejectedValueOnce(
        new Error('Duplicate failed')
      );

      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const duplicateButtons = screen.getAllByRole('button', { name: /duplicate/i });
      fireEvent.click(duplicateButtons[0]);

      // Wait for the error alert to appear
      await waitFor(() => {
        expect(screen.getByText('Duplicate failed')).toBeInTheDocument();
      }, { timeout: 2000 });
    });

    it('should display error when delete fails', async () => {
      (TransformationService.deleteRecipe as jest.Mock).mockRejectedValueOnce(
        new Error('Delete failed')
      );

      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
      fireEvent.click(deleteButtons[0]);

      // Wait for the error alert to appear
      await waitFor(() => {
        expect(screen.getByText('Delete failed')).toBeInTheDocument();
      }, { timeout: 2000 });
    });
  });

  describe('Pagination', () => {
    it('should show pagination when there are multiple pages', async () => {
      (TransformationService.listRecipes as jest.Mock).mockResolvedValue({
        recipes: mockRecipes,
        total: 25,
        page: 1,
        per_page: 12,
      });

      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
      expect(screen.getByText(/Page 1 of 3/i)).toBeInTheDocument();
    });

    it('should disable previous button on first page', async () => {
      (TransformationService.listRecipes as jest.Mock).mockResolvedValue({
        recipes: mockRecipes,
        total: 25,
        page: 1,
        per_page: 12,
      });

      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const prevButton = screen.getByRole('button', { name: /previous/i });
      expect(prevButton).toBeDisabled();
    });

    it('should navigate to next page', async () => {
      (TransformationService.listRecipes as jest.Mock).mockResolvedValue({
        recipes: mockRecipes,
        total: 25,
        page: 1,
        per_page: 12,
      });

      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
      });

      const nextButton = screen.getByRole('button', { name: /next/i });
      fireEvent.click(nextButton);

      await waitFor(() => {
        expect(TransformationService.listRecipes).toHaveBeenCalledWith(
          'mock-token',
          2,
          12,
          true,
          undefined
        );
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error when loading recipes fails', async () => {
      (TransformationService.listRecipes as jest.Mock).mockRejectedValueOnce(
        new Error('Failed to load')
      );

      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      // Wait for the error alert to appear
      await waitFor(() => {
        expect(screen.getByText('Failed to load')).toBeInTheDocument();
      }, { timeout: 2000 });
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no recipes exist', async () => {
      (TransformationService.listRecipes as jest.Mock).mockResolvedValue({
        recipes: [],
        total: 0,
        page: 1,
        per_page: 12,
      });

      render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

      await waitFor(() => {
        expect(screen.getByText('No recipes found')).toBeInTheDocument();
      });

      expect(screen.getByText('Create your first recipe to get started')).toBeInTheDocument();
    });
  });

  describe('Create Button', () => {
    it('should call onCreateNew when create button is clicked', async () => {
      render(
        <RecipeLibrary
          onApplyRecipe={mockHandlers.onApplyRecipe}
          onCreateNew={mockHandlers.onCreateNew}
          showCreateButton={true}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /create new recipe/i })).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /create new recipe/i });
      fireEvent.click(createButton);

      expect(mockHandlers.onCreateNew).toHaveBeenCalled();
    });
  });
});
