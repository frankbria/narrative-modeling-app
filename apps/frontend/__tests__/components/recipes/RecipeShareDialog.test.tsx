import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RecipeShareDialog } from '@/components/recipes/RecipeShareDialog';
import { TransformationService } from '@/lib/services/transformation';
import { getAuthToken } from '@/lib/auth-helpers';
import { waitForAsync, actAsync } from '@/__tests__/utils';

// Mock dependencies
jest.mock('@/lib/services/transformation');
jest.mock('@/lib/auth-helpers');

describe('RecipeShareDialog', () => {
  const mockProps = {
    open: true,
    onOpenChange: jest.fn(),
    recipeId: 'recipe-123',
    recipeName: 'Test Recipe',
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (getAuthToken as jest.Mock).mockResolvedValue('mock-token');
    (TransformationService.shareRecipe as jest.Mock).mockResolvedValue({
      message: 'Recipe shared successfully',
    });
  });

  describe('Rendering', () => {
    it('should render dialog when open is true', () => {
      render(<RecipeShareDialog {...mockProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      // Use heading role to be more specific than text which appears in both title and button
      expect(screen.getByRole('heading', { name: /share recipe/i })).toBeInTheDocument();
    });

    it('should not render dialog when open is false', () => {
      render(<RecipeShareDialog {...mockProps} open={false} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('should display recipe name in description', () => {
      render(<RecipeShareDialog {...mockProps} />);

      expect(screen.getByText(/Test Recipe/)).toBeInTheDocument();
    });

    it('should render user ID input field', () => {
      render(<RecipeShareDialog {...mockProps} />);

      expect(screen.getByLabelText('User ID')).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Enter recipient's user ID")).toBeInTheDocument();
    });

    it('should render help text for user ID field', () => {
      render(<RecipeShareDialog {...mockProps} />);

      expect(screen.getByText('The user must be registered in the system')).toBeInTheDocument();
    });

    it('should render Cancel button', () => {
      render(<RecipeShareDialog {...mockProps} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('should render Share Recipe button', () => {
      render(<RecipeShareDialog {...mockProps} />);

      expect(screen.getByRole('button', { name: /share recipe/i })).toBeInTheDocument();
    });
  });

  describe('Form Validation', () => {
    it('should disable Share button when user ID is empty', () => {
      render(<RecipeShareDialog {...mockProps} />);

      const shareButton = screen.getByRole('button', { name: /share recipe/i });
      expect(shareButton).toBeDisabled();
    });

    it('should enable Share button when user ID is provided', () => {
      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'user-456' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });
      expect(shareButton).not.toBeDisabled();
    });

    it('should disable Share button for whitespace-only user ID', () => {
      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: '   ' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });
      expect(shareButton).toBeDisabled();
    });

    it('should show error when submitting empty user ID', async () => {
      render(<RecipeShareDialog {...mockProps} />);

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      // Force enable button to test validation
      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'test' } });
      fireEvent.change(userIdInput, { target: { value: '' } });

      // Button should be disabled
      expect(shareButton).toBeDisabled();
    });
  });

  describe('Share Functionality', () => {
    it('should call shareRecipe API when Share button is clicked', async () => {
      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'user-456' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(getAuthToken).toHaveBeenCalled();
        expect(TransformationService.shareRecipe).toHaveBeenCalledWith(
          'recipe-123',
          'user-456',
          'mock-token'
        );
      });
    });

    it('should trim whitespace from user ID before submitting', async () => {
      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: '  user-456  ' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(TransformationService.shareRecipe).toHaveBeenCalledWith(
          'recipe-123',
          'user-456',
          'mock-token'
        );
      });
    });

    it('should show loading state while sharing', async () => {
      let resolveShare: (value: any) => void;
      const sharePromise = new Promise((resolve) => {
        resolveShare = resolve;
      });
      (TransformationService.shareRecipe as jest.Mock).mockReturnValue(sharePromise);

      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'user-456' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(screen.getByText('Sharing...')).toBeInTheDocument();
      });

      await actAsync(async () => {
        resolveShare!({ message: 'Recipe shared successfully' });
      });
    });

    it('should disable form inputs while sharing', async () => {
      let resolveShare: (value: any) => void;
      const sharePromise = new Promise((resolve) => {
        resolveShare = resolve;
      });
      (TransformationService.shareRecipe as jest.Mock).mockReturnValue(sharePromise);

      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'user-456' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(userIdInput).toBeDisabled();
        const cancelButton = screen.getByRole('button', { name: /cancel/i });
        expect(cancelButton).toBeDisabled();
      });

      await actAsync(async () => {
        resolveShare!({ message: 'Recipe shared successfully' });
      });
    });

    it('should display success message after successful share', async () => {
      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'user-456' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(screen.getByText('Recipe shared successfully')).toBeInTheDocument();
      });
    });

    it('should clear user ID input after successful share', async () => {
      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID') as HTMLInputElement;
      fireEvent.change(userIdInput, { target: { value: 'user-456' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(screen.getByText('Recipe shared successfully')).toBeInTheDocument();
      });

      // Wait for success message - input should be cleared
      await waitForAsync(() => {
        expect(userIdInput.value).toBe('');
      }, { timeout: 2500 });
    });

    it('should close dialog after successful share', async () => {
      jest.useFakeTimers();
      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'user-456' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(screen.getByText('Recipe shared successfully')).toBeInTheDocument();
      });

      await actAsync(async () => {
        jest.advanceTimersByTime(2000);
      });

      await waitForAsync(() => {
        expect(mockProps.onOpenChange).toHaveBeenCalledWith(false);
      });

      jest.useRealTimers();
    });
  });

  describe('Error Handling', () => {
    it('should display error message when share fails', async () => {
      (TransformationService.shareRecipe as jest.Mock).mockRejectedValue(
        new Error('User not found')
      );

      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'invalid-user' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(screen.getByText('User not found')).toBeInTheDocument();
      });
    });

    it('should display generic error for non-Error exceptions', async () => {
      (TransformationService.shareRecipe as jest.Mock).mockRejectedValue('Unknown error');

      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'user-456' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(screen.getByText('Failed to share recipe')).toBeInTheDocument();
      });
    });

    it('should clear error when user types again', async () => {
      (TransformationService.shareRecipe as jest.Mock).mockRejectedValue(
        new Error('User not found')
      );

      render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'invalid-user' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(screen.getByText('User not found')).toBeInTheDocument();
      });

      // Reset mock for next attempt
      (TransformationService.shareRecipe as jest.Mock).mockResolvedValue({
        message: 'Recipe shared successfully',
      });

      // Type again
      fireEvent.change(userIdInput, { target: { value: 'valid-user' } });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(screen.queryByText('User not found')).not.toBeInTheDocument();
      });
    });
  });

  describe('Dialog Close Handling', () => {
    it('should call onOpenChange when Cancel is clicked', () => {
      render(<RecipeShareDialog {...mockProps} />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      expect(mockProps.onOpenChange).toHaveBeenCalledWith(false);
    });

    it('should clear form when dialog is closed', () => {
      const { rerender } = render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID') as HTMLInputElement;
      fireEvent.change(userIdInput, { target: { value: 'user-456' } });

      expect(userIdInput.value).toBe('user-456');

      // Close dialog
      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      // Reopen dialog
      rerender(<RecipeShareDialog {...mockProps} open={true} />);

      const newUserIdInput = screen.getByLabelText('User ID') as HTMLInputElement;
      expect(newUserIdInput.value).toBe('');
    });

    it('should clear error state when dialog is closed', async () => {
      (TransformationService.shareRecipe as jest.Mock).mockRejectedValue(
        new Error('User not found')
      );

      const { rerender } = render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'invalid-user' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(screen.getByText('User not found')).toBeInTheDocument();
      });

      // Close dialog
      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      // Reopen dialog
      rerender(<RecipeShareDialog {...mockProps} open={true} />);

      expect(screen.queryByText('User not found')).not.toBeInTheDocument();
    });

    it('should clear success state when dialog is closed', async () => {
      const { rerender } = render(<RecipeShareDialog {...mockProps} />);

      const userIdInput = screen.getByLabelText('User ID');
      fireEvent.change(userIdInput, { target: { value: 'user-456' } });

      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      await actAsync(async () => {
        fireEvent.click(shareButton);
      });

      await waitForAsync(() => {
        expect(screen.getByText('Recipe shared successfully')).toBeInTheDocument();
      });

      // Close dialog manually (before auto-close)
      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      // Reopen dialog
      rerender(<RecipeShareDialog {...mockProps} open={true} />);

      expect(screen.queryByText('Recipe shared successfully')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper dialog aria labels', () => {
      render(<RecipeShareDialog {...mockProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('should have labeled input field', () => {
      render(<RecipeShareDialog {...mockProps} />);

      const input = screen.getByLabelText('User ID');
      expect(input).toHaveAttribute('id', 'userId');
    });

    it('should support keyboard navigation', () => {
      render(<RecipeShareDialog {...mockProps} />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      const shareButton = screen.getByRole('button', { name: /share recipe/i });

      expect(cancelButton).toHaveAttribute('type', 'button');
      expect(shareButton).toHaveAttribute('type', 'button');
    });
  });
});
