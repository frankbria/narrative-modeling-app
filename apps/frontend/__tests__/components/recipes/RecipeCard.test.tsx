import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RecipeCard } from '@/components/recipes/RecipeCard';
import { Recipe, RecipeCompatibilityResponse } from '@/lib/services/transformation';

// Mock the dialogs
jest.mock('@/components/recipes/RecipeShareDialog', () => ({
  RecipeShareDialog: ({ open, recipeName }: { open: boolean; recipeName: string }) =>
    open ? <div data-testid="share-dialog">Share {recipeName}</div> : null,
}));

jest.mock('@/components/recipes/RecipeExportDialog', () => ({
  RecipeExportDialog: ({ open, recipeName }: { open: boolean; recipeName: string }) =>
    open ? <div data-testid="export-dialog">Export {recipeName}</div> : null,
}));

jest.mock('@/components/recipes/RecipeCompatibilityBadge', () => ({
  RecipeCompatibilityBadge: ({ compatibility, isLoading }: { compatibility: RecipeCompatibilityResponse | null; isLoading: boolean }) => {
    if (isLoading) return <div>Loading compatibility...</div>;
    if (compatibility) {
      return <div data-testid="compatibility-badge">{compatibility.is_compatible ? 'Compatible' : 'Incompatible'}</div>;
    }
    return null;
  },
}));

describe('RecipeCard', () => {
  const mockRecipe: Recipe = {
    id: 'recipe-1',
    name: 'Test Recipe',
    description: 'A test recipe for unit testing',
    user_id: 'user-1',
    steps: [
      { step_id: 'step-1', type: 'remove_duplicates', parameters: {}, description: 'Remove duplicates', order: 0 },
      { step_id: 'step-2', type: 'fill_missing', parameters: { method: 'mean' }, description: 'Fill missing', order: 1 },
    ],
    tags: ['data-cleaning', 'preprocessing'],
    version: 1,
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
    is_public: false,
    usage_count: 5,
    rating: 4.5,
  };

  const mockCompatibility: RecipeCompatibilityResponse = {
    is_compatible: true,
    compatibility_score: 0.95,
    missing_columns: [],
    type_mismatches: [],
    warnings: [],
    suggestions: [],
  };

  const mockHandlers = {
    onApply: jest.fn(),
    onDuplicate: jest.fn(),
    onDelete: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Mock window.confirm
    global.confirm = jest.fn(() => true);
  });

  describe('Rendering', () => {
    it('should render recipe card with basic information', () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      expect(screen.getByText('Test Recipe')).toBeInTheDocument();
      expect(screen.getByText('A test recipe for unit testing')).toBeInTheDocument();
    });

    it('should display recipe tags', () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      expect(screen.getByText('data-cleaning')).toBeInTheDocument();
      expect(screen.getByText('preprocessing')).toBeInTheDocument();
    });

    it('should display steps count and usage count', () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      expect(screen.getByText(/2 steps/i)).toBeInTheDocument();
      expect(screen.getByText(/5 uses/i)).toBeInTheDocument();
    });

    it('should display creation date', () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      expect(screen.getByText(/Jan 15, 2024/i)).toBeInTheDocument();
    });

    it('should display rating when available', () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      expect(screen.getByText('4.5')).toBeInTheDocument();
    });

    it('should display public badge when recipe is public', () => {
      const publicRecipe = { ...mockRecipe, is_public: true };
      render(
        <RecipeCard
          recipe={publicRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      expect(screen.getByText('Public Recipe')).toBeInTheDocument();
    });

    it('should not display public badge when recipe is private', () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      expect(screen.queryByText('Public Recipe')).not.toBeInTheDocument();
    });
  });

  describe('Compatibility Badge', () => {
    it('should display compatibility badge when compatibility data is provided', () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          compatibility={mockCompatibility}
          currentUserId="user-2"
          showActions={true}
        />
      );

      expect(screen.getByTestId('compatibility-badge')).toBeInTheDocument();
      expect(screen.getByText('Compatible')).toBeInTheDocument();
    });

    it('should show loading state when compatibility is loading', () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          isLoadingCompatibility={true}
          currentUserId="user-2"
          showActions={true}
        />
      );

      expect(screen.getByText('Loading compatibility...')).toBeInTheDocument();
    });

    it('should not display compatibility badge when no compatibility data', () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      expect(screen.queryByTestId('compatibility-badge')).not.toBeInTheDocument();
    });
  });

  describe('Action Buttons', () => {
    it('should show action dropdown when showActions is true', () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      const dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      expect(dropdownTrigger).toBeInTheDocument();
    });

    it('should not show action dropdown when showActions is false', () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={false}
        />
      );

      const dropdownButtons = screen.queryAllByRole('button');
      expect(dropdownButtons.length).toBe(0);
    });

    it('should call onApply when Apply Recipe button is clicked', async () => {
      render(
        <RecipeCard
          recipe={mockRecipe}
          compatibility={mockCompatibility}
          onApply={mockHandlers.onApply}
          currentUserId="user-2"
          showActions={true}
        />
      );

      const applyButton = screen.getByRole('button', { name: /apply recipe/i });
      fireEvent.click(applyButton);

      expect(mockHandlers.onApply).toHaveBeenCalledWith(mockRecipe);
    });

    it('should disable Apply button when recipe is incompatible', () => {
      const incompatibleRecipe: RecipeCompatibilityResponse = {
        ...mockCompatibility,
        is_compatible: false,
        compatibility_score: 0.3,
      };

      render(
        <RecipeCard
          recipe={mockRecipe}
          compatibility={incompatibleRecipe}
          onApply={mockHandlers.onApply}
          currentUserId="user-2"
          showActions={true}
        />
      );

      const applyButton = screen.getByRole('button', { name: /apply recipe/i });
      expect(applyButton).toBeDisabled();
      expect(screen.getByText(/not compatible with the current dataset/i)).toBeInTheDocument();
    });

    it('should call onDuplicate when Duplicate is clicked from dropdown', async () => {
      const user = userEvent.setup();

      render(
        <RecipeCard
          recipe={mockRecipe}
          onDuplicate={mockHandlers.onDuplicate}
          currentUserId="user-2"
          showActions={true}
        />
      );

      // Open dropdown using aria-label
      const dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      await user.click(dropdownTrigger);

      // Wait for dropdown menu to appear and click Duplicate
      const duplicateItem = await screen.findByRole('menuitem', { name: /duplicate/i });
      await user.click(duplicateItem);

      expect(mockHandlers.onDuplicate).toHaveBeenCalledWith(mockRecipe);
    });
  });

  describe('Ownership Permissions', () => {
    it('should show Share option in dropdown when user is owner', async () => {
      const user = userEvent.setup();

      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-1"
          showActions={true}
        />
      );

      // Open dropdown
      const dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      await user.click(dropdownTrigger);

      // Wait for dropdown menu and verify Share option exists
      const shareItem = await screen.findByRole('menuitem', { name: /share/i });
      expect(shareItem).toBeInTheDocument();
    });

    it('should not show Share option when user is not owner', async () => {
      const user = userEvent.setup();

      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      // Open dropdown
      const dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      await user.click(dropdownTrigger);

      // Wait for dropdown menu to open
      await screen.findByRole('menuitem', { name: /export json/i });

      // Verify Share option does not exist
      expect(screen.queryByRole('menuitem', { name: /share/i })).not.toBeInTheDocument();
    });

    it('should show Delete option when user is owner', async () => {
      const user = userEvent.setup();

      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-1"
          onDelete={mockHandlers.onDelete}
          showActions={true}
        />
      );

      // Open dropdown
      const dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      await user.click(dropdownTrigger);

      // Wait for dropdown menu and verify Delete option exists
      const deleteItem = await screen.findByRole('menuitem', { name: /delete/i });
      expect(deleteItem).toBeInTheDocument();
    });

    it('should not show Delete option when user is not owner', async () => {
      const user = userEvent.setup();

      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          onDelete={mockHandlers.onDelete}
          showActions={true}
        />
      );

      // Open dropdown
      const dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      await user.click(dropdownTrigger);

      // Wait for dropdown menu to open
      await screen.findByRole('menuitem', { name: /export json/i });

      // Verify Delete option does not exist
      expect(screen.queryByRole('menuitem', { name: /delete/i })).not.toBeInTheDocument();
    });

    it('should confirm deletion before calling onDelete', async () => {
      const user = userEvent.setup();

      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-1"
          onDelete={mockHandlers.onDelete}
          showActions={true}
        />
      );

      // Open dropdown
      const dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      await user.click(dropdownTrigger);

      // Click Delete
      const deleteItem = await screen.findByRole('menuitem', { name: /delete/i });
      await user.click(deleteItem);

      expect(global.confirm).toHaveBeenCalledWith('Are you sure you want to delete "Test Recipe"?');
      expect(mockHandlers.onDelete).toHaveBeenCalledWith(mockRecipe);
    });

    it('should not delete when confirmation is cancelled', async () => {
      global.confirm = jest.fn(() => false);
      const user = userEvent.setup();

      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-1"
          onDelete={mockHandlers.onDelete}
          showActions={true}
        />
      );

      // Open dropdown
      const dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      await user.click(dropdownTrigger);

      // Click Delete
      const deleteItem = await screen.findByRole('menuitem', { name: /delete/i });
      await user.click(deleteItem);

      expect(mockHandlers.onDelete).not.toHaveBeenCalled();
    });
  });

  describe('Share Dialog', () => {
    it('should open share dialog when Share is clicked', async () => {
      const user = userEvent.setup();

      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-1"
          showActions={true}
        />
      );

      // Open dropdown
      const dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      await user.click(dropdownTrigger);

      // Click Share
      const shareItem = await screen.findByRole('menuitem', { name: /share/i });
      await user.click(shareItem);

      // Verify share dialog opens
      await waitFor(() => {
        expect(screen.getByTestId('share-dialog')).toBeInTheDocument();
      });
    });
  });

  describe('Export Dialog', () => {
    it('should open export dialog when Export JSON is clicked', async () => {
      const user = userEvent.setup();

      render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      // Open dropdown
      const dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      await user.click(dropdownTrigger);

      // Click Export JSON
      const exportItem = await screen.findByRole('menuitem', { name: /export json/i });
      await user.click(exportItem);

      await waitFor(() => {
        expect(screen.getByTestId('export-dialog')).toBeInTheDocument();
      });
    });

    it('should allow export for both owner and non-owner', async () => {
      const user = userEvent.setup();

      const { rerender } = render(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-1"
          showActions={true}
        />
      );

      // Test as owner
      let dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      await user.click(dropdownTrigger);

      const exportItemOwner = await screen.findByRole('menuitem', { name: /export json/i });
      expect(exportItemOwner).toBeInTheDocument();

      // Close dropdown by pressing Escape
      await user.keyboard('{Escape}');

      // Test as non-owner
      rerender(
        <RecipeCard
          recipe={mockRecipe}
          currentUserId="user-2"
          showActions={true}
        />
      );

      dropdownTrigger = screen.getByRole('button', { name: /recipe actions/i });
      await user.click(dropdownTrigger);

      const exportItemNonOwner = await screen.findByRole('menuitem', { name: /export json/i });
      expect(exportItemNonOwner).toBeInTheDocument();
    });
  });
});
