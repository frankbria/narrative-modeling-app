'use client';

import React, { useEffect } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import TransformationPipeline from '@/components/transformation/TransformationPipeline';
import { useRouter, useSearchParams } from 'next/navigation';

export default function PreparePage() {
  const { state, completeStage, canAccessStage, setDatasetId } = useWorkflow();
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlDatasetId = searchParams.get('datasetId');

  useEffect(() => {
    // If a dataset ID is provided in the URL, use it
    if (urlDatasetId && urlDatasetId !== state.datasetId) {
      setDatasetId(urlDatasetId);
    }
  }, [urlDatasetId, state.datasetId, setDatasetId]);

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
    </div>
  );
}