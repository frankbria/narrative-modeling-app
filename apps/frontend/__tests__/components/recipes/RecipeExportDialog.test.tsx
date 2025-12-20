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
    // Ensure clean DOM before each test
    document.body.innerHTML = '';

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
    global.Blob = jest.fn((content, options) => ({
      size: JSON.stringify(content).length,
      type: options?.type,
    })) as any;
  });

  afterEach(() => {
    cleanup();
    // Ensure timers are always real after each test
    jest.useRealTimers();
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

      fireEvent.click(downloadButton);

      await waitFor(() => {
        expect(global.Blob).toHaveBeenCalled();
      });

      const blobCall = (global.Blob as jest.Mock).mock.calls[0];
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
        expect(screen.getByRole('button', { name: /close/i })).toBeInTheDocument();
      });

      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);

      expect(mockProps.onOpenChange).toHaveBeenCalledWith(false);
    });

    it('should clear JSON data when dialog is closed', async () => {
      const { rerender } = render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText(/"name": "Test Recipe"/)).toBeInTheDocument();
      });

      // Close dialog
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);

      // Reopen dialog
      rerender(<RecipeExportDialog {...mockProps} open={true} />);

      // Should show loading again
      expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument();
    });

    it('should clear error state when dialog is closed', async () => {
      (TransformationService.exportRecipeAsJSON as jest.Mock).mockRejectedValue(
        new Error('Export failed')
      );

      const { rerender } = render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText('Failed to export recipe')).toBeInTheDocument();
      });

      // Close dialog
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);

      // Reset mock
      (TransformationService.exportRecipeAsJSON as jest.Mock).mockResolvedValue(mockRecipeJSON);

      // Reopen dialog
      rerender(<RecipeExportDialog {...mockProps} open={true} />);

      await waitFor(() => {
        expect(screen.queryByText('Failed to export recipe')).not.toBeInTheDocument();
      });
    });

    it('should clear copied state when dialog is closed', async () => {
      mockClipboard.writeText.mockResolvedValue(undefined);

      const { rerender } = render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /copy json/i })).toBeInTheDocument();
      });

      const copyButton = screen.getByRole('button', { name: /copy json/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(screen.getByText('Copied to clipboard!')).toBeInTheDocument();
      });

      // Close dialog
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);

      // Reopen dialog
      rerender(<RecipeExportDialog {...mockProps} open={true} />);

      await waitFor(() => {
        expect(screen.queryByText('Copied to clipboard!')).not.toBeInTheDocument();
      });
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
        const closeButton = screen.getByRole('button', { name: /close/i });
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
      (TransformationService.exportRecipeAsJSON as jest.Mock).mockResolvedValue({});

      render(<RecipeExportDialog {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByText(/\{\}/)).toBeInTheDocument();
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
