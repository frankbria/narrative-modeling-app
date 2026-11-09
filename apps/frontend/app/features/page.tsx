'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { HugeiconsIcon } from '@/components/ui/icon';
import { AlertCircleIcon, CheckmarkCircle02Icon, SparklesIcon } from '@hugeicons/core-free-icons';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useStageGuard } from '@/lib/hooks/useStageGuard';
import { StageNavigation } from '@/components/workflow/StageNavigation';
import { Switch } from '@/components/ui/switch';
import { useTargetChoice } from '@/lib/features/useTargetChoice';
import { loadColumns } from '@/lib/services/datasetColumns';
import {
  choiceOf,
  interactionsOn,
  recordedChoice,
  recordedTarget,
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
        <HugeiconsIcon icon={AlertCircleIcon} className="w-5 h-5 text-destructive" />
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
      <HugeiconsIcon icon={AlertCircleIcon} className="w-4 h-4" />
      Select at least {MIN_COLUMNS} columns.
    </p>
  );
}

function Recorded(props: ShownProps) {
  const { show } = props;
  if (!show) return null;
  return (
    <p data-testid="choice-recorded" className="text-sm flex items-center gap-2">
      <HugeiconsIcon icon={CheckmarkCircle02Icon} className="w-4 h-4 text-success" />
      Your choice is saved. Continue to Model Training below.
    </p>
  );
}

interface InteractionsSwitchProps {
  on: boolean;
  onChange(on: boolean): void;
}

function InteractionsSwitch(props: InteractionsSwitchProps) {
  const { on, onChange } = props;
  return (
    <div className="flex items-start gap-3 p-3 border border-border rounded-lg">
      <Switch id="try-interactions" checked={on} onCheckedChange={onChange} />
      <div className="space-y-1">
        <label htmlFor="try-interactions" className="text-sm font-medium cursor-pointer">
          Also try interaction features
        </label>
        <p className="text-sm text-muted-foreground">
          Adds products and ratios of pairs of numeric columns for the model to learn from. It can
          lengthen training.
        </p>
      </div>
    </div>
  );
}

interface TargetPickerProps {
  columns: string[];
  target: string;
  onChange(column: string): void;
}

function TargetPicker(props: TargetPickerProps) {
  const { columns, target, onChange } = props;
  const change = (e: React.ChangeEvent<HTMLSelectElement>) => onChange(e.target.value);
  return (
    <div className="p-3 border border-primary/30 bg-primary/5 rounded-lg">
      <label htmlFor="target-column" className="block text-sm font-medium mb-1">
        Column to predict
      </label>
      <select
        id="target-column"
        value={target}
        onChange={change}
        className="w-full p-2 border border-border rounded-lg focus:ring-[3px] focus:ring-ring/50 focus:border-primary"
      >
        <option value="">Select the column to predict...</option>
        {columns.map((column) => (
          <option key={column} value={column}>
            {column}
          </option>
        ))}
      </select>
      <p className="text-xs text-muted-foreground mt-1">
        This is the answer the model learns to give. It is never one of the columns it learns from.
      </p>
    </div>
  );
}

interface ColumnChoiceFormProps {
  columns: string[];
  features: string[];
  selected: string[];
  target: string;
  interactions: boolean;
  recorded: boolean;
  onToggle(column: string): void;
  onTarget(column: string): void;
  onInteractions(on: boolean): void;
}

function ColumnChoiceForm(props: ColumnChoiceFormProps) {
  const { columns, features, selected, target, interactions, recorded, onToggle, onTarget, onInteractions } = props;
  const summary = `${selected.length} of ${features.length} columns selected`;
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Pick the column to predict, then choose the other columns the model may learn from. A
        column you leave out is never shown to the model. Identifiers, dates and empty columns
        are set aside automatically at training.
      </p>
      <TargetPicker columns={columns} target={target} onChange={onTarget} />
      <p className="text-sm font-medium">{summary}</p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {features.map((column) => (
          <ColumnBox key={column} column={column} checked={selected.includes(column)} onToggle={onToggle} />
        ))}
      </div>
      <InteractionsSwitch on={interactions} onChange={onInteractions} />
      <TooFew show={selected.length < MIN_COLUMNS} />
      <Recorded show={recorded} />
    </div>
  );
}

/** What completing the stage stores: the choice, and when it was made. */
function stageRecord(selection: Selection) {
  const choice = choiceOf(selection.features, selection.selected);
  return { ...choice, targetColumn: selection.target, createInteractions: selection.interactions, timestamp: new Date().toISOString() };
}

interface Edited {
  datasetId: string | undefined;
  names: string[];
}

interface EditedSwitch {
  datasetId: string | undefined;
  on: boolean;
}

interface Selection {
  /** The columns the model may learn from: every column but the target. */
  features: string[];
  selected: string[];
  target: string;
  setTarget(column: string): void;
  toggle(column: string): void;
  interactions: boolean;
  setInteractions(on: boolean): void;
}

/** The user's edits on top of where the stage starts; they reset with the dataset. */
function useSelection(
  datasetId: string | undefined,
  columns: string[],
  recorded: ColumnChoice | null,
  recordedInteractions: boolean,
  recordedColumn: string,
): Selection {
  const [edited, setEdited] = useState<Edited | null>(null);
  const [switchEdit, setSwitchEdit] = useState<EditedSwitch | null>(null);
  const { target, setTarget } = useTargetChoice(datasetId, recordedColumn);
  const features = columns.filter((column) => column !== target);
  const mine = edited !== null && edited.datasetId === datasetId;
  const current = mine ? edited.names : startingSelection(columns, recorded);
  const toggle = (column: string) => {
    const names = current.includes(column) ? current.filter((name) => name !== column) : [...current, column];
    setEdited({ datasetId, names });
  };
  const switchIsMine = switchEdit !== null && switchEdit.datasetId === datasetId;
  const interactions = switchIsMine ? switchEdit.on : recordedInteractions;
  const setInteractions = (on: boolean) => setSwitchEdit({ datasetId, on });
  const selected = features.filter((column) => current.includes(column));
  return { features, selected, target, setTarget, toggle, interactions, setInteractions };
}

/** Whether the stage holds this selection; saves it as it is made, so Continue is the one confirmation. */
function useSavedChoice(
  selection: Selection,
  stageData: unknown,
  recorded: ColumnChoice | null,
  save: (stage: WorkflowStage, data: unknown) => void,
): boolean {
  const saved =
    sameChoice(recorded, selection.selected) &&
    interactionsOn(stageData) === selection.interactions &&
    recordedTarget(stageData) === selection.target;
  const complete = Boolean(selection.target) && selection.selected.length >= MIN_COLUMNS;
  const key = [selection.target, selection.interactions, ...selection.selected].join('\u0000');
  useEffect(() => {
    if (!saved && complete) save(WorkflowStage.FEATURE_ENGINEERING, stageRecord(selection));
    // The key stands for the selection; saving on a new object identity would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saved, complete, key]);
  return saved;
}

interface ChoiceBodyProps {
  loading: boolean;
  columns: string[];
  selection: Selection;
  recorded: boolean;
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
      features={selection.features}
      selected={selection.selected}
      target={selection.target}
      interactions={selection.interactions}
      recorded={props.recorded}
      onToggle={selection.toggle}
      onTarget={selection.setTarget}
      onInteractions={selection.setInteractions}
    />
  );
}

/**
 * Feature Engineering stage: which of the dataset's columns the model may learn from.
 *
 * The columns come from the dataset record itself, the same read the Model
 * Training stage uses. Recording the choice completes the stage; training then
 * leaves the unselected columns out (`feature_config.exclude_columns`, #969), and
 * tries interaction features when the switch is on (`create_interactions`, #974).
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
  const stageData = state.stageData[WorkflowStage.FEATURE_ENGINEERING];
  const recorded = recordedChoice(stageData);
  const selection = useSelection(datasetId, columns, recorded, interactionsOn(stageData), recordedTarget(stageData));
  const isRecorded = useSavedChoice(selection, stageData, recorded, completeStage);
  const goToUpload = () => router.push('/upload');

  if (!datasetId) return <NoDataset onUpload={goToUpload} />;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="bg-card rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
          <HugeiconsIcon icon={SparklesIcon} className="w-6 h-6 text-warning" />
          Feature Engineering
        </h1>
        <ChoiceBody
          loading={load.loading}
          columns={columns}
          selection={selection}
          recorded={isRecorded}
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
