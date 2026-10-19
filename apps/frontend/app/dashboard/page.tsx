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

async function getJson(path: string, what: string): Promise<unknown> {
  const token = await getAuthToken();
  const response = await fetch(`${API_URL}/${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch ${what}`);
  }
  return response.json();
}

async function fetchDatasets() {
  return listOf(await getJson('datasets?page=1&limit=5', 'datasets'), 'datasets') as DatasetItem[];
}

// One row of `GET /ml/` (`ModelInfo`), the trained-model surface (#1069).
type TrainedModel = Omit<ModelItem, 'status'> & { is_deployed: boolean };

function modelItem(model: TrainedModel): ModelItem {
  const { model_id, name, algorithm, test_score, created_at } = model;
  return { model_id, name, algorithm, test_score, created_at, status: model.is_deployed ? 'deployed' : 'trained' };
}

async function fetchModelList(query: string): Promise<ModelItem[]> {
  const body = await getJson(`ml/?${query}`, 'models');
  if (!Array.isArray(body)) {
    throw new Error('Invalid models format: expected array');
  }
  return (body as TrainedModel[]).map(modelItem);
}

function isDeployed(model: ModelItem): boolean {
  return model.status.toLowerCase() === 'deployed';
}

const NO_MODELS = { recent: [] as ModelItem[], canDeploy: false };

// `/ml/` answers a bare list, newest first. Recent Models asks for five rows; View
// Deployments asks for one deployed row, since the deployed model may be older than
// the five (#1085).
async function fetchModels() {
  const [recent, deployed] = await Promise.all([
    fetchModelList('limit=5'),
    fetchModelList('deployed=true&limit=1'),
  ]);
  return { recent, canDeploy: deployed.some(isDeployed) };
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
  const { recent: recentModels, canDeploy } = models.data || NO_MODELS;
  const [datasetToErase, setDatasetToErase] = useState<DatasetItem | null>(null);
  const [samplesOpen, setSamplesOpen] = useState(false);

  const hasDatasets = recentDatasets.length > 0;
  const openSamples = () => setSamplesOpen(true);
  const stopErasing = () => setDatasetToErase(null);
  const exploreSample = (datasetId: string) => router.push(`/explore/${datasetId}`);

  return (
    <div className="max-w-7xl mx-auto p-6" data-testid="dashboard">
      {HEADER}
      <QuickActions canTrain={hasDatasets} canDeploy={canDeploy} />
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
