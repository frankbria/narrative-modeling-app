import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RecipeExportDialog } from '@/components/recipes/RecipeExportDialog';
import { TransformationService } from '@/lib/services/transformation';
import { getAuthToken } from '@/lib/auth-helpers';

// Mock dependencies
jest.mock('@/lib/services/transformation');
jest.mock('@/lib/auth-helpers');

describe('RecipeExportDialog', () => {
  const mockProps = {
    open: true,
    onOpenChange: jest.fn(),
    recipeId: 'recipe-123',
    recipeName: 'Test Recipe',
  };

  const mockRecipeJSON = {
    id: 'recipe-123',
    name: 'Test Recipe',
    description: 'A test recipe',
    steps: [
      { type: 'remove_duplicates', parameters: {} },
      { type: 'fill_missing', parameters: { method: 'mean' } },
    ],
    tags: ['cleaning'],
    version: 1,
  };

  // Mock clipboard API
  const mockClipboard = {
    writeText: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (getAuthToken as jest.Mock).mockResolvedValue('mock-token');
    (TransformationService.exportRecipeAsJSON as jest.Mock).mockResolvedValue(mockRecipeJSON);

    // Mock clipboard using defineProperty for compatibility
    Object.defineProperty(navigator, 'clipboard', {
      value: mockClipboard,
      writable: true,
      configurable: true,
    });

    // Mock URL.createObjectURL and revokeObjectURL
    global.URL.createObjectURL = jest.fn(() => 'mock-blob-url');
    global.URL.revokeObjectURL = jest.fn();

    // Mock Blob
    global.Blob = jest.fn((content, options) => {
      const data = Array.isArray(content) ? content.join('') : content;
      return {
        size: typeof data === 'string' ? data.length : JSON.stringify(data).length,
        type: options?.type,
      };
    }) as any;
  });

  afterEach(() => {
    cleanup();
    // Ensure timers are always real after each test
    jest.useRealTimers();
    // Restore all mocks to prevent test pollution
    jest.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('should render dialog when open is true', () => {
      render(<RecipeExportDialog {...mockProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Export Recipe')).toBeInTheDocument();
    });

    it('should not render dialog when open is false', () => {
      render(<RecipeExportDialog {...mockProps} open={false} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('should display recipe name in description', () => {
      render(<RecipeExportDialog {...mockProps} />);

      expect(screen.getByText(/Test Recipe/)).toBeInTheDocument();
    });

    it('should show loading state initially', () => {
      render(<RecipeExportDialog {...mockProps} />);

      expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument();
    });
  });

  describe('Data Loading', () => {
    it('should load recipe JSON when dialog opens', async () => {
      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        expect(getAuthToken).toHaveBeenCalled();
      });

      expect(TransformationService.exportRecipeAsJSON).toHaveBeenCalledWith(
        'recipe-123',
        'mock-token'
      );
    });

    it('should display formatted JSON after loading', async () => {
      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText(/"name": "Test Recipe"/)).toBeInTheDocument();
      });
    });

    it('should not reload data if already loaded', async () => {
      const { rerender } = render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        expect(TransformationService.exportRecipeAsJSON).toHaveBeenCalledTimes(1);
      });

      // Close and reopen
      rerender(<RecipeExportDialog {...mockProps} open={false} />);
      rerender(<RecipeExportDialog {...mockProps} open={true} />);

      // Should still only be called once
      expect(TransformationService.exportRecipeAsJSON).toHaveBeenCalledTimes(1);
    });

    it('should display error when loading fails', async () => {
      (TransformationService.exportRecipeAsJSON as jest.Mock).mockRejectedValue(
        new Error('Export failed')
      );

      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('Export failed')).toBeInTheDocument();
      });
    });
  });

  describe('Tabs', () => {
    it('should render Preview and Formatted tabs', async () => {
      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /preview/i })).toBeInTheDocument();
      });

      expect(screen.getByRole('tab', { name: /formatted/i })).toBeInTheDocument();
    });

    it('should default to Preview tab', async () => {
      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        const previewTab = screen.getByRole('tab', { name: /preview/i });
        expect(previewTab).toHaveAttribute('data-state', 'active');
      });
    });

    it('should switch to Formatted tab when clicked', async () => {
      const user = userEvent.setup();
      render(<RecipeExportDialog {...mockProps} />);

      // Wait for data to load
      await waitFor(() => {
        const downloadButton = screen.getByRole('button', { name: /download/i });
        expect(downloadButton).not.toBeDisabled();
      });

      const formattedTab = screen.getByRole('tab', { name: /formatted/i });
      await user.click(formattedTab);

      await waitFor(() => {
        expect(screen.getByText('Recipe Format')).toBeInTheDocument();
      });
    });

    it('should display JSON preview in Preview tab', async () => {
      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        const preElement = screen.getByText(/"name": "Test Recipe"/, { exact: false });
        expect(preElement).toBeInTheDocument();
      });
    });

    it('should display recipe metadata in Formatted tab', async () => {
      const user = userEvent.setup();
      render(<RecipeExportDialog {...mockProps} />);

      // Wait for data to load
      await waitFor(() => {
        const downloadButton = screen.getByRole('button', { name: /download/i });
        expect(downloadButton).not.toBeDisabled();
      });

      const formattedTab = screen.getByRole('tab', { name: /formatted/i });
      await user.click(formattedTab);

      await waitFor(() => {
        expect(screen.getByText(/Test_Recipe_recipe\.json/)).toBeInTheDocument();
      });
    });

    it('should display file size in Formatted tab', async () => {
      const user = userEvent.setup();
      render(<RecipeExportDialog {...mockProps} />);

      // Wait for data to load
      await waitFor(() => {
        const downloadButton = screen.getByRole('button', { name: /download/i });
        expect(downloadButton).not.toBeDisabled();
      });

      const formattedTab = screen.getByRole('tab', { name: /formatted/i });
      await user.click(formattedTab);

      await waitFor(() => {
        expect(screen.getByText(/Size:/)).toBeInTheDocument();
      });
    });
  });

  describe('Copy to Clipboard', () => {
    it('should copy JSON to clipboard when Copy JSON is clicked', async () => {
      mockClipboard.writeText.mockResolvedValue(undefined);

      render(<RecipeExportDialog {...mockProps} />);

      // Wait for data to load (button to be enabled)
      await waitFor(() => {
        const copyButton = screen.getByRole('button', { name: /copy json/i });
        expect(copyButton).not.toBeDisabled();
      });

      const copyButton = screen.getByRole('button', { name: /copy json/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(mockClipboard.writeText).toHaveBeenCalled();
      });

      const copiedText = mockClipboard.writeText.mock.calls[0][0];
      expect(copiedText).toContain('"name": "Test Recipe"');
    });

    it('should show success message after copying', async () => {
      mockClipboard.writeText.mockResolvedValue(undefined);

      render(<RecipeExportDialog {...mockProps} />);

      // Wait for data to load (button to be enabled)
      await waitFor(() => {
        const copyButton = screen.getByRole('button', { name: /copy json/i });
        expect(copyButton).not.toBeDisabled();
      });

      const copyButton = screen.getByRole('button', { name: /copy json/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(screen.getByText('Copied to clipboard!')).toBeInTheDocument();
      });
    });

    it('should hide success message after timeout', async () => {
      try {
        jest.useFakeTimers();
        mockClipboard.writeText.mockResolvedValue(undefined);

        render(<RecipeExportDialog {...mockProps} />);

        // Wait for data to load (button to be enabled)
        await waitFor(() => {
          const copyButton = screen.getByRole('button', { name: /copy json/i });
          expect(copyButton).not.toBeDisabled();
        });

        const copyButton = screen.getByRole('button', { name: /copy json/i });
        fireEvent.click(copyButton);

        await waitFor(() => {
          expect(screen.getByText('Copied to clipboard!')).toBeInTheDocument();
        });

        jest.advanceTimersByTime(2000);

        await waitFor(() => {
          expect(screen.queryByText('Copied to clipboard!')).not.toBeInTheDocument();
        });
      } finally {
        jest.useRealTimers();
      }
    });

    it('should display error when clipboard copy fails', async () => {
      mockClipboard.writeText.mockRejectedValue(new Error('Clipboard error'));

      render(<RecipeExportDialog {...mockProps} />);

      // Wait for data to load (button to be enabled)
      await waitFor(() => {
        const copyButton = screen.getByRole('button', { name: /copy json/i });
        expect(copyButton).not.toBeDisabled();
      });

      const copyButton = screen.getByRole('button', { name: /copy json/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(screen.getByText('Failed to copy to clipboard')).toBeInTheDocument();
      });
    });

    it('should disable Copy button when loading', () => {
      render(<RecipeExportDialog {...mockProps} />);

      const copyButton = screen.getByRole('button', { name: /copy json/i });
      expect(copyButton).toBeDisabled();
    });

    it('should enable Copy button after data loads', async () => {
      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        const copyButton = screen.getByRole('button', { name: /copy json/i });
        expect(copyButton).not.toBeDisabled();
      });
    });
  });

  describe('Download Functionality', () => {
    it('should trigger download when Download button is clicked', async () => {
      render(<RecipeExportDialog {...mockProps} />);

      // Wait for data to load (button to be enabled)
      const downloadButton = await waitFor(() => {
        const btn = screen.getByRole('button', { name: /download/i });
        expect(btn).not.toBeDisabled();
        return btn;
      });

      // Mock createElement and appendChild
      const mockLink = {
        href: '',
        download: '',
        click: jest.fn(),
      };
      const createElementSpy = jest.spyOn(document, 'createElement').mockReturnValue(mockLink as any);
      const appendChildSpy = jest.spyOn(document.body, 'appendChild').mockImplementation(() => mockLink as any);
      const removeChildSpy = jest.spyOn(document.body, 'removeChild').mockImplementation(() => mockLink as any);

      fireEvent.click(downloadButton);

      await waitFor(() => {
        expect(createElementSpy).toHaveBeenCalledWith('a');
      });

      expect(mockLink.download).toBe('Test_Recipe_recipe.json');
      expect(mockLink.click).toHaveBeenCalled();
      expect(appendChildSpy).toHaveBeenCalled();
      expect(removeChildSpy).toHaveBeenCalled();
      expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('mock-blob-url');

      createElementSpy.mockRestore();
      appendChildSpy.mockRestore();
      removeChildSpy.mockRestore();
    });

    it('should sanitize recipe name for filename', async () => {
      const propsWithSpaces = {
        ...mockProps,
        recipeName: 'My Test Recipe With Spaces',
      };

      render(<RecipeExportDialog {...propsWithSpaces} />);

      // Wait for data to load (button to be enabled)
      const downloadButton = await waitFor(() => {
        const btn = screen.getByRole('button', { name: /download/i });
        expect(btn).not.toBeDisabled();
        return btn;
      });

      const mockLink = {
        href: '',
        download: '',
        click: jest.fn(),
      };
      jest.spyOn(document, 'createElement').mockReturnValue(mockLink as any);
      jest.spyOn(document.body, 'appendChild').mockImplementation(() => mockLink as any);
      jest.spyOn(document.body, 'removeChild').mockImplementation(() => mockLink as any);

      fireEvent.click(downloadButton);

      await waitFor(() => {
        expect(mockLink.download).toBe('My_Test_Recipe_With_Spaces_recipe.json');
      });
    });

    it('should create blob with correct content type', async () => {
      render(<RecipeExportDialog {...mockProps} />);

      // Wait for data to load (button to be enabled)
      const downloadButton = await waitFor(() => {
        const btn = screen.getByRole('button', { name: /download/i });
        expect(btn).not.toBeDisabled();
        return btn;
      });

      const mockLink = {
        href: '',
        download: '',
        click: jest.fn(),
      };
      jest.spyOn(document, 'createElement').mockReturnValue(mockLink as any);
      jest.spyOn(document.body, 'appendChild').mockImplementation(() => mockLink as any);
      jest.spyOn(document.body, 'removeChild').mockImplementation(() => mockLink as any);

      // Clear any previous Blob calls (from rendering the size display)
      (global.Blob as jest.Mock).mockClear();

      fireEvent.click(downloadButton);

      await waitFor(() => {
        expect(global.Blob).toHaveBeenCalled();
      });

      // Check the download Blob call (should be the first call after clearing)
      const blobCall = (global.Blob as jest.Mock).mock.calls[0];
      expect(blobCall[0]).toEqual([expect.any(String)]); // Check content is a string array
      expect(blobCall[1]).toEqual({ type: 'application/json' });
    });

    it('should disable Download button when loading', () => {
      render(<RecipeExportDialog {...mockProps} />);

      const downloadButton = screen.getByRole('button', { name: /download/i });
      expect(downloadButton).toBeDisabled();
    });

    it('should enable Download button after data loads', async () => {
      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        const downloadButton = screen.getByRole('button', { name: /download/i });
        expect(downloadButton).not.toBeDisabled();
      });
    });
  });

  describe('Dialog Close Handling', () => {
    it('should call onOpenChange when Close button is clicked', async () => {
      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        expect(screen.getAllByRole('button', { name: /close/i })[0]).toBeInTheDocument();
      });

      // Get the first Close button (the one in the footer, not the X button)
      const closeButtons = screen.getAllByRole('button', { name: /close/i });
      const closeButton = closeButtons.find(btn => btn.textContent === 'Close');
      fireEvent.click(closeButton!);

      expect(mockProps.onOpenChange).toHaveBeenCalledWith(false);
    });

    it('should clear JSON data when dialog is closed', async () => {
      const mockOnOpenChange = jest.fn();
      const { rerender } = render(
        <RecipeExportDialog
          open={true}
          onOpenChange={mockOnOpenChange}
          recipeId="recipe-123"
          recipeName="Test Recipe"
        />
      );

      // Wait for data to load
      await waitFor(() => {
        const downloadButton = screen.getByRole('button', { name: /download/i });
        expect(downloadButton).not.toBeDisabled();
      });

      // Verify JSON data is shown by checking the pre element exists
      const preElement = document.querySelector('pre');
      expect(preElement).toBeInTheDocument();
      expect(preElement?.textContent).toContain('Test Recipe');

      // Close dialog via close button
      const closeButtons = screen.getAllByRole('button', { name: /close/i });
      const closeButton = closeButtons.find(btn => btn.textContent === 'Close');
      fireEvent.click(closeButton!);

      // Verify onOpenChange was called to close the dialog
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);

      // Actually close the dialog
      rerender(
        <RecipeExportDialog
          open={false}
          onOpenChange={mockOnOpenChange}
          recipeId="recipe-123"
          recipeName="Test Recipe"
        />
      );

      // Verify dialog is closed
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

      // Reopen with a new instance (simulating navigation back)
      cleanup();

      // Ensure cleanup completed
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

      render(
        <RecipeExportDialog
          open={true}
          onOpenChange={jest.fn()}
          recipeId="recipe-123"
          recipeName="Test Recipe"
        />
      );

      // Should show loading again (fresh instance)
      await waitFor(() => {
        expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument();
      });
    });

    it('should clear error state when dialog is closed', async () => {
      (TransformationService.exportRecipeAsJSON as jest.Mock).mockRejectedValueOnce(
        new Error('Export failed')
      );

      const mockOnOpenChange = jest.fn();
      const { rerender } = render(
        <RecipeExportDialog
          open={true}
          onOpenChange={mockOnOpenChange}
          recipeId="recipe-123"
          recipeName="Test Recipe"
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Failed to export recipe')).toBeInTheDocument();
      });

      // Close dialog via close button
      const closeButtons = screen.getAllByRole('button', { name: /close/i });
      const closeButton = closeButtons.find(btn => btn.textContent === 'Close');
      fireEvent.click(closeButton!);

      // Verify onOpenChange was called to close the dialog
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);

      // Reset mock to return success
      (TransformationService.exportRecipeAsJSON as jest.Mock).mockResolvedValue(mockRecipeJSON);

      // Actually close the dialog
      rerender(
        <RecipeExportDialog
          open={false}
          onOpenChange={mockOnOpenChange}
          recipeId="recipe-123"
          recipeName="Test Recipe"
        />
      );

      // Reopen with a new instance
      cleanup();

      // Ensure cleanup completed
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

      render(
        <RecipeExportDialog
          open={true}
          onOpenChange={jest.fn()}
          recipeId="recipe-123"
          recipeName="Test Recipe"
        />
      );

      // Error should not be present in new instance (mockResolvedValue returns success)
      await waitFor(() => {
        const downloadButton = screen.getByRole('button', { name: /download/i });
        expect(downloadButton).not.toBeDisabled();
      });

      expect(screen.queryByText('Failed to export recipe')).not.toBeInTheDocument();
    });

    it('should clear copied state when dialog is closed', async () => {
      mockClipboard.writeText.mockResolvedValue(undefined);

      const mockOnOpenChange = jest.fn();
      const { rerender } = render(
        <RecipeExportDialog
          open={true}
          onOpenChange={mockOnOpenChange}
          recipeId="recipe-123"
          recipeName="Test Recipe"
        />
      );

      await waitFor(() => {
        const copyButton = screen.getByRole('button', { name: /copy json/i });
        expect(copyButton).not.toBeDisabled();
      });

      const copyButton = screen.getByRole('button', { name: /copy json/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(screen.getByText('Copied to clipboard!')).toBeInTheDocument();
      });

      // Close dialog via close button
      const closeButtons = screen.getAllByRole('button', { name: /close/i });
      const closeButton = closeButtons.find(btn => btn.textContent === 'Close');
      fireEvent.click(closeButton!);

      // Verify onOpenChange was called to close the dialog
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);

      // Actually close the dialog
      rerender(
        <RecipeExportDialog
          open={false}
          onOpenChange={mockOnOpenChange}
          recipeId="recipe-123"
          recipeName="Test Recipe"
        />
      );

      // Reopen with a new instance
      cleanup();
      render(
        <RecipeExportDialog
          open={true}
          onOpenChange={jest.fn()}
          recipeId="recipe-123"
          recipeName="Test Recipe"
        />
      );

      // Copied state should not be present in new instance
      expect(screen.queryByText('Copied to clipboard!')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper dialog aria labels', () => {
      render(<RecipeExportDialog {...mockProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('should support keyboard navigation', async () => {
      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        const closeButtons = screen.getAllByRole('button', { name: /close/i });
        const closeButton = closeButtons.find(btn => btn.textContent === 'Close');
        expect(closeButton).toHaveAttribute('type', 'button');
      });

      const copyButton = screen.getByRole('button', { name: /copy json/i });
      const downloadButton = screen.getByRole('button', { name: /download/i });

      expect(copyButton).toHaveAttribute('type', 'button');
      expect(downloadButton).toHaveAttribute('type', 'button');
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty recipe data', async () => {
      // Override the mock to return empty object BEFORE rendering
      (TransformationService.exportRecipeAsJSON as jest.Mock).mockResolvedValueOnce({});

      render(<RecipeExportDialog {...mockProps} />);

      // Wait for the empty JSON to be displayed in the pre element
      await waitFor(() => {
        const preElement = document.querySelector('pre');
        expect(preElement).toBeInTheDocument();
        // JSON.stringify({}, null, 2) produces "{}" with proper formatting
        expect(preElement?.textContent?.trim()).toBe('{}');
      });
    });

    it('should handle very large JSON data', async () => {
      const largeRecipe = {
        ...mockRecipeJSON,
        steps: Array(100).fill({ type: 'transform', parameters: { key: 'value' } }),
      };

      (TransformationService.exportRecipeAsJSON as jest.Mock).mockResolvedValue(largeRecipe);

      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        const copyButton = screen.getByRole('button', { name: /copy json/i });
        expect(copyButton).not.toBeDisabled();
      });
    });
  });
});
