'use client';

import React, { useEffect } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import TransformationPipeline from '@/components/TransformationPipeline';
import { useRouter } from 'next/navigation';

export default function PreparePage() {
  const { state, completeStage, canAccessStage } = useWorkflow();
  const router = useRouter();

  useEffect(() => {
    // Check if user can access this stage
    if (!canAccessStage(WorkflowStage.DATA_PREPARATION)) {
      router.push('/upload');
    }
  }, [canAccessStage, router]);

  const handleTransformationComplete = (transformedDatasetId: string) => {
    // Mark stage as complete and save the transformed dataset ID
    completeStage(WorkflowStage.DATA_PREPARATION, {
      transformedDatasetId,
      timestamp: new Date().toISOString()
    });
  };

  if (!state.datasetId) {
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
    <div className="h-full">
      <TransformationPipeline 
        datasetId={state.datasetId}
        onComplete={handleTransformationComplete}
      />
    </div>
  );
}