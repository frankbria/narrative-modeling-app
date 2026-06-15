'use client';

import React, { useEffect } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useStageGuard } from '@/lib/hooks/useStageGuard';
import { StageNavigation } from '@/components/workflow/StageNavigation';
import TransformationPipeline from '@/components/transformation/TransformationPipeline';
import { useRouter, useSearchParams } from 'next/navigation';

export default function PreparePage() {
  const { state, completeStage, setDatasetId } = useWorkflow();
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlDatasetId = searchParams.get('datasetId');

  // Guard: redirect (with a message) if this stage is not accessible yet.
  useStageGuard(WorkflowStage.DATA_PREPARATION);

  useEffect(() => {
    // If a dataset ID is provided in the URL, use it
    if (urlDatasetId && urlDatasetId !== state.datasetId) {
      setDatasetId(urlDatasetId);
    }
  }, [urlDatasetId, state.datasetId, setDatasetId]);

  const handleTransformationComplete = (transformedDatasetId: string) => {
    // Mark stage as complete and save the transformed dataset ID
    completeStage(WorkflowStage.DATA_PREPARATION, {
      transformedDatasetId,
      timestamp: new Date().toISOString()
    });
  };

  const currentDatasetId = urlDatasetId || state.datasetId;

  if (!currentDatasetId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h2 className="text-2xl font-semibold mb-2">No Dataset Selected</h2>
          <p className="text-gray-600 mb-4">Please complete the data loading step first.</p>
          <button
            onClick={() => router.push('/upload')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Go to Data Loading
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="bg-white border-b px-6 py-4">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-2xl font-bold text-gray-900">Data Preparation</h1>
          <p className="text-gray-600 mt-1">Clean and transform your data using our visual pipeline builder</p>
        </div>
      </div>
      
      <div className="flex-1">
        <TransformationPipeline
          datasetId={currentDatasetId}
          onComplete={handleTransformationComplete}
        />
      </div>

      <div className="bg-white border-t px-6 py-4">
        <div className="max-w-7xl mx-auto">
          {/* Data preparation is optional — the user can apply transformations
              or skip straight to feature engineering. `ready` keeps Continue
              enabled; onContinue records the stage if it wasn't completed via a
              transformation. */}
          <StageNavigation
            currentStage={WorkflowStage.DATA_PREPARATION}
            ready
            onContinue={() => {
              if (!state.completedStages.has(WorkflowStage.DATA_PREPARATION)) {
                completeStage(WorkflowStage.DATA_PREPARATION, {
                  skipped: true,
                  timestamp: new Date().toISOString(),
                });
              }
            }}
          />
        </div>
      </div>
    </div>
  );
}