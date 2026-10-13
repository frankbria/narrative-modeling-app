'use client';

import React, { useState } from 'react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { useRouter } from 'next/navigation';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { useOnboardingRedirect } from '@/lib/hooks/useOnboardingRedirect';
import { ErasureConfirmDialog } from '@/components/settings/ErasureConfirmDialog';
import { SampleDatasetSelector } from '@/components/SampleDatasetSelector';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { erasureApi } from '@/lib/services/erasure';
import { COMPANY } from '@/lib/legal/company';
import { HelpCard, QuickActions, StageCards, WorkflowProgress } from '@/components/dashboard/StageOverview';
import { RecentDatasets, RecentModels, type DatasetItem, type ModelItem } from '@/components/dashboard/RecentLists';

type EraseDialogProps = { dataset: DatasetItem; onClose: VoidFunction; onErased: VoidFunction };

const HEADER = (
  <div className="mb-8">
    <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
    <p className="text-muted-foreground mt-2">
      Welcome to {COMPANY.serviceName}. Track your progress through the 8-stage ML workflow.
    </p>
  </div>
);

const ERASE_BODY = (
  <p>
    This permanently deletes this dataset and everything derived from it —
    transformations, versions, trained models and their stored files. This cannot be
    undone.
  </p>
);

function listOf(data: unknown, key: string): unknown[] {
  if (!data || typeof data !== 'object') {
    throw new Error('Invalid API response format');
  }
  const items = (data as Record<string, unknown>)[key];
  if (items === undefined) return [];
  if (!Array.isArray(items)) {
    throw new Error(`Invalid ${key} format: expected array`);
  }
  return items;
}

async function fetchList(key: string): Promise<unknown[]> {
  const token = await getAuthToken();
  const response = await fetch(`${API_URL}/${key}?page=1&limit=5`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch ${key}`);
  }
  return listOf(await response.json(), key);
}

async function fetchDatasets() {
  return (await fetchList('datasets')) as DatasetItem[];
}

async function fetchModels() {
  return (await fetchList('models')) as ModelItem[];
}

function isDeployed(model: ModelItem): boolean {
  return model.status.toLowerCase() === 'deployed';
}

// Per-dataset right-to-erasure (#482).
function EraseDatasetDialog(props: EraseDialogProps) {
  const { dataset, onClose, onErased } = props;
  const closeWhenDismissed = (next: boolean) => {
    if (!next) onClose();
  };
  const erase = () => erasureApi.eraseDataset(dataset.dataset_id);

  return (
    <ErasureConfirmDialog
      open
      onOpenChange={closeWhenDismissed}
      title={`Delete "${dataset.filename}"`}
      confirmWord={dataset.filename}
      onConfirm={erase}
      // Keep the dialog open so its success summary shows; refresh the list
      // behind it. Closing (the Close button) clears the dataset.
      onErased={onErased}
      body={ERASE_BODY}
    />
  );
}

export default function DashboardPage() {
  const router = useRouter();
  useOnboardingRedirect();

  const datasets = useAsyncData(fetchDatasets, [], { errorMessage: 'Unable to load datasets' });
  const models = useAsyncData(fetchModels, [], { errorMessage: 'Unable to load models' });
  const recentDatasets = datasets.data || [];
  const recentModels = models.data || [];
  const [datasetToErase, setDatasetToErase] = useState<DatasetItem | null>(null);
  const [samplesOpen, setSamplesOpen] = useState(false);

  const hasDatasets = recentDatasets.length > 0;
  const openSamples = () => setSamplesOpen(true);
  const stopErasing = () => setDatasetToErase(null);
  const exploreSample = (datasetId: string) => router.push(`/explore/${datasetId}`);

  return (
    <div className="max-w-7xl mx-auto p-6" data-testid="dashboard">
      {HEADER}
      <QuickActions canTrain={hasDatasets} canDeploy={recentModels.some(isDeployed)} />
      <WorkflowProgress />
      <StageCards />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecentDatasets
          datasets={recentDatasets}
          loading={datasets.loading}
          error={datasets.error}
          onRetry={datasets.reload}
          onErase={setDatasetToErase}
          onTrySample={openSamples}
        />
        <RecentModels
          models={recentModels}
          loading={models.loading}
          error={models.error}
          onRetry={models.reload}
          canTrain={hasDatasets}
        />
      </div>

      <HelpCard />

      <Dialog open={samplesOpen} onOpenChange={setSamplesOpen}>
        <DialogContent className="sm:max-w-5xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Try a sample dataset</DialogTitle>
            <DialogDescription>
              Each sample is a few thousand rows and trains in quick mode in under a minute.
            </DialogDescription>
          </DialogHeader>
          <SampleDatasetSelector onDatasetSelected={exploreSample} />
        </DialogContent>
      </Dialog>

      {datasetToErase && (
        <EraseDatasetDialog dataset={datasetToErase} onClose={stopErasing} onErased={datasets.reload} />
      )}
    </div>
  );
}
