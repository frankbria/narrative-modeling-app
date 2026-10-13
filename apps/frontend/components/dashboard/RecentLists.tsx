'use client';

import React, { type KeyboardEvent, type MouseEvent, type ReactNode, type SyntheticEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Upload, Sparkles, Brain, ArrowRight, Database, AlertCircle, Trash2 } from 'lucide-react';

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
  training: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200',
  trained: 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200',
  deployed: 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200',
  failed: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200',
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
      <div className="h-10 w-10 bg-gray-200 rounded" />
      <div className="flex-1 space-y-2">
        <div className="h-4 bg-gray-200 rounded w-3/4" />
        <div className="h-3 bg-gray-200 rounded w-1/2" />
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
    <div className="flex items-center gap-2 text-red-600 py-4">
      <AlertCircle size={16} />
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
      <div className="p-2 bg-blue-100 dark:bg-blue-900/40 rounded">
        <Database size={16} className="text-blue-600" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm text-foreground truncate">{dataset.filename}</p>
        <p className="text-xs text-muted-foreground">
          {dataset.num_rows.toLocaleString()} rows, {dataset.num_columns} columns
        </p>
      </div>
      <span className="text-xs text-gray-400">{formatRelativeTime(dataset.created_at)}</span>
      <button
        type="button"
        aria-label={`Delete dataset ${dataset.filename}`}
        data-testid="erase-dataset"
        className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10"
        onClick={erase}
        onKeyDown={stopHere}
      >
        <Trash2 size={16} />
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
        <ArrowRight size={14} className="ml-1" />
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
      <Database size={32} className="mx-auto text-muted-foreground mb-3" />
      <p className="font-medium text-sm mb-1">Start with some data</p>
      <p className="text-muted-foreground text-sm mb-4">
        Upload a CSV of your own, or start with a sample that trains in under a minute.
      </p>
      <div className="flex flex-wrap gap-2 justify-center">
        <Button size="sm" onClick={upload}>
          <Upload size={14} className="mr-1" />
          Upload a CSV
        </Button>
        <Button size="sm" variant="outline" onClick={onTrySample}>
          <Sparkles size={14} className="mr-1" />
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
          <Database size={20} />
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
      <div className="p-2 bg-purple-100 dark:bg-purple-900/40 rounded">
        <Brain size={16} className="text-purple-600" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm text-foreground truncate">{model.name}</p>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{model.algorithm}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${statusColor(model.status)}`}>{model.status}</span>
        </div>
      </div>
      {model.test_score !== null && (
        <span className="text-xs font-medium text-green-600">{(model.test_score * 100).toFixed(1)}%</span>
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
        <ArrowRight size={14} className="ml-1" />
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
      <Brain size={32} className="mx-auto text-gray-300 mb-3" />
      <p className="text-muted-foreground text-sm mb-4">No models trained yet</p>
      <Button size="sm" onClick={train} disabled={!canTrain}>
        <Sparkles size={14} className="mr-1" />
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
          <Brain size={20} />
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
