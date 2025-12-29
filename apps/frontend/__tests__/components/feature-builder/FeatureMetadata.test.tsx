import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import FeatureMetadata from '@/components/feature-builder/FeatureMetadata';

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  X: () => <span data-testid="x-icon">X</span>,
  Tag: () => <span data-testid="tag-icon">Tag</span>,
  Plus: () => <span data-testid="plus-icon">Plus</span>,
}));

describe('FeatureMetadata Component', () => {
  const mockProps = {
    name: 'price_per_unit',
    description: 'Price divided by quantity',
    tags: ['pricing', 'calculated'],
    onNameChange: jest.fn(),
    onDescriptionChange: jest.fn(),
    onTagsChange: jest.fn(),
    onSave: jest.fn(),
    onClose: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render modal with title', () => {
      render(<FeatureMetadata {...mockProps} />);

      expect(screen.getByText('Feature Details')).toBeInTheDocument();
    });

    it('should render name input with current value', () => {
      render(<FeatureMetadata {...mockProps} />);

      const nameInput = screen.getByPlaceholderText('e.g., price_per_sqft');
      expect(nameInput).toHaveValue('price_per_unit');
    });

    it('should render description textarea with current value', () => {
      render(<FeatureMetadata {...mockProps} />);

      const descriptionInput = screen.getByPlaceholderText('Describe what this feature represents...');
      expect(descriptionInput).toHaveValue('Price divided by quantity');
    });

    it('should render existing tags', () => {
      render(<FeatureMetadata {...mockProps} />);

      expect(screen.getByText('pricing')).toBeInTheDocument();
      expect(screen.getByText('calculated')).toBeInTheDocument();
    });

    it('should render close button in header', () => {
      render(<FeatureMetadata {...mockProps} />);

      const closeButtons = screen.getAllByTestId('x-icon');
      expect(closeButtons.length).toBeGreaterThan(0);
    });

    it('should render Save and Cancel buttons', () => {
      render(<FeatureMetadata {...mockProps} />);

      expect(screen.getByText('Save Feature')).toBeInTheDocument();
      expect(screen.getByText('Cancel')).toBeInTheDocument();
    });
  });

  describe('Name Input', () => {
    it('should call onNameChange when name is changed', () => {
      render(<FeatureMetadata {...mockProps} />);

      const nameInput = screen.getByPlaceholderText('e.g., price_per_sqft');
      fireEvent.change(nameInput, { target: { value: 'new_feature_name' } });

      expect(mockProps.onNameChange).toHaveBeenCalledWith('new_feature_name');
    });

    it('should show required indicator for name', () => {
      render(<FeatureMetadata {...mockProps} />);

      expect(screen.getByText('Feature Name')).toBeInTheDocument();
      expect(screen.getByText('*')).toBeInTheDocument();
    });

    it('should show helper text for name', () => {
      render(<FeatureMetadata {...mockProps} />);

      expect(screen.getByText('Use descriptive names without spaces (use underscores)')).toBeInTheDocument();
    });
  });

  describe('Description Input', () => {
    it('should call onDescriptionChange when description is changed', () => {
      render(<FeatureMetadata {...mockProps} />);

      const descriptionInput = screen.getByPlaceholderText('Describe what this feature represents...');
      fireEvent.change(descriptionInput, { target: { value: 'New description' } });

      expect(mockProps.onDescriptionChange).toHaveBeenCalledWith('New description');
    });
  });

  describe('Tags Functionality', () => {
    it('should render tag input', () => {
      render(<FeatureMetadata {...mockProps} />);

      expect(screen.getByPlaceholderText('Add a tag...')).toBeInTheDocument();
    });

    it('should add new tag when Add button clicked', () => {
      render(<FeatureMetadata {...mockProps} />);

      const tagInput = screen.getByPlaceholderText('Add a tag...');
      fireEvent.change(tagInput, { target: { value: 'new-tag' } });

      const addButton = screen.getByTestId('plus-icon').closest('button');
      fireEvent.click(addButton!);

      expect(mockProps.onTagsChange).toHaveBeenCalledWith(['pricing', 'calculated', 'new-tag']);
    });

    it('should add new tag when Enter pressed', () => {
      render(<FeatureMetadata {...mockProps} />);

      const tagInput = screen.getByPlaceholderText('Add a tag...');
      fireEvent.change(tagInput, { target: { value: 'keyboard-tag' } });
      fireEvent.keyDown(tagInput, { key: 'Enter', code: 'Enter' });

      expect(mockProps.onTagsChange).toHaveBeenCalledWith(['pricing', 'calculated', 'keyboard-tag']);
    });

    it('should not add duplicate tags', () => {
      render(<FeatureMetadata {...mockProps} />);

      const tagInput = screen.getByPlaceholderText('Add a tag...');
      fireEvent.change(tagInput, { target: { value: 'pricing' } });
      fireEvent.keyDown(tagInput, { key: 'Enter', code: 'Enter' });

      expect(mockProps.onTagsChange).not.toHaveBeenCalled();
    });

    it('should not add empty tags', () => {
      render(<FeatureMetadata {...mockProps} />);

      const tagInput = screen.getByPlaceholderText('Add a tag...');
      fireEvent.change(tagInput, { target: { value: '   ' } });
      fireEvent.keyDown(tagInput, { key: 'Enter', code: 'Enter' });

      expect(mockProps.onTagsChange).not.toHaveBeenCalled();
    });

    it('should trim whitespace from tags', () => {
      render(<FeatureMetadata {...mockProps} />);

      const tagInput = screen.getByPlaceholderText('Add a tag...');
      fireEvent.change(tagInput, { target: { value: '  trimmed-tag  ' } });
      fireEvent.keyDown(tagInput, { key: 'Enter', code: 'Enter' });

      expect(mockProps.onTagsChange).toHaveBeenCalledWith(['pricing', 'calculated', 'trimmed-tag']);
    });

    it('should remove tag when X button clicked', () => {
      render(<FeatureMetadata {...mockProps} />);

      // Find the remove button for the "pricing" tag
      const pricingTag = screen.getByText('pricing').closest('span');
      const removeButton = pricingTag?.querySelector('button');
      fireEvent.click(removeButton!);

      expect(mockProps.onTagsChange).toHaveBeenCalledWith(['calculated']);
    });

    it('should disable add button when input is empty', () => {
      render(<FeatureMetadata {...mockProps} />);

      const addButton = screen.getByTestId('plus-icon').closest('button');
      expect(addButton).toBeDisabled();
    });

    it('should show helper text for tags', () => {
      render(<FeatureMetadata {...mockProps} />);

      expect(screen.getByText('Press Enter or click + to add a tag')).toBeInTheDocument();
    });

    it('should display tag icons', () => {
      render(<FeatureMetadata {...mockProps} />);

      // Each tag should have a tag icon
      const tagIcons = screen.getAllByTestId('tag-icon');
      expect(tagIcons.length).toBe(2); // pricing and calculated
    });
  });

  describe('Save Functionality', () => {
    it('should call onSave when Save button clicked', () => {
      render(<FeatureMetadata {...mockProps} />);

      const saveButton = screen.getByText('Save Feature');
      fireEvent.click(saveButton);

      expect(mockProps.onSave).toHaveBeenCalled();
    });

    it('should disable Save button when name is empty', () => {
      render(<FeatureMetadata {...mockProps} name="" />);

      const saveButton = screen.getByText('Save Feature');
      expect(saveButton).toBeDisabled();
    });

    it('should disable Save button when name is only whitespace', () => {
      render(<FeatureMetadata {...mockProps} name="   " />);

      const saveButton = screen.getByText('Save Feature');
      expect(saveButton).toBeDisabled();
    });

    it('should enable Save button when name is valid', () => {
      render(<FeatureMetadata {...mockProps} name="valid_name" />);

      const saveButton = screen.getByText('Save Feature');
      expect(saveButton).not.toBeDisabled();
    });
  });

  describe('Close Functionality', () => {
    it('should call onClose when Cancel button clicked', () => {
      render(<FeatureMetadata {...mockProps} />);

      const cancelButton = screen.getByText('Cancel');
      fireEvent.click(cancelButton);

      expect(mockProps.onClose).toHaveBeenCalled();
    });

    it('should call onClose when header X button clicked', () => {
      render(<FeatureMetadata {...mockProps} />);

      // The first X icon is in the header
      const closeButton = screen.getAllByTestId('x-icon')[0].closest('button');
      fireEvent.click(closeButton!);

      expect(mockProps.onClose).toHaveBeenCalled();
    });
  });

  describe('Modal Styling', () => {
    it('should have overlay background', () => {
      const { container } = render(<FeatureMetadata {...mockProps} />);

      const overlay = container.firstChild;
      expect(overlay).toHaveClass('fixed');
      expect(overlay).toHaveClass('inset-0');
      expect(overlay).toHaveClass('bg-black/50');
    });

    it('should have centered modal dialog', () => {
      const { container } = render(<FeatureMetadata {...mockProps} />);

      const overlay = container.firstChild;
      expect(overlay).toHaveClass('flex');
      expect(overlay).toHaveClass('items-center');
      expect(overlay).toHaveClass('justify-center');
    });
  });

  describe('Empty Tags', () => {
    it('should render correctly with no tags', () => {
      render(<FeatureMetadata {...mockProps} tags={[]} />);

      // Should not show any tag chips
      expect(screen.queryByTestId('tag-icon')).not.toBeInTheDocument();

      // But should still show tag input
      expect(screen.getByPlaceholderText('Add a tag...')).toBeInTheDocument();
    });
  });
});
