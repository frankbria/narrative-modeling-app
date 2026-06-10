import React from 'react';
import { render, screen, within, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { WorkflowBar } from '@/components/WorkflowBar';
import { WorkflowStage, WORKFLOW_STAGES } from '@/lib/types/workflow';

jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: jest.fn(),
}));

import { useWorkflow } from '@/lib/contexts/WorkflowContext';

const mockSetCurrentStage = jest.fn();

function mockWorkflowState({
  currentStage = WorkflowStage.DATA_PROFILING,
  completedStages = new Set([WorkflowStage.DATA_LOADING]),
  accessibleStages = [
    WorkflowStage.DATA_LOADING,
    WorkflowStage.DATA_PROFILING,
    WorkflowStage.DATA_PREPARATION,
  ],
} = {}) {
  (useWorkflow as jest.Mock).mockReturnValue({
    state: {
      currentStage,
      completedStages,
      stageData: {},
    },
    canAccessStage: (stage: WorkflowStage) => accessibleStages.includes(stage),
    setCurrentStage: mockSetCurrentStage,
  });
}

describe('WorkflowBar layout (issue #185)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockWorkflowState();
  });

  it('keeps the progress indicator outside the scroll container, pinned as a nav sibling', () => {
    const { container } = render(<WorkflowBar />);

    const progressLabel = screen.getByText('Progress:');
    const progressIndicator = progressLabel.parentElement as HTMLElement;

    // The progress indicator must never live inside a scrollable region
    expect(progressLabel.closest('.overflow-x-auto')).toBeNull();
    // ...and must resist flex compression
    expect(progressIndicator.className).toContain('shrink-0');

    // The nav itself must not be the scroll container
    const nav = container.querySelector('nav') as HTMLElement;
    expect(nav.className).not.toContain('overflow-x-auto');
  });

  it('scrolls only the stage strip: one scroll container holding all stage buttons', () => {
    const { container } = render(<WorkflowBar />);

    const scrollContainers = container.querySelectorAll('.overflow-x-auto');
    expect(scrollContainers).toHaveLength(1);

    const strip = scrollContainers[0] as HTMLElement;
    // Strip must be able to shrink inside the flex row
    expect(strip.className).toContain('min-w-0');
    expect(strip.className).toContain('flex-1');

    // All 8 stage buttons live inside the strip
    const buttons = within(strip).getAllByRole('button');
    expect(buttons).toHaveLength(WORKFLOW_STAGES.length);
  });

  it('uses slim connectors instead of the w-8/sm:w-12 lines that forced overflow', () => {
    const { container } = render(<WorkflowBar />);

    expect(container.querySelector('.w-8')).toBeNull();
    expect(container.querySelector('.sm\\:w-12')).toBeNull();

    // ...and the slim connectors actually exist (one per gap between 8 stages)
    expect(container.querySelectorAll('.w-2.sm\\:w-3')).toHaveLength(WORKFLOW_STAGES.length - 1);
  });

  it('shows the full name only on the current stage; other stages show number with a title tooltip', () => {
    const { container } = render(<WorkflowBar />);
    const nav = container.querySelector('nav') as HTMLElement;

    // Current stage shows its full name
    const currentButton = within(nav).getByTitle('Data Profiling');
    expect(within(currentButton).getByText('Data Profiling')).toBeInTheDocument();

    // Non-current stages show their number, not their name, but keep a title tooltip
    const firstButton = within(nav).getByTitle('Data Loading');
    expect(within(firstButton).queryByText('Data Loading')).toBeNull();
    expect(within(firstButton).getByText('1')).toBeInTheDocument();

    // Every stage stays identifiable via its title attribute and accessible name
    WORKFLOW_STAGES.forEach(stage => {
      expect(within(nav).getByTitle(stage.name)).toBeInTheDocument();
      expect(within(nav).getByRole('button', { name: stage.name })).toBeInTheDocument();
    });
  });

  it('preserves click-through on accessible stages', () => {
    const { container } = render(<WorkflowBar />);
    const nav = container.querySelector('nav') as HTMLElement;

    fireEvent.click(within(nav).getByTitle('Data Loading'));
    expect(mockSetCurrentStage).toHaveBeenCalledWith(WorkflowStage.DATA_LOADING);
  });

  it('preserves disabled behavior on inaccessible stages', () => {
    const { container } = render(<WorkflowBar />);
    const nav = container.querySelector('nav') as HTMLElement;

    const lockedButton = within(nav).getByTitle('Model Training');
    expect(lockedButton).toBeDisabled();

    fireEvent.click(lockedButton);
    expect(mockSetCurrentStage).not.toHaveBeenCalled();
  });

  it('renders the progress count from completed stages', () => {
    mockWorkflowState({
      completedStages: new Set([WorkflowStage.DATA_LOADING, WorkflowStage.DATA_PROFILING]),
    });
    const { container } = render(<WorkflowBar />);
    const nav = container.querySelector('nav') as HTMLElement;

    const progress = screen.getByText('Progress:').parentElement as HTMLElement;
    expect(within(progress).getByText('2')).toBeInTheDocument();
    expect(within(progress).getByText(`${WORKFLOW_STAGES.length}`)).toBeInTheDocument();
    expect(nav).toContainElement(progress);
  });
});
