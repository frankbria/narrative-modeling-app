/**
 * Tests for the useStageGuard hook (issue #88, AC2).
 */

import { renderHook } from '@testing-library/react';
import { useStageGuard } from '@/lib/hooks/useStageGuard';
import { WorkflowStage } from '@/lib/types/workflow';

const requestStageRedirect = jest.fn();
const canAccessStage = jest.fn();

let mockCtx: {
  isHydrated: boolean;
  state: { completedStages: Set<WorkflowStage> };
};

jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => ({
    state: mockCtx.state,
    isHydrated: mockCtx.isHydrated,
    canAccessStage,
    requestStageRedirect,
  }),
}));

beforeEach(() => {
  requestStageRedirect.mockClear();
  canAccessStage.mockReset();
  mockCtx = { isHydrated: true, state: { completedStages: new Set() } };
});

describe('useStageGuard', () => {
  it('does not redirect before hydration', () => {
    mockCtx.isHydrated = false;
    canAccessStage.mockReturnValue(false);

    const { result } = renderHook(() => useStageGuard(WorkflowStage.MODEL_TRAINING));

    expect(requestStageRedirect).not.toHaveBeenCalled();
    expect(result.current.ready).toBe(false);
  });

  it('redirects a gated stage to the earliest incomplete prerequisite with a message', () => {
    canAccessStage.mockReturnValue(false);
    mockCtx.state.completedStages = new Set([WorkflowStage.DATA_LOADING]);

    const { result } = renderHook(() => useStageGuard(WorkflowStage.MODEL_TRAINING));

    expect(requestStageRedirect).toHaveBeenCalledTimes(1);
    const [target, message] = requestStageRedirect.mock.calls[0];
    expect(target).toBe(WorkflowStage.DATA_PROFILING);
    expect(message).toMatch(/Data Profiling/);
    expect(message).toMatch(/Model Training/);
    expect(result.current.ready).toBe(false);
  });

  it('does not redirect when the stage is accessible', () => {
    canAccessStage.mockReturnValue(true);

    const { result } = renderHook(() => useStageGuard(WorkflowStage.DATA_PROFILING));

    expect(requestStageRedirect).not.toHaveBeenCalled();
    expect(result.current.ready).toBe(true);
  });
});
