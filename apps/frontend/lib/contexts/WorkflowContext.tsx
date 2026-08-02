'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { WorkflowState, WorkflowStage, WorkflowContextType, WORKFLOW_STAGES } from '@/lib/types/workflow';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { buildStageUrl, getNextStage, getPreviousStage } from '@/lib/utils/stageValidation';

const initialState: WorkflowState = {
  currentStage: WorkflowStage.DATA_LOADING,
  completedStages: new Set<WorkflowStage>(),
  stageData: {} as Record<WorkflowStage, unknown>,
};

// Shape of the state cached in localStorage (Set serialized as array)
type CachedWorkflowState = Omit<WorkflowState, 'completedStages'> & {
  completedStages: WorkflowStage[];
  lastUpdated?: string;
};

// Read the localStorage cache, discarding entries older than 24 hours
function readLocalState(): CachedWorkflowState | null {
  const savedState = localStorage.getItem('workflowState');
  if (!savedState) return null;
  try {
    const parsed = JSON.parse(savedState) as CachedWorkflowState;
    const stateAge = parsed.lastUpdated ? Date.now() - new Date(parsed.lastUpdated).getTime() : Infinity;
    const oneDayMs = 24 * 60 * 60 * 1000;
    if (stateAge < oneDayMs) {
      return parsed;
    }
    localStorage.removeItem('workflowState');
  } catch (e) {
    console.error('Failed to load workflow state:', e);
    localStorage.removeItem('workflowState');
  }
  return null;
}

// Map frontend state to the backend WorkflowCreateRequest/WorkflowUpdateRequest shape
function buildSavePayload(state: WorkflowState) {
  return {
    current_stage: state.currentStage,
    completed_stages: Array.from(state.completedStages),
    stage_data: state.stageData,
    model_id: state.modelId ?? null,
    deployment_id: state.deploymentId ?? null,
  };
}

const WorkflowContext = createContext<WorkflowContextType | undefined>(undefined);

export function WorkflowProvider({ 
  children,
  initialDatasetId
}: { 
  children: React.ReactNode;
  initialDatasetId?: string;
}) {
  const [state, setState] = useState<WorkflowState>({
    ...initialState,
    datasetId: initialDatasetId
  });
  // Pages must not run stage-gating redirects until state is restored:
  // consumer effects fire before this provider's hydration effect, so an
  // early canAccessStage() check always sees an empty completedStages set.
  const [isHydrated, setIsHydrated] = useState(false);
  // Helpful message shown by StageGuardBanner when a guard redirects the user.
  const [guardMessage, setGuardMessage] = useState<string | null>(null);
  // Whether a backend workflow document exists for the current dataset
  // (decides POST vs PUT on save).
  const workflowExistsRef = useRef(false);
  // Signature of the last state persisted to (or loaded from) the backend,
  // so reloads and re-renders don't append redundant history versions.
  const lastSavedRef = useRef<string | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  const loadWorkflow = useCallback(async (datasetId: string) => {
    setState(prev => ({ ...prev, datasetId }));

    // Offline fallback: restore the localStorage cache if it belongs to this dataset
    const restoreFromLocal = (): boolean => {
      const localState = readLocalState();
      if (localState && localState.datasetId === datasetId) {
        setState({
          ...localState,
          completedStages: new Set(localState.completedStages),
          datasetId
        });
        return true;
      }
      return false;
    };

    try {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/workflows/${datasetId}`, {
        headers: {
          ...(token && { Authorization: `Bearer ${token}` })
        }
      });
      if (response.ok) {
        const data = await response.json();
        workflowExistsRef.current = true;
        const restored: WorkflowState = {
          currentStage: data.current_stage as WorkflowStage,
          completedStages: new Set<WorkflowStage>(data.completed_stages),
          stageData: data.stage_data ?? {},
          datasetId,
          modelId: data.model_id ?? undefined,
          deploymentId: data.deployment_id ?? undefined
        };
        // Backend is the source of truth; remember it so the auto-save
        // effect doesn't immediately write an identical version back
        lastSavedRef.current = JSON.stringify(buildSavePayload(restored));
        setState(prev => ({ ...prev, ...restored }));
      } else if (response.status === 404) {
        // New dataset with no backend workflow yet; if the local cache is for
        // a different dataset, start this one from a clean slate. Reset the
        // saved-signature so the first save for this dataset is never skipped.
        workflowExistsRef.current = false;
        lastSavedRef.current = null;
        if (!restoreFromLocal()) {
          setState({ ...initialState, datasetId });
        }
      } else {
        console.error(`Failed to load workflow (HTTP ${response.status})`);
        restoreFromLocal();
      }
    } catch (error) {
      console.error('Failed to load workflow, using localStorage fallback:', error);
      restoreFromLocal();
    }
  }, []);

  // Load workflow state from backend (with localStorage fallback) or localStorage.
  // The backend load must finish BEFORE isHydrated flips: gated pages redirect
  // on canAccessStage() as soon as isHydrated is true, so recovery state has to
  // be in place by then (crash/new-device loads have no localStorage to lean on).
  useEffect(() => {
    const hydrate = async () => {
      const localState = readLocalState();
      // Dataset id sources, in priority order: explicit prop, localStorage
      // cache, the URL of a direct stage-page load (/explore/{id} after a
      // crash or on a new device, where no local cache exists)
      const pathSegments = (pathname ?? '').split('/').filter(Boolean);
      const pathDatasetId =
        pathSegments.length === 2 &&
        WORKFLOW_STAGES.some(stage => stage.route === `/${pathSegments[0]}`)
          ? pathSegments[1]
          : undefined;
      const datasetId = initialDatasetId ?? localState?.datasetId ?? pathDatasetId;

      if (localState) {
        setState({
          ...localState,
          completedStages: new Set(localState.completedStages)
        });
      }
      if (datasetId) {
        await loadWorkflow(datasetId);
      }
      setIsHydrated(true);
    };
    hydrate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialDatasetId]);

  // Save workflow state to localStorage when it changes
  useEffect(() => {
    if (state.datasetId) {
      const stateToSave = {
        ...state,
        completedStages: Array.from(state.completedStages),
        lastUpdated: new Date().toISOString()
      };
      localStorage.setItem('workflowState', JSON.stringify(stateToSave));
    }
  }, [state]);

  // Update current stage based on current route
  // Keeping currentStage in step with the route is a prop-driven adjustment, so
  // React's documented place for it is during render rather than in an effect.
  // Doing it here also means the first paint after a navigation already has the
  // right stage, instead of rendering the previous one and correcting it.
  const routeStage = WORKFLOW_STAGES.find(stage => pathname?.includes(stage.route));
  if (routeStage && routeStage.id !== state.currentStage) {
    setState(prev => ({
      ...prev,
      currentStage: routeStage.id
    }));
  }

  const canAccessStage = useCallback((stage: WorkflowStage): boolean => {
    const stageConfig = WORKFLOW_STAGES.find(s => s.id === stage);
    if (!stageConfig) return false;

    // Check if all required stages are completed
    return stageConfig.requiredStages.every(reqStage => 
      state.completedStages.has(reqStage)
    );
  }, [state.completedStages]);

  const completeStage = useCallback((
    stage: WorkflowStage,
    data?: any,
    opts?: { autoAdvance?: boolean }
  ) => {
    // The dataset id may arrive with this very completion (DATA_LOADING), so
    // resolve it for navigation rather than relying on the (stale) state value.
    const resolvedDatasetId =
      stage === WorkflowStage.DATA_LOADING && data?.datasetId
        ? data.datasetId
        : state.datasetId;

    setState(prev => {
      const newCompletedStages = new Set(prev.completedStages);
      newCompletedStages.add(stage);

      const newStageData = { ...prev.stageData };
      if (data) {
        newStageData[stage] = data;
      }

      // Update specific IDs based on stage
      const updates: Partial<WorkflowState> =
        stage === WorkflowStage.DATA_LOADING && data?.datasetId
          ? { datasetId: data.datasetId }
          : stage === WorkflowStage.MODEL_TRAINING && data?.modelId
          ? { modelId: data.modelId }
          : stage === WorkflowStage.DEPLOYMENT && data?.deploymentId
          ? { deploymentId: data.deploymentId }
          : {};

      return {
        ...prev,
        completedStages: newCompletedStages,
        stageData: newStageData,
        ...updates
      };
    });

    // Forward navigation is opt-in (default off): explicit "Continue" CTAs drive
    // transitions so the user stays in control. When auto-advance is requested,
    // check accessibility against the about-to-be-completed set (not the stale
    // closure) and use route-aware URL building.
    if (opts?.autoAdvance) {
      const next = getNextStage(stage);
      if (next) {
        const willBeComplete = new Set(state.completedStages);
        willBeComplete.add(stage);
        const accessible = next.requiredStages.every(req => willBeComplete.has(req));
        if (accessible) {
          router.push(buildStageUrl(next.id, resolvedDatasetId));
        }
      }
    }
  }, [state.datasetId, state.completedStages, router]);

  const setCurrentStage = useCallback((stage: WorkflowStage) => {
    if (canAccessStage(stage)) {
      setState(prev => ({ ...prev, currentStage: stage }));
      router.push(buildStageUrl(stage, state.datasetId));
    }
  }, [state.datasetId, canAccessStage, router]);

  const goToNextStage = useCallback(() => {
    const next = getNextStage(state.currentStage);
    if (!next) return;
    setState(prev => ({ ...prev, currentStage: next.id }));
    router.push(buildStageUrl(next.id, state.datasetId));
  }, [state.currentStage, state.datasetId, router]);

  const goToPreviousStage = useCallback(() => {
    const previous = getPreviousStage(state.currentStage);
    if (!previous) return;
    // No access check: backward navigation always restores a prior stage.
    setState(prev => ({ ...prev, currentStage: previous.id }));
    router.push(buildStageUrl(previous.id, state.datasetId));
  }, [state.currentStage, state.datasetId, router]);

  const requestStageRedirect = useCallback((targetStage: WorkflowStage, message: string) => {
    setGuardMessage(message);
    router.push(buildStageUrl(targetStage, state.datasetId));
  }, [state.datasetId, router]);

  const clearGuardMessage = useCallback(() => setGuardMessage(null), []);

  const resetWorkflow = useCallback(() => {
    setState(initialState);
    workflowExistsRef.current = false;
    lastSavedRef.current = null;
    localStorage.removeItem('workflowState');
    router.push('/upload');
  }, [router]);

  const setDatasetId = useCallback((datasetId: string) => {
    setState(prev => ({ ...prev, datasetId }));
    // Load workflow for this dataset
    loadWorkflow(datasetId);
  }, [loadWorkflow]);

  const saveWorkflow = useCallback(async () => {
    if (!state.datasetId) return;
    const payload = buildSavePayload(state);
    const signature = JSON.stringify(payload);
    // Skip no-op saves so reloads don't append redundant history versions
    if (signature === lastSavedRef.current) return;
    try {
      const token = await getAuthToken();
      const headers = {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` })
      };
      const url = `${API_URL}/workflows/${state.datasetId}`;
      const method = workflowExistsRef.current ? 'PUT' : 'POST';
      let response = await fetch(url, { method, headers, body: signature });
      if (method === 'POST' && response.status === 409) {
        // Workflow was already created (e.g. in another session) — update it
        response = await fetch(url, { method: 'PUT', headers, body: signature });
      }
      if (response.ok) {
        workflowExistsRef.current = true;
        lastSavedRef.current = signature;
      } else {
        console.error(`Failed to save workflow (HTTP ${response.status}); state kept in localStorage`);
      }
    } catch (error) {
      console.error('Failed to save workflow; state kept in localStorage:', error);
    }
  }, [state]);

  // Auto-save to the backend at stage boundaries: when a stage completes
  // (completedStages only grows) and when the user moves to a different
  // stage — otherwise a refresh mid-stage would restore the previous stage.
  // localStorage (effect above) remains the offline cache layer.
  const completedCount = state.completedStages.size;
  useEffect(() => {
    if (!isHydrated || !state.datasetId || completedCount === 0) return;
    saveWorkflow();
    // saveWorkflow identity changes with every state update; keying on
    // completedCount + currentStage limits backend writes to stage boundaries
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [completedCount, state.currentStage, state.datasetId, isHydrated]);

  const updateHistoryPosition = useCallback((position: number) => {
    setState(prev => ({
      ...prev,
      historyPosition: position
    }));
  }, []);

  const updateHistoryState = useCallback((historyState: { position: number; canUndo: boolean; canRedo: boolean }) => {
    setState(prev => ({
      ...prev,
      historyPosition: historyState.position,
      canUndo: historyState.canUndo,
      canRedo: historyState.canRedo
    }));
  }, []);

  const refreshHistory = useCallback(async () => {
    if (!state.datasetId) return;
    try {
      const token = await getAuthToken();
      const response = await fetch(
        `${API_URL}/api/v1/transformations/datasets/${state.datasetId}/history`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        updateHistoryState({
          position: data.current_position,
          canUndo: data.can_undo,
          canRedo: data.can_redo
        });
      }
    } catch (error) {
      console.error('Failed to refresh history:', error);
    }
  }, [state.datasetId, updateHistoryState]);

  const value: WorkflowContextType = {
    state,
    isHydrated,
    guardMessage,
    canAccessStage,
    completeStage,
    setCurrentStage,
    setDatasetId,
    resetWorkflow,
    loadWorkflow,
    saveWorkflow,
    goToNextStage,
    goToPreviousStage,
    requestStageRedirect,
    clearGuardMessage,
    updateHistoryPosition,
    updateHistoryState,
    refreshHistory
  };

  return (
    <WorkflowContext.Provider value={value}>
      {children}
    </WorkflowContext.Provider>
  );
}

export function useWorkflow() {
  const context = useContext(WorkflowContext);
  if (!context) {
    throw new Error('useWorkflow must be used within a WorkflowProvider');
  }
  return context;
}