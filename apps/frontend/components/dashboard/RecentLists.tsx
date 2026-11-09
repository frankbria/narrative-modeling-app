'use client';

import React, { type KeyboardEvent, type MouseEvent, type ReactNode, type SyntheticEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { HugeiconsIcon } from '@/components/ui/icon';
import { AlertCircleIcon, ArrowRight01Icon, Brain01Icon, Database01Icon, Delete02Icon, SparklesIcon, Upload04Icon } from '@hugeicons/core-free-icons';

export interface DatasetItem {
  dataset_id: string;
  filename: string;
  num_rows: number;
  num_columns: number;
  created_at: string;
}

export interface ModelItem {
  model_id: string;
  name: string;
  algorithm: string;
  status: string;
  test_score: number | null;
  created_at: string;
}

type ListStateProps = { loading: boolean; error: string | null; onRetry: VoidFunction; children: ReactNode };
type RecentDatasetsProps = {
  datasets: DatasetItem[];
  loading: boolean;
  error: string | null;
  onRetry: VoidFunction;
  onErase(dataset: DatasetItem): void;
  onTrySample: VoidFunction;
};
type DatasetRowProps = { dataset: DatasetItem; onErase(dataset: DatasetItem): void };
type DatasetRowsProps = { datasets: DatasetItem[]; onErase(dataset: DatasetItem): void };
type EmptyDatasetsProps = { onTrySample: VoidFunction };
type RecentModelsProps = {
  models: ModelItem[];
  loading: boolean;
  error: string | null;
  onRetry: VoidFunction;
  canTrain: boolean;
};
type ModelRowProps = { model: ModelItem };
type ModelRowsProps = { models: ModelItem[] };
type EmptyModelsProps = { canTrain: boolean };

const ROW = 'flex items-center gap-3 p-2 rounded-lg hover:bg-muted cursor-pointer transition-colors';

const STATUS_COLORS: Record<string, string> = {
  training: 'bg-warning/10 text-warning',
  trained: 'bg-success/10 text-success',
  deployed: 'bg-primary/10 text-primary',
  failed: 'bg-destructive/10 text-destructive',
};

function statusColor(status: string): string {
  return STATUS_COLORS[status.toLowerCase()] || 'bg-muted text-foreground';
}

function ago(count: number, unit: string): string {
  const plural = count === 1 ? '' : 's';
  return `${count} ${unit}${plural} ago`;
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const diffSecs = Math.floor((Date.now() - date.getTime()) / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return 'just now';
  if (diffMins < 60) return ago(diffMins, 'minute');
  if (diffHours < 24) return ago(diffHours, 'hour');
  if (diffDays < 7) return ago(diffDays, 'day');
  return date.toLocaleDateString();
}

// A button inside a row: its Enter/Space must not reach the row's own handler,
// which opens the row. The button's native activation still fires its onClick.
function stopHere(e: SyntheticEvent) {
  e.stopPropagation();
}

function skeletonRow(i: number) {
  return (
    <div key={i} className="animate-pulse flex items-center gap-3">
      <div className="h-10 w-10 bg-muted rounded" />
      <div className="flex-1 space-y-2">
        <div className="h-4 bg-muted rounded w-3/4" />
        <div className="h-3 bg-muted rounded w-1/2" />
      </div>
    </div>
  );
}

const LIST_SKELETON = <div className="space-y-3">{[1, 2, 3].map(skeletonRow)}</div>;

/** A list's loading and failed states; its children are the loaded one. */
function ListState(props: ListStateProps) {
  const { loading, error, onRetry, children } = props;
  if (loading) return LIST_SKELETON;
  if (!error) return children;
  return (
    <div className="flex items-center gap-2 text-destructive py-4">
      <HugeiconsIcon icon={AlertCircleIcon} size={16} />
      <span className="text-sm">{error}</span>
      <Button variant="ghost" size="sm" onClick={onRetry} className="ml-2">
        Retry
      </Button>
    </div>
  );
}

function DatasetRow(props: DatasetRowProps) {
  const { dataset, onErase } = props;
  const router = useRouter();
  const open = () => router.push(`/explore/${dataset.dataset_id}`);
  const openOnEnter = (e: KeyboardEvent) => {
    if (e.key === 'Enter') open();
  };
  const erase = (e: MouseEvent) => {
    e.stopPropagation();
    onErase(dataset);
  };

  return (
    <div className={ROW} onClick={open} role="button" tabIndex={0} onKeyDown={openOnEnter}>
      <div className="p-2 bg-primary/10 rounded">
        <HugeiconsIcon icon={Database01Icon} size={16} className="text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm text-foreground truncate">{dataset.filename}</p>
        <p className="text-xs text-muted-foreground">
          {dataset.num_rows.toLocaleString()} rows, {dataset.num_columns} columns
        </p>
      </div>
      <span className="text-xs text-muted-foreground">{formatRelativeTime(dataset.created_at)}</span>
      <button
        type="button"
        aria-label={`Delete dataset ${dataset.filename}`}
        data-testid="erase-dataset"
        className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10"
        onClick={erase}
        onKeyDown={stopHere}
      >
        <HugeiconsIcon icon={Delete02Icon} size={16} />
      </button>
    </div>
  );
}

function DatasetRows(props: DatasetRowsProps) {
  const { datasets, onErase } = props;
  const router = useRouter();
  const viewAll = () => router.push('/explore');
  const row = (dataset: DatasetItem) => <DatasetRow key={dataset.dataset_id} dataset={dataset} onErase={onErase} />;

  return (
    <div className="space-y-3">
      {datasets.map(row)}
      <Button variant="ghost" size="sm" onClick={viewAll} className="w-full mt-2">
        View All Datasets
        <HugeiconsIcon icon={ArrowRight01Icon} size={14} className="ml-1" />
      </Button>
    </div>
  );
}

function EmptyDatasets(props: EmptyDatasetsProps) {
  const { onTrySample } = props;
  const router = useRouter();
  const upload = () => router.push('/upload');

  return (
    <div className="text-center py-8" data-testid="datasets-empty-state">
      <HugeiconsIcon icon={Database01Icon} size={32} className="mx-auto text-muted-foreground mb-3" />
      <p className="font-medium text-sm mb-1">Start with some data</p>
      <p className="text-muted-foreground text-sm mb-4">
        Upload a CSV of your own, or start with a sample that trains in under a minute.
      </p>
      <div className="flex flex-wrap gap-2 justify-center">
        <Button size="sm" onClick={upload}>
          <HugeiconsIcon icon={Upload04Icon} size={14} className="mr-1" />
          Upload a CSV
        </Button>
        <Button size="sm" variant="outline" onClick={onTrySample}>
          <HugeiconsIcon icon={SparklesIcon} size={14} className="mr-1" />
          Try a sample dataset
        </Button>
      </div>
    </div>
  );
}

export function RecentDatasets(props: RecentDatasetsProps) {
  const { datasets, loading, error, onRetry, onErase, onTrySample } = props;
  const loaded =
    datasets.length > 0 ? <DatasetRows datasets={datasets} onErase={onErase} /> : <EmptyDatasets onTrySample={onTrySample} />;

  return (
    <Card data-testid="recent-datasets">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <HugeiconsIcon icon={Database01Icon} size={20} />
          Recent Datasets
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ListState loading={loading} error={error} onRetry={onRetry}>
          {loaded}
        </ListState>
      </CardContent>
    </Card>
  );
}

function ModelRow(props: ModelRowProps) {
  const { model } = props;
  const router = useRouter();
  const open = () => router.push(`/model/${model.model_id}`);
  const openOnEnter = (e: KeyboardEvent) => {
    if (e.key === 'Enter') open();
  };

  return (
    <div className={ROW} onClick={open} role="button" tabIndex={0} onKeyDown={openOnEnter}>
      <div className="p-2 bg-primary/10 rounded">
        <HugeiconsIcon icon={Brain01Icon} size={16} className="text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm text-foreground truncate">{model.name}</p>
        {/* Runs of one dataset share a name; the time tells them apart. */}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 whitespace-nowrap">
          <span className="text-xs text-muted-foreground">{model.algorithm}</span>
          <span className="text-xs text-muted-foreground">{formatRelativeTime(model.created_at)}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${statusColor(model.status)}`}>{model.status}</span>
        </div>
      </div>
      {model.test_score !== null && (
        <span className="text-sm font-semibold text-foreground">{(model.test_score * 100).toFixed(1)}%</span>
      )}
    </div>
  );
}

function ModelRows(props: ModelRowsProps) {
  const { models } = props;
  const router = useRouter();
  const viewAll = () => router.push('/model');
  const row = (model: ModelItem) => <ModelRow key={model.model_id} model={model} />;

  return (
    <div className="space-y-3">
      {models.map(row)}
      <Button variant="ghost" size="sm" onClick={viewAll} className="w-full mt-2">
        View All Models
        <HugeiconsIcon icon={ArrowRight01Icon} size={14} className="ml-1" />
      </Button>
    </div>
  );
}

function EmptyModels(props: EmptyModelsProps) {
  const { canTrain } = props;
  const router = useRouter();
  const train = () => router.push('/model');

  return (
    <div className="text-center py-8">
      <HugeiconsIcon icon={Brain01Icon} size={32} className="mx-auto text-muted-foreground mb-3" />
      <p className="text-muted-foreground text-sm mb-4">No models trained yet</p>
      <Button size="sm" onClick={train} disabled={!canTrain}>
        <HugeiconsIcon icon={SparklesIcon} size={14} className="mr-1" />
        Train Model
      </Button>
    </div>
  );
}

export function RecentModels(props: RecentModelsProps) {
  const { models, loading, error, onRetry, canTrain } = props;
  const loaded = models.length > 0 ? <ModelRows models={models} /> : <EmptyModels canTrain={canTrain} />;

  return (
    <Card data-testid="recent-models">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <HugeiconsIcon icon={Brain01Icon} size={20} />
          Recent Models
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ListState loading={loading} error={error} onRetry={onRetry}>
          {loaded}
        </ListState>
      </CardContent>
    </Card>
  );
}
