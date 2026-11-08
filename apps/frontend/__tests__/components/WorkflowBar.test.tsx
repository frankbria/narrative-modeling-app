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

describe('WorkflowBar sheet tabs (#185, design identity)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockWorkflowState();
  });

  it('scrolls only the tab strip: one scroll container holding all stage buttons', () => {
    const { container } = render(<WorkflowBar />);

    const scrollContainers = container.querySelectorAll('.overflow-x-auto');
    expect(scrollContainers).toHaveLength(1);

    const strip = scrollContainers[0] as HTMLElement;
    expect(strip.className).toContain('min-w-0');
    expect(strip.className).toContain('flex-1');
    expect(within(strip).getAllByRole('button')).toHaveLength(WORKFLOW_STAGES.length);

    // The nav itself must not be the scroll container
    const nav = container.querySelector('nav') as HTMLElement;
    expect(nav.className).not.toContain('overflow-x-auto');
  });

  it('names every stage on its tab, not just the current one', () => {
    const { container } = render(<WorkflowBar />);
    const nav = container.querySelector('nav') as HTMLElement;

    WORKFLOW_STAGES.forEach((stage, index) => {
      // Label in name (WCAG 2.5.3): the accessible name begins with the visible tab label.
      const tab = within(nav).getByRole('button', { name: new RegExp(`^(${index + 1} )?${stage.tab} ?, ${stage.name}$`) });
      expect(tab).toHaveAttribute('title', stage.name);
      expect(within(tab).getByText(stage.tab)).toBeInTheDocument();
      // A finished stage shows a check instead of its number.
      if (stage.id !== WorkflowStage.DATA_LOADING) {
        expect(within(tab).getByText(`${index + 1}`)).toBeInTheDocument();
      }
    });
  });

  it('marks the open stage as the current step', () => {
    const { container } = render(<WorkflowBar />);
    const nav = container.querySelector('nav') as HTMLElement;

    expect(within(nav).getByTitle('Data Profiling')).toHaveAttribute('aria-current', 'step');
    expect(within(nav).getByTitle('Data Loading')).not.toHaveAttribute('aria-current');
  });

  it('scrolls the open stage tab into view on a narrow screen', () => {
    const scrollIntoView = jest.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    render(<WorkflowBar />);

    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    expect(scrollIntoView.mock.contexts[0]).toHaveAttribute('title', 'Data Profiling');
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

  it('counts completed stages', () => {
    mockWorkflowState({
      completedStages: new Set([WorkflowStage.DATA_LOADING, WorkflowStage.DATA_PROFILING]),
    });
    render(<WorkflowBar />);

    expect(screen.getByText(`2 of ${WORKFLOW_STAGES.length} stages done`)).toBeInTheDocument();
  });
});
