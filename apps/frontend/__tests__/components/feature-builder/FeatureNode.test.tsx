import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import FeatureNode, { FeatureNodeData } from '@/components/feature-builder/FeatureNode';
import { ReactFlowProvider } from '@xyflow/react';

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  Settings: () => <span data-testid="settings-icon">Settings</span>,
  X: () => <span data-testid="x-icon">X</span>,
  AlertCircle: () => <span data-testid="alert-icon">Alert</span>,
}));

// Wrapper component for ReactFlow context
const ReactFlowWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <ReactFlowProvider>{children}</ReactFlowProvider>
);

describe('FeatureNode Component', () => {
  const mockOnDelete = jest.fn();
  const mockOnUpdate = jest.fn();

  const createNodeProps = (data: Partial<FeatureNodeData> = {}) => ({
    id: 'test-node-1',
    data: {
      nodeType: 'column' as const,
      value: 'test_column',
      label: 'Test Column',
      parameters: {},
      onDelete: mockOnDelete,
      onUpdate: mockOnUpdate,
      ...data,
    },
    selected: false,
    type: 'featureNode',
    zIndex: 1,
    isConnectable: true,
    positionAbsoluteX: 0,
    positionAbsoluteY: 0,
    dragging: false,
    targetPosition: undefined,
    sourcePosition: undefined,
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Column Node', () => {
    it('should render column node with correct value', () => {
      const props = createNodeProps({
        nodeType: 'column',
        value: 'price',
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByText('[price]')).toBeInTheDocument();
      expect(screen.getByText('column')).toBeInTheDocument();
    });

    it('should display column type indicator', () => {
      const props = createNodeProps({
        nodeType: 'column',
        value: 'quantity',
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByText('column')).toBeInTheDocument();
    });
  });

  describe('Operation Node', () => {
    it('should render add operation with + symbol', () => {
      const props = createNodeProps({
        nodeType: 'operation',
        value: 'add',
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByText('+')).toBeInTheDocument();
    });

    it('should render subtract operation with - symbol', () => {
      const props = createNodeProps({
        nodeType: 'operation',
        value: 'subtract',
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByText('-')).toBeInTheDocument();
    });

    it('should render multiply operation with * symbol', () => {
      const props = createNodeProps({
        nodeType: 'operation',
        value: 'multiply',
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByText('*')).toBeInTheDocument();
    });

    it('should render divide operation with / symbol', () => {
      const props = createNodeProps({
        nodeType: 'operation',
        value: 'divide',
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByText('/')).toBeInTheDocument();
    });

    it('should render logical AND operation', () => {
      const props = createNodeProps({
        nodeType: 'operation',
        value: 'and',
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByText('AND')).toBeInTheDocument();
    });
  });

  describe('Function Node', () => {
    it('should render function node with parentheses', () => {
      const props = createNodeProps({
        nodeType: 'function',
        value: 'sqrt',
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByText('sqrt()')).toBeInTheDocument();
    });

    it('should show settings button for function nodes', () => {
      const props = createNodeProps({
        nodeType: 'function',
        value: 'round',
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByTestId('settings-icon')).toBeInTheDocument();
    });

    it('should show decimals parameter for round function when settings opened', () => {
      const props = createNodeProps({
        nodeType: 'function',
        value: 'round',
        parameters: { decimals: 2 },
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      // Click settings button
      const settingsButton = screen.getByTestId('settings-icon').closest('button');
      fireEvent.click(settingsButton!);

      expect(screen.getByText('Decimals')).toBeInTheDocument();
    });

    it('should show fill_value parameter for fill_null function', () => {
      const props = createNodeProps({
        nodeType: 'function',
        value: 'fill_null',
        parameters: { fill_value: '0' },
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      // Click settings button
      const settingsButton = screen.getByTestId('settings-icon').closest('button');
      fireEvent.click(settingsButton!);

      expect(screen.getByText('Fill Value')).toBeInTheDocument();
    });
  });

  describe('Constant Node', () => {
    it('should render constant node with value', () => {
      const props = createNodeProps({
        nodeType: 'constant',
        value: 42,
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByText('42')).toBeInTheDocument();
    });

    it('should show settings button for constant nodes', () => {
      const props = createNodeProps({
        nodeType: 'constant',
        value: 10,
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByTestId('settings-icon')).toBeInTheDocument();
    });

    it('should show editable input when settings clicked', () => {
      const props = createNodeProps({
        nodeType: 'constant',
        value: 10,
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      // Click settings button
      const settingsButton = screen.getByTestId('settings-icon').closest('button');
      fireEvent.click(settingsButton!);

      const input = screen.getByRole('spinbutton');
      expect(input).toBeInTheDocument();
      expect(input).toHaveValue(10);
    });

    it('should update value when input changes', () => {
      const props = createNodeProps({
        nodeType: 'constant',
        value: 10,
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      // Click settings button to show input
      const settingsButton = screen.getByTestId('settings-icon').closest('button');
      fireEvent.click(settingsButton!);

      const input = screen.getByRole('spinbutton');
      fireEvent.change(input, { target: { value: '25' } });

      expect(mockOnUpdate).toHaveBeenCalledWith('test-node-1', { value: 25 });
    });
  });

  describe('Conditional Node', () => {
    it('should render conditional node with IF-THEN-ELSE text', () => {
      const props = createNodeProps({
        nodeType: 'conditional',
        value: null,
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByText('IF-THEN-ELSE')).toBeInTheDocument();
    });
  });

  describe('Delete Functionality', () => {
    it('should show delete button when onDelete is provided', () => {
      const props = createNodeProps();

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByTestId('x-icon')).toBeInTheDocument();
    });

    it('should call onDelete when delete button clicked', () => {
      const props = createNodeProps();

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      const deleteButton = screen.getByTestId('x-icon').closest('button');
      fireEvent.click(deleteButton!);

      expect(mockOnDelete).toHaveBeenCalledWith('test-node-1');
    });

    it('should not show delete button when onDelete is not provided', () => {
      const props = createNodeProps({ onDelete: undefined });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.queryByTestId('x-icon')).not.toBeInTheDocument();
    });
  });

  describe('Error Display', () => {
    it('should show error message when error is provided', () => {
      const props = createNodeProps({
        error: 'Invalid column reference',
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.getByText('Invalid column reference')).toBeInTheDocument();
      expect(screen.getByTestId('alert-icon')).toBeInTheDocument();
    });

    it('should not show error section when no error', () => {
      const props = createNodeProps({
        error: undefined,
      });

      render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(screen.queryByTestId('alert-icon')).not.toBeInTheDocument();
    });
  });

  describe('Selection State', () => {
    it('should apply selection styling when selected', () => {
      const props = { ...createNodeProps(), selected: true };

      const { container } = render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      const nodeElement = container.querySelector('.border-blue-500');
      expect(nodeElement).toBeInTheDocument();
    });
  });

  describe('Node Colors', () => {
    it('should have blue styling for column nodes', () => {
      const props = createNodeProps({
        nodeType: 'column',
      });

      const { container } = render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(container.querySelector('.bg-blue-50')).toBeInTheDocument();
    });

    it('should have green styling for operation nodes', () => {
      const props = createNodeProps({
        nodeType: 'operation',
        value: 'add',
      });

      const { container } = render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(container.querySelector('.bg-green-50')).toBeInTheDocument();
    });

    it('should have orange styling for function nodes', () => {
      const props = createNodeProps({
        nodeType: 'function',
        value: 'sqrt',
      });

      const { container } = render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(container.querySelector('.bg-orange-50')).toBeInTheDocument();
    });

    it('should have purple styling for constant nodes', () => {
      const props = createNodeProps({
        nodeType: 'constant',
        value: 100,
      });

      const { container } = render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(container.querySelector('.bg-purple-50')).toBeInTheDocument();
    });

    it('should have yellow styling for conditional nodes', () => {
      const props = createNodeProps({
        nodeType: 'conditional',
      });

      const { container } = render(
        <ReactFlowWrapper>
          <FeatureNode {...props} />
        </ReactFlowWrapper>
      );

      expect(container.querySelector('.bg-yellow-50')).toBeInTheDocument();
    });
  });
});
