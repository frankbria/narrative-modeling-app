import React, { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { modelService } from '@/lib/services/model';

/**
 * The columns training left out of the model, and a way to put one back (#841).
 *
 * Training leaves out columns that read as per-row identifiers (#806) or as
 * dates (#840), and columns with no values (#911). The first two are judged by
 * rule, and a real feature can match a rule, so each can be kept: retraining
 * sends them as `feature_config.keep_columns`. An empty column cannot be kept.
 */

interface Exclusions {
  identifiers: string[];
  dates: string[];
  empty: string[];
}

function listed(columns: string[] | undefined): string[] {
  return columns ?? [];
}

async function loadExclusions(modelId: string): Promise<Exclusions> {
  const { dataset } = await modelService.getModelReport(modelId);
  return {
    identifiers: listed(dataset.excluded_columns),
    dates: listed(dataset.excluded_date_columns),
    empty: listed(dataset.excluded_empty_columns),
  };
}

function count(exclusions: Exclusions): number {
  return exclusions.identifiers.length + exclusions.dates.length + exclusions.empty.length;
}

interface KeepBoxProps {
  column: string;
  checked: boolean;
  onToggle(column: string): void;
}

function KeepBox(props: KeepBoxProps) {
  const { column, checked, onToggle } = props;
  const toggle = () => onToggle(column);
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={checked} onChange={toggle} aria-label={`Keep ${column}`} />
      <span className="font-mono">{column}</span>
    </label>
  );
}

interface KeepableGroupProps {
  title: string;
  hint: string;
  columns: string[];
  keep: string[];
  onToggle(column: string): void;
}

function KeepableGroup(props: KeepableGroupProps) {
  const { columns, keep, onToggle } = props;
  if (columns.length === 0) return null;
  return (
    <div>
      <p className="text-sm font-medium text-foreground">{props.title}</p>
      <p className="text-xs text-muted-foreground mb-1">{props.hint}</p>
      <div className="space-y-1">
        {columns.map((column) => (
          <KeepBox key={column} column={column} checked={keep.includes(column)} onToggle={onToggle} />
        ))}
      </div>
    </div>
  );
}

function EmptyGroup(props: { columns: string[] }) {
  const { columns } = props;
  if (columns.length === 0) return null;
  return (
    <div data-testid="excluded-empty">
      <p className="text-sm font-medium text-foreground">No values</p>
      <p className="text-xs text-muted-foreground mb-1">
        Nothing can be learned from a column with no values, so these cannot be kept.
      </p>
      <p className="text-sm font-mono">{columns.join(', ')}</p>
    </div>
  );
}

function toggled(keep: string[], column: string): string[] {
  return keep.includes(column) ? keep.filter((c) => c !== column) : [...keep, column];
}

export interface ExcludedColumnsPanelProps {
  modelId: string;
  onRetrain(columns: string[]): void;
}

export function ExcludedColumnsPanel(props: ExcludedColumnsPanelProps) {
  const { modelId, onRetrain } = props;
  // A report that cannot be loaded leaves the panel out; the run's result stands without it.
  const { data } = useAsyncData(() => loadExclusions(modelId), [modelId]);
  const [keep, setKeep] = useState<string[]>([]);
  const toggle = (column: string) => setKeep((current) => toggled(current, column));
  const retrain = () => onRetrain(keep);
  if (!data || count(data) === 0) return null;
  return (
    <div data-testid="excluded-columns" className="border border-border rounded-lg p-3 space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-foreground">Columns left out of the model</h3>
        <p className="text-sm text-muted-foreground">
          These were not used as features. Tick one to keep it and train again.
        </p>
      </div>
      <KeepableGroup
        title="Read as identifiers"
        hint="Unique on nearly every row, like a customer ID."
        columns={data.identifiers}
        keep={keep}
        onToggle={toggle}
      />
      <KeepableGroup
        title="Read as dates"
        hint="A kept date is treated as a category, one per distinct date."
        columns={data.dates}
        keep={keep}
        onToggle={toggle}
      />
      <EmptyGroup columns={data.empty} />
      <button
        type="button"
        data-testid="retrain-keeping"
        onClick={retrain}
        disabled={keep.length === 0}
        className="px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:text-muted-foreground disabled:cursor-not-allowed"
      >
        <RefreshCw className="w-4 h-4" />
        Retrain keeping {keep.length} column{keep.length === 1 ? '' : 's'}
      </button>
    </div>
  );
}
