/**
 * Direct tests for WorkflowContext.canAccessStage (issue #268).
 *
 * canAccessStage is the workflow access gate: every gated page calls it (via
 * useStageGuard) to decide whether to render or redirect. Previously it was
 * always MOCKED to `true` in page tests and never exercised directly, so a
 * regression in the prerequisite logic would ship with CI green. These tests
 * drive the REAL provider and assert access per stage as prerequisites are met.
 */

import React from 'react';
import { renderHook, act } from '@testing-library/react';
import { WorkflowProvider, useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), prefetch: jest.fn(), back: jest.fn() }),
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/',
}));

const DATASET_ID = 'ds-access-1';

function wrapper({ children }: { children: React.ReactNode }) {
  return <WorkflowProvider>{children}</WorkflowProvider>;
}

beforeEach(() => {
  localStorage.clear();
  // Auto-save fires after the first completed stage; give it a benign backend.
  (global.fetch as jest.Mock).mockReset();
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    status: 200,
    json: jest.fn().mockResolvedValue({}),
  });
});

// The linear prerequisite chain: each stage requires exactly its predecessor.
// [stage, the single prerequisite that must be completed to unlock it]
const CHAIN: Array<[WorkflowStage, WorkflowStage | null]> = [
  [WorkflowStage.DATA_LOADING, null],
  [WorkflowStage.DATA_PROFILING, WorkflowStage.DATA_LOADING],
  [WorkflowStage.DATA_PREPARATION, WorkflowStage.DATA_PROFILING],
  [WorkflowStage.FEATURE_ENGINEERING, WorkflowStage.DATA_PREPARATION],
  [WorkflowStage.MODEL_TRAINING, WorkflowStage.FEATURE_ENGINEERING],
  [WorkflowStage.MODEL_EVALUATION, WorkflowStage.MODEL_TRAINING],
  [WorkflowStage.PREDICTION, WorkflowStage.MODEL_EVALUATION],
  [WorkflowStage.DEPLOYMENT, WorkflowStage.PREDICTION],
];

describe('canAccessStage', () => {
  it('allows the first stage (DATA_LOADING) with no prerequisites', () => {
    const { result } = renderHook(() => useWorkflow(), { wrapper });
    expect(result.current.canAccessStage(WorkflowStage.DATA_LOADING)).toBe(true);
  });

  it('blocks every downstream stage before any prerequisite is completed', () => {
    const { result } = renderHook(() => useWorkflow(), { wrapper });
    for (const [stage, prereq] of CHAIN) {
      // Only the prerequisite-free first stage is reachable from an empty state.
      expect(result.current.canAccessStage(stage)).toBe(prereq === null);
    }
  });

  it.each(CHAIN.filter(([, prereq]) => prereq !== null))(
    'unlocks %s only once its prerequisite is completed',
    async (stage, prereq) => {
      const { result } = renderHook(() => useWorkflow(), { wrapper });

      // Locked before the prerequisite is completed.
      expect(result.current.canAccessStage(stage)).toBe(false);

      await act(async () => {
        // DATA_LOADING must carry a datasetId; other completions need no data.
        result.current.completeStage(
          prereq as WorkflowStage,
          prereq === WorkflowStage.DATA_LOADING ? { datasetId: DATASET_ID } : undefined
        );
      });

      // Unlocked once the immediate prerequisite is completed.
      expect(result.current.canAccessStage(stage)).toBe(true);
    }
  );

  it('completing DATA_LOADING unlocks PROFILING but NOT PREPARATION (only the immediate prerequisite)', async () => {
    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      result.current.completeStage(WorkflowStage.DATA_LOADING, { datasetId: DATASET_ID });
    });

    expect(result.current.canAccessStage(WorkflowStage.DATA_PROFILING)).toBe(true);
    // PREPARATION requires PROFILING, which is not yet complete.
    expect(result.current.canAccessStage(WorkflowStage.DATA_PREPARATION)).toBe(false);
  });

  it('grants access to the full chain once every stage is completed in order', async () => {
    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      for (const [stage] of CHAIN) {
        result.current.completeStage(
          stage,
          stage === WorkflowStage.DATA_LOADING ? { datasetId: DATASET_ID } : undefined
        );
      }
    });

    for (const [stage] of CHAIN) {
      expect(result.current.canAccessStage(stage)).toBe(true);
    }
  });

  it('returns false for an unknown stage id', () => {
    const { result } = renderHook(() => useWorkflow(), { wrapper });
    expect(result.current.canAccessStage('nonexistent_stage' as WorkflowStage)).toBe(false);
  });
});
