'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle, CheckCircle2, Sparkles } from 'lucide-react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useStageGuard } from '@/lib/hooks/useStageGuard';
import { StageNavigation } from '@/components/workflow/StageNavigation';
import { loadColumns } from '@/lib/services/datasetColumns';
import {
  choiceOf,
  recordedChoice,
  sameChoice,
  startingSelection,
  type ColumnChoice,
} from '@/lib/features/columnChoice';

/** The stage validation's own minimum (`validateStageCompletion`). */
const MIN_COLUMNS = 2;

interface NoDatasetProps {
  onUpload: VoidFunction;
}

function NoDataset(props: NoDatasetProps) {
  const { onUpload } = props;
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <h2 className="text-2xl font-semibold mb-2">No Dataset Selected</h2>
        <p className="text-muted-foreground mb-4">Please complete the previous steps first.</p>
        <button
          onClick={onUpload}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
        >
          Go to Data Loading
        </button>
      </div>
    </div>
  );
}

interface ColumnsUnavailableProps {
  onRetry: VoidFunction;
}

function ColumnsUnavailable(props: ColumnsUnavailableProps) {
  const { onRetry } = props;
  return (
    <div role="alert" className="p-4 rounded-lg border border-destructive/40 bg-destructive/10">
      <p className="font-semibold flex items-center gap-2">
        <AlertCircle className="w-5 h-5 text-destructive" />
        We could not read this dataset&apos;s columns.
      </p>
      <p className="text-sm text-muted-foreground mt-1">
        Nothing has been changed. If it keeps happening, open the dataset in Data Exploration
        first, so that it is processed.
      </p>
      <button
        onClick={onRetry}
        className="mt-3 px-4 py-2 rounded-lg border border-border bg-card hover:bg-muted text-sm font-medium"
      >
        Try again
      </button>
    </div>
  );
}

interface ColumnBoxProps {
  column: string;
  checked: boolean;
  onToggle(column: string): void;
}

function ColumnBox(props: ColumnBoxProps) {
  const { column, checked, onToggle } = props;
  const toggle = () => onToggle(column);
  return (
    <label className="flex items-center gap-2 p-3 border border-border rounded-lg hover:bg-muted cursor-pointer">
      <input type="checkbox" checked={checked} onChange={toggle} aria-label={column} className="w-4 h-4" />
      <span className="font-medium font-mono text-sm break-all">{column}</span>
    </label>
  );
}

interface ShownProps {
  show: boolean;
}

function TooFew(props: ShownProps) {
  const { show } = props;
  if (!show) return null;
  return (
    <p className="text-sm text-destructive flex items-center gap-2">
      <AlertCircle className="w-4 h-4" />
      Select at least {MIN_COLUMNS} columns.
    </p>
  );
}

function Recorded(props: ShownProps) {
  const { show } = props;
  if (!show) return null;
  return (
    <p data-testid="choice-recorded" className="text-sm flex items-center gap-2">
      <CheckCircle2 className="w-4 h-4 text-green-600" />
      This choice is recorded. Continue to Model Training below.
    </p>
  );
}

interface ColumnChoiceFormProps {
  columns: string[];
  selected: string[];
  recorded: boolean;
  onToggle(column: string): void;
  onRecord: VoidFunction;
}

function ColumnChoiceForm(props: ColumnChoiceFormProps) {
  const { columns, selected, recorded, onToggle, onRecord } = props;
  const enough = selected.length >= MIN_COLUMNS;
  const summary = `${selected.length} of ${columns.length} columns selected`;
  const action = `Use these ${selected.length} columns`;
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Choose the columns the model may learn from. A column you leave out is never shown to
        the model. You pick the column to predict in the next step, and it is never used as a
        feature, whatever you choose here. Identifiers, dates and empty columns are set aside
        automatically at training.
      </p>
      <p className="text-sm font-medium">{summary}</p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {columns.map((column) => (
          <ColumnBox key={column} column={column} checked={selected.includes(column)} onToggle={onToggle} />
        ))}
      </div>
      <TooFew show={!enough} />
      <Recorded show={recorded} />
      <div className="flex justify-end">
        <button
          onClick={onRecord}
          disabled={!enough || recorded}
          data-testid="use-columns-button"
          className="px-6 py-2 rounded-lg font-medium bg-primary text-primary-foreground hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed"
        >
          {action}
        </button>
      </div>
    </div>
  );
}

/** What completing the stage stores: the choice, and when it was made. */
function stageRecord(columns: string[], selected: string[]) {
  const choice = choiceOf(columns, selected);
  return { ...choice, timestamp: new Date().toISOString() };
}

interface Edited {
  datasetId: string | undefined;
  names: string[];
}

interface Selection {
  selected: string[];
  toggle(column: string): void;
}

/** The user's edits on top of where the stage starts; they reset with the dataset. */
function useSelection(datasetId: string | undefined, columns: string[], recorded: ColumnChoice | null): Selection {
  const [edited, setEdited] = useState<Edited | null>(null);
  const mine = edited !== null && edited.datasetId === datasetId;
  const current = mine ? edited.names : startingSelection(columns, recorded);
  const toggle = (column: string) => {
    const names = current.includes(column) ? current.filter((name) => name !== column) : [...current, column];
    setEdited({ datasetId, names });
  };
  return { selected: columns.filter((column) => current.includes(column)), toggle };
}

interface ChoiceBodyProps {
  loading: boolean;
  columns: string[];
  selection: Selection;
  recorded: boolean;
  onRecord: VoidFunction;
  onRetry: VoidFunction;
}

function ChoiceBody(props: ChoiceBodyProps) {
  const { loading, columns, selection } = props;
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
      </div>
    );
  }
  if (columns.length === 0) return <ColumnsUnavailable onRetry={props.onRetry} />;
  return (
    <ColumnChoiceForm
      columns={columns}
      selected={selection.selected}
      recorded={props.recorded}
      onToggle={selection.toggle}
      onRecord={props.onRecord}
    />
  );
}

/**
 * Feature Engineering stage: which of the dataset's columns the model may learn from.
 *
 * The columns come from the dataset record itself, the same read the Model
 * Training stage uses. Recording the choice completes the stage; training then
 * leaves the unselected columns out (`feature_config.exclude_columns`, #969).
 */
export default function FeaturesPage() {
  const { state, completeStage } = useWorkflow();
  const router = useRouter();
  const { ready } = useStageGuard(WorkflowStage.FEATURE_ENGINEERING);
  const datasetId = state.datasetId;
  const load = useAsyncData(() => loadColumns(datasetId as string), [datasetId], {
    enabled: ready && Boolean(datasetId),
  });
  const columns = load.data ?? [];
  const recorded = recordedChoice(state.stageData[WorkflowStage.FEATURE_ENGINEERING]);
  const selection = useSelection(datasetId, columns, recorded);
  const isRecorded = sameChoice(recorded, selection.selected);
  const goToUpload = () => router.push('/upload');
  const record = () => completeStage(WorkflowStage.FEATURE_ENGINEERING, stageRecord(columns, selection.selected));

  if (!datasetId) return <NoDataset onUpload={goToUpload} />;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="bg-card rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-yellow-500" />
          Feature Engineering
        </h1>
        <ChoiceBody
          loading={load.loading}
          columns={columns}
          selection={selection}
          recorded={isRecorded}
          onRecord={record}
          onRetry={load.reload}
        />
        <StageNavigation
          currentStage={WorkflowStage.FEATURE_ENGINEERING}
          ready={isRecorded}
          loading={load.loading}
        />
      </div>
    </div>
  );
}
