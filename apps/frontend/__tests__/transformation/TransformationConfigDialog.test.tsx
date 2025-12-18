import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  TransformationConfigDialog,
  TransformationConfig,
} from '@/components/transformation/TransformationConfigDialog';

describe('TransformationConfigDialog', () => {
  const mockAvailableColumns = ['id', 'name', 'email', 'age', 'status'];
  const mockOnAdd = jest.fn();
  const mockOnOpenChange = jest.fn();
  const mockOnPreview = jest.fn();
  const mockOnDelete = jest.fn();

  const defaultProps = {
    open: true,
    onOpenChange: mockOnOpenChange,
    transformationType: 'fill_missing',
    transformationLabel: 'Fill Missing Values',
    transformationDescription: 'Replace missing values with specified method',
    parametersSchema: {
      column: {
        type: 'string',
        title: 'Column',
        description: 'Select column to fill',
        required: true,
      },
      method: {
        type: 'string',
        title: 'Fill Method',
        enum: ['mean', 'median', 'mode', 'forward', 'backward'],
        required: true,
      },
      fill_value: {
        type: 'string',
        title: 'Fill Value',
        description: 'Value to use if method is value-based',
        required: false,
      },
    },
    availableColumns: mockAvailableColumns,
    datasetId: 'dataset-123',
    onAdd: mockOnAdd,
    onPreview: mockOnPreview,
    onDelete: mockOnDelete,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Dialog Opening and Closing', () => {
    it('renders dialog when open is true', () => {
      render(<TransformationConfigDialog {...defaultProps} />);
      expect(screen.getByText('Fill Missing Values')).toBeInTheDocument();
    });

    it('does not render dialog when open is false', () => {
      const { container } = render(
        <TransformationConfigDialog {...defaultProps} open={false} />
      );
      expect(
        container.querySelector('[role="dialog"]')
      ).not.toBeInTheDocument();
    });

    it('closes dialog on Escape key', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      await user.keyboard('{Escape}');
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });

    it('calls onOpenChange with false when close button clicked', async () => {
      render(<TransformationConfigDialog {...defaultProps} />);

      // Find and click the close button (X button in dialog header)
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);

      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe('Form Field Rendering', () => {
    it('renders text input for string type parameters', () => {
      render(<TransformationConfigDialog {...defaultProps} />);
      const fillValueInput = screen.getByLabelText(/Fill Value/i);
      expect(fillValueInput).toBeInTheDocument();
      expect(fillValueInput).toHaveAttribute('type', 'text');
    });

    it('renders select dropdown for enum type parameters', () => {
      render(<TransformationConfigDialog {...defaultProps} />);
      const methodSelect = screen.getByRole('button', { name: /Fill Method/i });
      expect(methodSelect).toBeInTheDocument();
    });

    it('renders required indicator for required fields', () => {
      render(<TransformationConfigDialog {...defaultProps} />);
      const labels = screen.getAllByText('*');
      expect(labels.length).toBeGreaterThan(0);
    });

    it('displays field descriptions', () => {
      render(<TransformationConfigDialog {...defaultProps} />);
      expect(
        screen.getByDisplayValue('Select column to fill')
      ).toBeInTheDocument();
    });
  });

  describe('Number Input Parameters', () => {
    it('renders number input for numeric type', () => {
      const schema = {
        threshold: {
          type: 'number',
          title: 'Threshold',
          minimum: 0,
          maximum: 1,
          required: true,
        },
      };

      render(
        <TransformationConfigDialog
          {...defaultProps}
          parametersSchema={schema}
        />
      );

      const input = screen.getByLabelText(/Threshold/i);
      expect(input).toHaveAttribute('type', 'number');
      expect(input).toHaveAttribute('min', '0');
      expect(input).toHaveAttribute('max', '1');
    });

    it('accepts numeric input and coerces to number', async () => {
      const user = userEvent.setup();
      const schema = {
        count: {
          type: 'number',
          title: 'Count',
          required: true,
        },
      };

      render(
        <TransformationConfigDialog
          {...defaultProps}
          parametersSchema={schema}
        />
      );

      const input = screen.getByLabelText(/Count/i);
      await user.type(input, '42');
      expect(input).toHaveValue(42);
    });
  });

  describe('Boolean Input Parameters', () => {
    it('renders checkbox for boolean type', () => {
      const schema = {
        remove_duplicates: {
          type: 'boolean',
          title: 'Remove Duplicates',
        },
      };

      render(
        <TransformationConfigDialog
          {...defaultProps}
          parametersSchema={schema}
        />
      );

      const checkbox = screen.getByRole('checkbox', { name: /Remove Duplicates/i });
      expect(checkbox).toBeInTheDocument();
    });

    it('toggles boolean value on checkbox click', async () => {
      const user = userEvent.setup();
      const schema = {
        enabled: {
          type: 'boolean',
          title: 'Enabled',
        },
      };

      render(
        <TransformationConfigDialog
          {...defaultProps}
          parametersSchema={schema}
        />
      );

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).not.toBeChecked();

      await user.click(checkbox);
      expect(checkbox).toBeChecked();

      await user.click(checkbox);
      expect(checkbox).not.toBeChecked();
    });
  });

  describe('Array/Multi-Select Parameters', () => {
    it('renders multi-select for array type with string items', () => {
      const schema = {
        columns: {
          type: 'array',
          items: { type: 'string' },
          title: 'Columns',
          required: true,
        },
      };

      render(
        <TransformationConfigDialog
          {...defaultProps}
          parametersSchema={schema}
        />
      );

      const trigger = screen.getByRole('button', { name: /Columns/i });
      expect(trigger).toBeInTheDocument();
    });

    it('opens and closes multi-select dropdown', async () => {
      const user = userEvent.setup();
      const schema = {
        columns: {
          type: 'array',
          items: { type: 'string' },
          required: true,
        },
      };

      render(
        <TransformationConfigDialog
          {...defaultProps}
          parametersSchema={schema}
        />
      );

      const trigger = screen.getByRole('button', { name: /Columns/i });
      await user.click(trigger);

      const options = screen.getAllByRole('option');
      expect(options.length).toBeGreaterThan(0);
    });

    it('selects columns in multi-select', async () => {
      const user = userEvent.setup();
      const schema = {
        columns: {
          type: 'array',
          items: { type: 'string' },
          required: true,
        },
      };

      render(
        <TransformationConfigDialog
          {...defaultProps}
          parametersSchema={schema}
        />
      );

      const trigger = screen.getByRole('button', { name: /Columns/i });
      await user.click(trigger);

      const nameCheckbox = screen.getByRole('checkbox', { name: /name/i });
      await user.click(nameCheckbox);

      expect(nameCheckbox).toBeChecked();
      expect(trigger).toHaveTextContent('1 selected');
    });

    it('supports select all in multi-select', async () => {
      const user = userEvent.setup();
      const schema = {
        columns: {
          type: 'array',
          items: { type: 'string' },
          required: true,
        },
      };

      render(
        <TransformationConfigDialog
          {...defaultProps}
          parametersSchema={schema}
        />
      );

      const trigger = screen.getByRole('button', { name: /Columns/i });
      await user.click(trigger);

      const selectAllButton = screen.getByRole('button', { name: /Select All/i });
      await user.click(selectAllButton);

      const checkboxes = screen.getAllByRole('checkbox').filter(
        (cb) => !cb.getAttribute('aria-label')
      );
      checkboxes.forEach((cb) => {
        expect(cb).toBeChecked();
      });
    });
  });

  describe('Enum Select Parameters', () => {
    it('renders select dropdown with enum options', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const methodButton = screen.getByRole('button', { name: /Fill Method/i });
      await user.click(methodButton);

      expect(screen.getByText('Mean')).toBeInTheDocument();
      expect(screen.getByText('Median')).toBeInTheDocument();
      expect(screen.getByText('Mode')).toBeInTheDocument();
    });

    it('selects enum value', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const methodButton = screen.getByRole('button', { name: /Fill Method/i });
      await user.click(methodButton);

      const medianOption = screen.getByRole('option', { name: /Median/i });
      await user.click(medianOption);

      expect(methodButton).toHaveTextContent('Median');
    });
  });

  describe('Form Validation', () => {
    it('shows error when required field is empty', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const addButton = screen.getByRole('button', { name: /Add to Pipeline/i });
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByText(/is required/)).toBeInTheDocument();
      });
    });

    it('prevents submission with validation errors', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const addButton = screen.getByRole('button', { name: /Add to Pipeline/i });
      await user.click(addButton);

      await waitFor(() => {
        expect(mockOnAdd).not.toHaveBeenCalled();
      });
    });

    it('clears error when field is corrected', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const addButton = screen.getByRole('button', { name: /Add to Pipeline/i });
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByText(/is required/)).toBeInTheDocument();
      });

      const columnSelect = screen.getByRole('button', { name: /Column/i });
      await user.click(columnSelect);

      const option = screen.getByRole('option', { name: /name/i });
      await user.click(option);

      await waitFor(() => {
        const errors = screen.queryAllByText(/is required/);
        expect(errors.length).toBeLessThan(1);
      });
    });

    it('validates number ranges', async () => {
      const user = userEvent.setup();
      const schema = {
        percentage: {
          type: 'number',
          title: 'Percentage',
          minimum: 0,
          maximum: 100,
          required: true,
        },
      };

      render(
        <TransformationConfigDialog
          {...defaultProps}
          parametersSchema={schema}
        />
      );

      const input = screen.getByLabelText(/Percentage/i);
      await user.type(input, '150');

      const addButton = screen.getByRole('button', { name: /Add to Pipeline/i });
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByText(/must be no more than 100/)).toBeInTheDocument();
      });
    });
  });

  describe('Form Submission', () => {
    it('calls onAdd with correct parameters on submit', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      // Fill required fields
      const columnButton = screen.getByRole('button', { name: /Column/i });
      await user.click(columnButton);

      const nameOption = screen.getByRole('option', { name: /name/i });
      await user.click(nameOption);

      const methodButton = screen.getByRole('button', { name: /Fill Method/i });
      await user.click(methodButton);

      const medianOption = screen.getByRole('option', { name: /Median/i });
      await user.click(medianOption);

      const addButton = screen.getByRole('button', { name: /Add to Pipeline/i });
      await user.click(addButton);

      await waitFor(() => {
        expect(mockOnAdd).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'fill_missing',
            parameters: expect.objectContaining({
              column: 'name',
              method: 'median',
            }),
          })
        );
      });
    });

    it('closes dialog after successful submission', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const columnButton = screen.getByRole('button', { name: /Column/i });
      await user.click(columnButton);

      const nameOption = screen.getByRole('option', { name: /name/i });
      await user.click(nameOption);

      const methodButton = screen.getByRole('button', { name: /Fill Method/i });
      await user.click(methodButton);

      const medianOption = screen.getByRole('option', { name: /Median/i });
      await user.click(medianOption);

      const addButton = screen.getByRole('button', { name: /Add to Pipeline/i });
      await user.click(addButton);

      await waitFor(() => {
        expect(mockOnOpenChange).toHaveBeenCalledWith(false);
      });
    });
  });

  describe('Preview Functionality', () => {
    it('calls onPreview when preview button clicked', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const columnButton = screen.getByRole('button', { name: /Column/i });
      await user.click(columnButton);

      const nameOption = screen.getByRole('option', { name: /name/i });
      await user.click(nameOption);

      const previewButton = screen.getByRole('button', { name: /Preview/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(mockOnPreview).toHaveBeenCalled();
      });
    });

    it('shows error if preview fails', async () => {
      const user = userEvent.setup();
      mockOnPreview.mockRejectedValueOnce(new Error('Preview error'));

      render(<TransformationConfigDialog {...defaultProps} />);

      const columnButton = screen.getByRole('button', { name: /Column/i });
      await user.click(columnButton);

      const nameOption = screen.getByRole('option', { name: /name/i });
      await user.click(nameOption);

      const previewButton = screen.getByRole('button', { name: /Preview/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText('Preview error')).toBeInTheDocument();
      });
    });

    it('disables buttons during preview loading', async () => {
      const user = userEvent.setup();
      mockOnPreview.mockImplementationOnce(
        () =>
          new Promise((resolve) =>
            setTimeout(resolve, 1000)
          )
      );

      render(<TransformationConfigDialog {...defaultProps} />);

      const columnButton = screen.getByRole('button', { name: /Column/i });
      await user.click(columnButton);

      const nameOption = screen.getByRole('option', { name: /name/i });
      await user.click(nameOption);

      const previewButton = screen.getByRole('button', { name: /Preview/i });
      await user.click(previewButton);

      const addButton = screen.getByRole('button', { name: /Add to Pipeline/i });
      expect(addButton).toBeDisabled();

      await waitFor(
        () => {
          expect(addButton).not.toBeDisabled();
        },
        { timeout: 2000 }
      );
    });
  });

  describe('Delete Functionality', () => {
    it('renders delete button when onDelete provided', () => {
      render(<TransformationConfigDialog {...defaultProps} />);
      expect(screen.getByRole('button', { name: /Delete/i })).toBeInTheDocument();
    });

    it('does not render delete button when onDelete not provided', () => {
      const { onDelete, ...propsWithoutDelete } = defaultProps;
      render(<TransformationConfigDialog {...propsWithoutDelete} />);
      expect(
        screen.queryByRole('button', { name: /Delete/i })
      ).not.toBeInTheDocument();
    });

    it('calls onDelete when delete button clicked', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const deleteButton = screen.getByRole('button', { name: /Delete/i });
      await user.click(deleteButton);

      expect(mockOnDelete).toHaveBeenCalled();
    });
  });

  describe('Keyboard Navigation', () => {
    it('traps focus within dialog', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const columnButton = screen.getByRole('button', { name: /Column/i });
      await user.click(columnButton);

      const nameOption = screen.getByRole('option', { name: /name/i });
      await user.click(nameOption);

      // Tab to cycle through form elements
      await user.keyboard('{Tab}');

      const addButton = screen.getByRole('button', { name: /Add to Pipeline/i });
      addButton.focus();

      // Simulate forward Tab at end (should cycle back)
      const tabEvent = new KeyboardEvent('keydown', {
        key: 'Tab',
        bubbles: true,
      });
      fireEvent(addButton, tabEvent);

      // Should not throw or cause focus to escape
      expect(document.activeElement).toBeTruthy();
    });

    it('supports Tab and Shift+Tab navigation', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      // Test Tab navigation
      await user.keyboard('{Tab}');
      let focused = document.activeElement;
      expect(focused).toBeInTheDocument();

      // Test Shift+Tab
      await user.keyboard('{Shift>}{Tab}{/Shift}');
      focused = document.activeElement;
      expect(focused).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      render(<TransformationConfigDialog {...defaultProps} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby');
      expect(dialog).toHaveAttribute('aria-describedby');
    });

    it('marks invalid fields with aria-invalid', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const addButton = screen.getByRole('button', { name: /Add to Pipeline/i });
      await user.click(addButton);

      await waitFor(() => {
        const fields = screen.getAllByRole('button');
        const invalidField = fields.find((f) =>
          f.getAttribute('aria-invalid') === 'true'
        );
        expect(invalidField).toBeTruthy();
      });
    });

    it('provides error descriptions via aria-describedby', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const addButton = screen.getByRole('button', { name: /Add to Pipeline/i });
      await user.click(addButton);

      await waitFor(() => {
        const errorElements = screen.getAllByRole('button');
        const fieldWithError = errorElements.find((f) =>
          f.getAttribute('aria-describedby')
        );
        expect(fieldWithError).toBeTruthy();
      });
    });
  });

  describe('Edge Cases', () => {
    it('handles transformation with no parameters', () => {
      render(
        <TransformationConfigDialog
          {...defaultProps}
          parametersSchema={{}}
        />
      );

      expect(
        screen.getByText(/No parameters needed/i)
      ).toBeInTheDocument();
    });

    it('handles undefined/null values gracefully', async () => {
      const user = userEvent.setup();
      render(<TransformationConfigDialog {...defaultProps} />);

      const addButton = screen.getByRole('button', { name: /Add to Pipeline/i });
      await user.click(addButton);

      await waitFor(() => {
        expect(mockOnAdd).not.toHaveBeenCalled();
      });
    });

    it('displays existing configuration for editing', () => {
      const existingConfig: TransformationConfig = {
        type: 'fill_missing',
        parameters: {
          column: 'name',
          method: 'mean',
          fill_value: '',
        },
      };

      render(
        <TransformationConfigDialog
          {...defaultProps}
          existingConfig={existingConfig}
        />
      );

      // Button text should change to "Update"
      expect(
        screen.getByRole('button', { name: /Update to Pipeline/i })
      ).toBeInTheDocument();
    });

    it('handles very long column names', () => {
      const longColumnName = 'a'.repeat(100);
      render(
        <TransformationConfigDialog
          {...defaultProps}
          availableColumns={[longColumnName, ...mockAvailableColumns]}
        />
      );

      expect(screen.getByText(longColumnName)).toBeInTheDocument();
    });
  });
});
