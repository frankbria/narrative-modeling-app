/**
 * Tests for WorkflowContext stage-transition helpers (issue #88):
 * goToNextStage / goToPreviousStage (route-aware), completeStage auto-advance
 * opt-in, and the guard-message mechanism.
 */

import React from 'react';
import { renderHook, act, waitFor } from '@testing-library/react';
import { WorkflowProvider, useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';

const pushMock = jest.fn();
let mockPathname = '/';
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: jest.fn(), prefetch: jest.fn(), back: jest.fn() }),
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => mockPathname,
}));

const DATASET_ID = 'ds-123';

function wrapper({ children }: { children: React.ReactNode }) {
  return <WorkflowProvider>{children}</WorkflowProvider>;
}

beforeEach(() => {
  localStorage.clear();
  mockPathname = '/';
  pushMock.mockClear();
  (global.fetch as jest.Mock).mockReset();
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    status: 200,
    json: jest.fn().mockResolvedValue({}),
  });
});

describe('completeStage navigation', () => {
  it('does NOT auto-advance by default (explicit Continue CTAs drive transitions)', async () => {
    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      result.current.completeStage(WorkflowStage.DATA_LOADING, { datasetId: DATASET_ID });
    });

    expect(pushMock).not.toHaveBeenCalled();
    expect(result.current.state.completedStages.has(WorkflowStage.DATA_LOADING)).toBe(true);
  });

  it('auto-advances route-aware when opts.autoAdvance is true', async () => {
    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      result.current.completeStage(
        WorkflowStage.DATA_LOADING,
        { datasetId: DATASET_ID },
        { autoAdvance: true }
      );
    });

    // Next stage (data_profiling) is deep-linked with the dataset id
    expect(pushMock).toHaveBeenCalledWith(`/explore/${DATASET_ID}`);
  });
});

describe('goToNextStage / goToPreviousStage', () => {
  it('navigates forward to the next stage (bare route for non-deep-linked stages)', async () => {
    const { result } = renderHook(() => useWorkflow(), { wrapper });

    // Establish the dataset and complete loading + profiling
    await act(async () => {
      result.current.completeStage(WorkflowStage.DATA_LOADING, { datasetId: DATASET_ID });
      result.current.completeStage(WorkflowStage.DATA_PROFILING);
    });

    // currentStage is data_loading (route effect inert at '/'); advance from it
    await act(async () => {
      result.current.goToNextStage();
    });
    expect(pushMock).toHaveBeenLastCalledWith(`/explore/${DATASET_ID}`);
    expect(result.current.state.currentStage).toBe(WorkflowStage.DATA_PROFILING);

    await act(async () => {
      result.current.goToNextStage();
    });
    // data_preparation renders at its bare route
    expect(pushMock).toHaveBeenLastCalledWith('/prepare');
    expect(result.current.state.currentStage).toBe(WorkflowStage.DATA_PREPARATION);
  });

  it('navigates backward without an access check', async () => {
    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      result.current.completeStage(WorkflowStage.DATA_LOADING, { datasetId: DATASET_ID });
    });
    await act(async () => {
      result.current.goToNextStage(); // -> data_profiling
    });
    pushMock.mockClear();

    await act(async () => {
      result.current.goToPreviousStage(); // back to data_loading
    });
    expect(pushMock).toHaveBeenLastCalledWith('/upload');
    expect(result.current.state.currentStage).toBe(WorkflowStage.DATA_LOADING);
  });

  it('does nothing past the last / before the first stage', async () => {
    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      result.current.goToPreviousStage(); // already at data_loading
    });
    expect(pushMock).not.toHaveBeenCalled();
  });
});

describe('guard message', () => {
  it('requestStageRedirect surfaces a message and navigates; clearGuardMessage clears it', async () => {
    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      result.current.completeStage(WorkflowStage.DATA_LOADING, { datasetId: DATASET_ID });
    });
    pushMock.mockClear();

    await act(async () => {
      result.current.requestStageRedirect(
        WorkflowStage.DATA_PROFILING,
        'Complete "Data Profiling" first.'
      );
    });

    expect(result.current.guardMessage).toBe('Complete "Data Profiling" first.');
    expect(pushMock).toHaveBeenCalledWith(`/explore/${DATASET_ID}`);

    await act(async () => {
      result.current.clearGuardMessage();
    });
    expect(result.current.guardMessage).toBeNull();
  });
});
