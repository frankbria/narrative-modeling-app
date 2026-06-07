import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import TransformationNode, {
  TransformationNodeData,
  TransformationFlowNode,
} from '@/components/transformation/TransformationNode';
import { ReactFlowProvider, NodeProps } from '@xyflow/react';

jest.mock('lucide-react', () => ({
  Settings: () => <span data-testid="settings-icon">Settings</span>,
  X: () => <span data-testid="x-icon">X</span>,
}));

const ReactFlowWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <ReactFlowProvider>{children}</ReactFlowProvider>
);

describe('TransformationNode Component', () => {
  const mockOnDelete = jest.fn();
  const mockOnUpdate = jest.fn();

  const createNodeProps = (
    data: Partial<TransformationNodeData> = {}
  ): NodeProps<TransformationFlowNode> => ({
    id: 'transform-node-1',
    data: {
      type: 'fill_missing',
      label: 'Fill Missing Values',
      parameters: {},
      onDelete: mockOnDelete,
      onUpdate: mockOnUpdate,
      ...data,
    },
    selected: false,
    type: 'transformation',
    zIndex: 1,
    isConnectable: true,
    positionAbsoluteX: 0,
    positionAbsoluteY: 0,
    dragging: false,
    selectable: true,
    deletable: true,
    draggable: true,
    width: 200,
    height: 100,
    parentId: undefined,
    dragHandle: undefined,
    targetPosition: undefined,
    sourcePosition: undefined,
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the node label and type', () => {
    const props = createNodeProps({ label: 'One Hot Encode', type: 'one_hot_encode' });

    render(
      <ReactFlowWrapper>
        <TransformationNode {...props} />
      </ReactFlowWrapper>
    );

    expect(screen.getByText('One Hot Encode')).toBeInTheDocument();
    expect(screen.getByText('Type: one_hot_encode')).toBeInTheDocument();
  });

  it('shows the delete button and calls onDelete with the node id when clicked', () => {
    const props = createNodeProps();

    render(
      <ReactFlowWrapper>
        <TransformationNode {...props} />
      </ReactFlowWrapper>
    );

    const deleteButton = screen.getByTestId('x-icon').closest('button');
    fireEvent.click(deleteButton!);

    expect(mockOnDelete).toHaveBeenCalledWith('transform-node-1');
  });

  it('does not render the delete button when onDelete is not provided', () => {
    const props = createNodeProps({ onDelete: undefined });

    render(
      <ReactFlowWrapper>
        <TransformationNode {...props} />
      </ReactFlowWrapper>
    );

    expect(screen.queryByTestId('x-icon')).not.toBeInTheDocument();
    // The settings button (no onDelete guard) is still rendered.
    expect(screen.getByTestId('settings-icon')).toBeInTheDocument();
  });

  it('reveals fill_missing parameter inputs when settings are toggled', () => {
    const props = createNodeProps({ type: 'fill_missing' });

    render(
      <ReactFlowWrapper>
        <TransformationNode {...props} />
      </ReactFlowWrapper>
    );

    const settingsButton = screen.getByTestId('settings-icon').closest('button');
    fireEvent.click(settingsButton!);

    expect(screen.getByText('Columns')).toBeInTheDocument();
  });

  it('propagates parameter changes through onUpdate', () => {
    const props = createNodeProps({ type: 'create_bins', parameters: {} });

    render(
      <ReactFlowWrapper>
        <TransformationNode {...props} />
      </ReactFlowWrapper>
    );

    const settingsButton = screen.getByTestId('settings-icon').closest('button');
    fireEvent.click(settingsButton!);

    const columnInput = screen.getByPlaceholderText('Column name');
    fireEvent.change(columnInput, { target: { value: 'age' } });

    expect(mockOnUpdate).toHaveBeenCalledWith(
      'transform-node-1',
      expect.objectContaining({ parameters: expect.objectContaining({ column: 'age' }) })
    );
  });
});
