/**
 * Tests for WorkflowContext backend persistence (issue #87).
 *
 * Covers: loadWorkflow (backend hydration, 404 + network-error localStorage
 * fallback), saveWorkflow (POST create, PUT update, 409 retry), and auto-save
 * at stage boundaries via completeStage.
 */

import React from 'react';
import { renderHook, act, waitFor } from '@testing-library/react';
import { WorkflowProvider, useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { API_URL } from '@/lib/constants';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), prefetch: jest.fn(), back: jest.fn() }),
  useParams: () => ({ id: 'test-dataset-id' }),
  useSearchParams: () => new URLSearchParams(),
  // '/' matches no stage route, so the route-sync effect never overrides
  // the currentStage restored from the backend in these tests
  usePathname: () => '/',
}));

const DATASET_ID = 'ds-123';

const backendState = {
  workflow_id: 'wf-1',
  dataset_id: DATASET_ID,
  current_stage: 'data_preparation',
  completed_stages: ['data_loading', 'data_profiling'],
  stage_data: { data_loading: { datasetId: DATASET_ID } },
  model_id: null,
  deployment_id: null,
  created_at: '2026-06-12T00:00:00Z',
  updated_at: '2026-06-12T00:00:00Z',
};

function mockFetchResponse(status: number, body: unknown = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: jest.fn().mockResolvedValue(body),
  };
}

function wrapper({ children }: { children: React.ReactNode }) {
  return <WorkflowProvider>{children}</WorkflowProvider>;
}

function workflowCalls() {
  return (global.fetch as jest.Mock).mock.calls.filter(([url]) =>
    String(url).includes('/workflows/')
  );
}

beforeEach(() => {
  localStorage.clear();
  (global.fetch as jest.Mock).mockReset();
});

describe('loadWorkflow', () => {
  it('hydrates state from the backend and refreshes the localStorage cache', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(mockFetchResponse(200, backendState));

    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      await result.current.loadWorkflow(DATASET_ID);
    });

    const [url, init] = workflowCalls()[0];
    expect(url).toBe(`${API_URL}/workflows/${DATASET_ID}`);
    expect(init.headers.Authorization).toBe('Bearer mock-token');

    expect(result.current.state.currentStage).toBe(WorkflowStage.DATA_PREPARATION);
    expect(result.current.state.completedStages.has(WorkflowStage.DATA_LOADING)).toBe(true);
    expect(result.current.state.completedStages.has(WorkflowStage.DATA_PROFILING)).toBe(true);
    expect(result.current.state.datasetId).toBe(DATASET_ID);

    // localStorage cache refreshed to match backend
    await waitFor(() => {
      const cached = JSON.parse(localStorage.getItem('workflowState') as string);
      expect(cached.currentStage).toBe('data_preparation');
      expect(cached.completedStages).toEqual(
        expect.arrayContaining(['data_loading', 'data_profiling'])
      );
    });
  });

  it('falls back to localStorage state when the backend returns 404', async () => {
    localStorage.setItem(
      'workflowState',
      JSON.stringify({
        currentStage: 'data_profiling',
        completedStages: ['data_loading'],
        stageData: {},
        datasetId: DATASET_ID,
        lastUpdated: new Date().toISOString(),
      })
    );
    (global.fetch as jest.Mock).mockResolvedValue(mockFetchResponse(404, { detail: 'not found' }));

    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      await result.current.loadWorkflow(DATASET_ID);
    });

    expect(result.current.state.completedStages.has(WorkflowStage.DATA_LOADING)).toBe(true);
    expect(result.current.state.datasetId).toBe(DATASET_ID);
  });

  it('falls back to localStorage state on network error', async () => {
    localStorage.setItem(
      'workflowState',
      JSON.stringify({
        currentStage: 'data_profiling',
        completedStages: ['data_loading'],
        stageData: {},
        datasetId: DATASET_ID,
        lastUpdated: new Date().toISOString(),
      })
    );
    (global.fetch as jest.Mock).mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      await result.current.loadWorkflow(DATASET_ID);
    });

    expect(result.current.state.completedStages.has(WorkflowStage.DATA_LOADING)).toBe(true);
    expect(result.current.state.datasetId).toBe(DATASET_ID);
  });

  it('ignores stale localStorage state belonging to a different dataset', async () => {
    localStorage.setItem(
      'workflowState',
      JSON.stringify({
        currentStage: 'model_training',
        completedStages: ['data_loading', 'data_profiling', 'data_preparation'],
        stageData: {},
        datasetId: 'some-other-dataset',
        lastUpdated: new Date().toISOString(),
      })
    );
    (global.fetch as jest.Mock).mockResolvedValue(mockFetchResponse(404, { detail: 'not found' }));

    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      await result.current.loadWorkflow(DATASET_ID);
    });

    expect(result.current.state.completedStages.size).toBe(0);
    expect(result.current.state.datasetId).toBe(DATASET_ID);
  });
});

describe('saveWorkflow', () => {
  it('POSTs on first save and PUTs once the workflow exists', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(mockFetchResponse(201, backendState));

    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      result.current.completeStage(WorkflowStage.DATA_LOADING, { datasetId: DATASET_ID });
    });

    await waitFor(() => expect(workflowCalls().length).toBeGreaterThanOrEqual(1));
    const [firstUrl, firstInit] = workflowCalls()[0];
    expect(firstUrl).toBe(`${API_URL}/workflows/${DATASET_ID}`);
    expect(firstInit.method).toBe('POST');

    const firstBody = JSON.parse(firstInit.body);
    expect(firstBody.current_stage).toBeDefined();
    expect(firstBody.completed_stages).toContain('data_loading');
    expect(firstBody.stage_data).toBeDefined();

    // Second boundary: workflow now exists -> PUT
    await act(async () => {
      result.current.completeStage(WorkflowStage.DATA_PROFILING);
    });

    await waitFor(() => {
      const methods = workflowCalls().map(([, init]) => init.method);
      expect(methods).toContain('PUT');
    });
  });

  it('retries with PUT when POST returns 409 (workflow already exists)', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(mockFetchResponse(409, { detail: 'exists' }))
      .mockResolvedValue(mockFetchResponse(200, backendState));

    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      result.current.completeStage(WorkflowStage.DATA_LOADING, { datasetId: DATASET_ID });
    });

    await waitFor(() => {
      const methods = workflowCalls().map(([, init]) => init.method);
      expect(methods).toEqual(['POST', 'PUT']);
    });
  });

  it('keeps state in localStorage when the backend save fails', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      result.current.completeStage(WorkflowStage.DATA_LOADING, { datasetId: DATASET_ID });
    });

    await waitFor(() => {
      const cached = JSON.parse(localStorage.getItem('workflowState') as string);
      expect(cached.completedStages).toContain('data_loading');
      expect(cached.datasetId).toBe(DATASET_ID);
    });
  });

  it('persists a current-stage change so refresh restores the right stage', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(mockFetchResponse(201, backendState));

    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      result.current.completeStage(WorkflowStage.DATA_LOADING, { datasetId: DATASET_ID });
    });
    await waitFor(() => expect(workflowCalls().length).toBe(1));

    // User navigates into the next stage (no completion yet) — must still save
    await act(async () => {
      result.current.setCurrentStage(WorkflowStage.DATA_PROFILING);
    });

    await waitFor(() => {
      const saves = workflowCalls();
      expect(saves.length).toBe(2);
      const [, init] = saves[1];
      expect(init.method).toBe('PUT');
      expect(JSON.parse(init.body).current_stage).toBe('data_profiling');
    });
  });

  it('does not re-save unchanged state (no redundant history versions)', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(mockFetchResponse(201, backendState));

    const { result } = renderHook(() => useWorkflow(), { wrapper });

    await act(async () => {
      result.current.completeStage(WorkflowStage.DATA_LOADING, { datasetId: DATASET_ID });
    });
    await waitFor(() => expect(workflowCalls().length).toBe(1));

    // Explicit save with identical state is a no-op
    await act(async () => {
      await result.current.saveWorkflow();
    });

    expect(workflowCalls().length).toBe(1);
  });
});

describe('recovery on mount', () => {
  it('loads backend state on mount when initialDatasetId is provided', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(mockFetchResponse(200, backendState));

    const mountWrapper = ({ children }: { children: React.ReactNode }) => (
      <WorkflowProvider initialDatasetId={DATASET_ID}>{children}</WorkflowProvider>
    );
    const { result } = renderHook(() => useWorkflow(), { wrapper: mountWrapper });

    await waitFor(() => expect(result.current.isHydrated).toBe(true));
    expect(result.current.state.currentStage).toBe(WorkflowStage.DATA_PREPARATION);
    expect(result.current.state.completedStages.has(WorkflowStage.DATA_PROFILING)).toBe(true);
  });
});
