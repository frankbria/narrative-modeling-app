/**
 * Tests for the shared StageNavigation footer (issue #88).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { StageNavigation } from '@/components/workflow/StageNavigation';
import { WorkflowStage } from '@/lib/types/workflow';

const goToNextStage = jest.fn();
const goToPreviousStage = jest.fn();

let mockState: {
  completedStages: Set<WorkflowStage>;
  stageData: Record<string, unknown>;
};

jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => ({
    state: mockState,
    goToNextStage,
    goToPreviousStage,
  }),
}));

beforeEach(() => {
  goToNextStage.mockClear();
  goToPreviousStage.mockClear();
  mockState = { completedStages: new Set(), stageData: {} };
});

describe('StageNavigation', () => {
  it('disables Continue and shows a hint when the stage is not complete', () => {
    render(<StageNavigation currentStage={WorkflowStage.DATA_PREPARATION} />);

    const button = screen.getByTestId('continue-button');
    expect(button).toBeDisabled();
    expect(screen.getByTestId('continue-hint')).toHaveTextContent(/complete this step/i);
    expect(button).toHaveTextContent(/Continue to Feature Engineering/i);
  });

  it('enables Continue once the stage is complete and advances on click', () => {
    mockState.completedStages = new Set([WorkflowStage.DATA_PREPARATION]);
    render(<StageNavigation currentStage={WorkflowStage.DATA_PREPARATION} />);

    const button = screen.getByTestId('continue-button');
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(goToNextStage).toHaveBeenCalledTimes(1);
  });

  it('blocks Continue with a validation error when stage data is incomplete', () => {
    // Feature engineering is "complete" but has too few features selected
    mockState.completedStages = new Set([WorkflowStage.FEATURE_ENGINEERING]);
    mockState.stageData = {
      [WorkflowStage.FEATURE_ENGINEERING]: { selectedFeatures: ['only-one'] },
    };
    render(<StageNavigation currentStage={WorkflowStage.FEATURE_ENGINEERING} />);

    expect(screen.getByTestId('continue-button')).toBeDisabled();
    expect(screen.getByTestId('continue-hint')).toHaveTextContent(/at least 2 features/i);
  });

  it('runs onContinue before navigating', async () => {
    mockState.completedStages = new Set([WorkflowStage.DATA_PREPARATION]);
    const onContinue = jest.fn().mockResolvedValue(undefined);
    render(
      <StageNavigation currentStage={WorkflowStage.DATA_PREPARATION} onContinue={onContinue} />
    );

    fireEvent.click(screen.getByTestId('continue-button'));
    await waitFor(() => expect(onContinue).toHaveBeenCalledTimes(1));
    expect(goToNextStage).toHaveBeenCalledTimes(1);
  });

  it('does not navigate if onContinue throws', async () => {
    mockState.completedStages = new Set([WorkflowStage.DATA_PREPARATION]);
    const onContinue = jest.fn().mockRejectedValue(new Error('boom'));
    const errSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <StageNavigation currentStage={WorkflowStage.DATA_PREPARATION} onContinue={onContinue} />
    );

    fireEvent.click(screen.getByTestId('continue-button'));
    await waitFor(() => expect(onContinue).toHaveBeenCalled());
    expect(goToNextStage).not.toHaveBeenCalled();
    errSpy.mockRestore();
  });

  it('navigates back on Back click', () => {
    render(<StageNavigation currentStage={WorkflowStage.DATA_PREPARATION} />);
    fireEvent.click(screen.getByTestId('back-button'));
    expect(goToPreviousStage).toHaveBeenCalledTimes(1);
  });

  it('hides Back on the first stage', () => {
    render(<StageNavigation currentStage={WorkflowStage.DATA_LOADING} />);
    expect(screen.queryByTestId('back-button')).not.toBeInTheDocument();
  });

  it('shows a Finish CTA (not Continue) on the final stage', () => {
    const onFinish = jest.fn();
    render(
      <StageNavigation currentStage={WorkflowStage.DEPLOYMENT} onFinish={onFinish} finishLabel="Done" />
    );

    expect(screen.queryByTestId('continue-button')).not.toBeInTheDocument();
    const finish = screen.getByTestId('finish-button');
    expect(finish).toHaveTextContent('Done');
    fireEvent.click(finish);
    expect(onFinish).toHaveBeenCalledTimes(1);
  });
});
