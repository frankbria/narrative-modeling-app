import React from 'react';
import { AlertTriangle, FileText, Target } from 'lucide-react';

/** The prediction page's frame: its error banner and the single/batch switch. */

export type PredictionMode = 'single' | 'batch';

/**
 * Prediction failures are the user's action; a schema-load failure is the page's.
 * Tracked apart, displayed as one value, the user's action first.
 */
export function ErrorBanner(props: { actionError: string | null; featuresError: string | null }) {
  const error = props.actionError ?? props.featuresError;
  if (!error) return null;
  return (
    <div
      data-testid="prediction-error"
      className="mb-4 p-3 rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 text-sm text-red-700 dark:text-red-300 flex items-center gap-2"
    >
      <AlertTriangle className="w-4 h-4 shrink-0" />
      <span>{error}</span>
    </div>
  );
}

interface ModeButtonProps {
  testId: string;
  active: boolean;
  onSelect: VoidFunction;
  icon: React.ReactNode;
  title: string;
  hint: string;
}

function ModeButton(props: ModeButtonProps) {
  const { active } = props;
  const colour = active
    ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40'
    : 'border-border hover:border-gray-400';
  return (
    <button
      type="button"
      data-testid={props.testId}
      onClick={props.onSelect}
      className={`p-4 border-2 rounded-lg transition-colors ${colour}`}
    >
      {props.icon}
      <h3 className="font-semibold">{props.title}</h3>
      <p className="text-sm text-muted-foreground mt-1">{props.hint}</p>
    </button>
  );
}

export function ModeToggle(props: {
  mode: PredictionMode;
  setMode: React.Dispatch<React.SetStateAction<PredictionMode>>;
}) {
  const { mode, setMode } = props;
  const selectSingle = () => setMode('single');
  const selectBatch = () => setMode('batch');
  return (
    <div className="mb-6">
      <div className="grid grid-cols-2 gap-4">
        <ModeButton
          testId="single-prediction-link"
          active={mode === 'single'}
          onSelect={selectSingle}
          icon={<Target className="w-8 h-8 text-blue-600 mx-auto mb-2" />}
          title="Single Prediction"
          hint="Enter values manually for one prediction"
        />
        <ModeButton
          testId="batch-prediction-link"
          active={mode === 'batch'}
          onSelect={selectBatch}
          icon={<FileText className="w-8 h-8 text-green-600 mx-auto mb-2" />}
          title="Batch Prediction"
          hint="Upload a CSV file for multiple predictions"
        />
      </div>
    </div>
  );
}
