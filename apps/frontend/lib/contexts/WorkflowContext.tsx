'use client';

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { WorkflowState, WorkflowStage, WorkflowContextType, WORKFLOW_STAGES } from '@/lib/types/workflow';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';

const initialState: WorkflowState = {
  currentStage: WorkflowStage.DATA_LOADING,
  completedStages: new Set<WorkflowStage>(),
  stageData: {} as Record<WorkflowStage, any>,
};

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
  const router = useRouter();
  const pathname = usePathname();

  // Load workflow state from localStorage or backend
  useEffect(() => {
    if (initialDatasetId) {
      loadWorkflow(initialDatasetId);
    } else {
      // Try to load from localStorage
      const savedState = localStorage.getItem('workflowState');
      if (savedState) {
        try {
          const parsed = JSON.parse(savedState);
          setState({
            ...parsed,
            completedStages: new Set(parsed.completedStages)
          });
        } catch (e) {
          console.error('Failed to load workflow state:', e);
        }
      }
    }
  }, [initialDatasetId]);

  // Save workflow state to localStorage when it changes
  useEffect(() => {
    if (state.datasetId) {
      const stateToSave = {
        ...state,
        completedStages: Array.from(state.completedStages)
      };
      localStorage.setItem('workflowState', JSON.stringify(stateToSave));
    }
  }, [state]);

  // Update current stage based on current route
  useEffect(() => {
    const currentStageConfig = WORKFLOW_STAGES.find(stage => 
      pathname?.includes(stage.route)
    );
    if (currentStageConfig && currentStageConfig.id !== state.currentStage) {
      setState(prev => ({
        ...prev,
        currentStage: currentStageConfig.id
      }));
    }
  }, [pathname, state.currentStage]);

  const canAccessStage = useCallback((stage: WorkflowStage): boolean => {
    const stageConfig = WORKFLOW_STAGES.find(s => s.id === stage);
    if (!stageConfig) return false;

    // Check if all required stages are completed
    return stageConfig.requiredStages.every(reqStage => 
      state.completedStages.has(reqStage)
    );
  }, [state.completedStages]);

  const completeStage = useCallback((stage: WorkflowStage, data?: any) => {
    setState(prev => {
      const newCompletedStages = new Set(prev.completedStages);
      newCompletedStages.add(stage);
      
      const newStageData = { ...prev.stageData };
      if (data) {
        newStageData[stage] = data;
      }

      // Update specific IDs based on stage
      let updates: Partial<WorkflowState> = {};
      if (stage === WorkflowStage.DATA_LOADING && data?.datasetId) {
        updates.datasetId = data.datasetId;
      } else if (stage === WorkflowStage.MODEL_TRAINING && data?.modelId) {
        updates.modelId = data.modelId;
      } else if (stage === WorkflowStage.DEPLOYMENT && data?.deploymentId) {
        updates.deploymentId = data.deploymentId;
      }

      return {
        ...prev,
        completedStages: newCompletedStages,
        stageData: newStageData,
        ...updates
      };
    });

    // Auto-advance to next stage
    const currentIndex = WORKFLOW_STAGES.findIndex(s => s.id === stage);
    if (currentIndex < WORKFLOW_STAGES.length - 1) {
      const nextStage = WORKFLOW_STAGES[currentIndex + 1];
      if (canAccessStage(nextStage.id)) {
        router.push(`${nextStage.route}${state.datasetId ? `/${state.datasetId}` : ''}`);
      }
    }
  }, [state.datasetId, canAccessStage, router]);

  const setCurrentStage = useCallback((stage: WorkflowStage) => {
    const stageConfig = WORKFLOW_STAGES.find(s => s.id === stage);
    if (stageConfig && canAccessStage(stage)) {
      setState(prev => ({ ...prev, currentStage: stage }));
      router.push(`${stageConfig.route}${state.datasetId ? `/${state.datasetId}` : ''}`);
    }
  }, [state.datasetId, canAccessStage, router]);

  const resetWorkflow = useCallback(() => {
    setState(initialState);
    localStorage.removeItem('workflowState');
    router.push('/upload');
  }, [router]);

  const loadWorkflow = useCallback(async (datasetId: string) => {
    try {
      // For now, just set the datasetId without loading from backend
      // TODO: Implement workflow persistence endpoint
      setState(prev => ({
        ...prev,
        datasetId
      }));
      return;
      
      // Use client-side token helper
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/workflow/${datasetId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setState({
          ...data,
          completedStages: new Set(data.completedStages),
          datasetId
        });
      }
    } catch (error) {
      console.error('Failed to load workflow:', error);
    }
  }, []);

  const setDatasetId = useCallback((datasetId: string) => {
    setState(prev => ({ ...prev, datasetId }));
    // Load workflow for this dataset
    loadWorkflow(datasetId);
  }, [loadWorkflow]);

  const saveWorkflow = useCallback(async () => {
    if (!state.datasetId) return;
    try {
      const token = await getAuthToken();
      const dataToSave = {
        ...state,
        completedStages: Array.from(state.completedStages)
      };
      await fetch(`${API_URL}/workflow/${state.datasetId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(dataToSave)
      });
    } catch (error) {
      console.error('Failed to save workflow:', error);
    }
  }, [state]);

  const value: WorkflowContextType = {
    state,
    canAccessStage,
    completeStage,
    setCurrentStage,
    setDatasetId,
    resetWorkflow,
    loadWorkflow,
    saveWorkflow
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