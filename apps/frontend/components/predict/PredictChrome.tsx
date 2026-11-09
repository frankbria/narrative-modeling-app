import React from 'react';
import { HugeiconsIcon } from '@hugeicons/react';
import { Alert02Icon, FileEditIcon, Target02Icon } from '@hugeicons/core-free-icons';

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
      className="mb-4 p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-sm text-destructive flex items-center gap-2"
    >
      <HugeiconsIcon icon={Alert02Icon} className="w-4 h-4 shrink-0" />
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
    ? 'border-primary bg-primary/10'
    : 'border-border hover:border-muted-foreground';
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
          icon={<HugeiconsIcon icon={Target02Icon} className="w-8 h-8 text-primary mx-auto mb-2" />}
          title="Single Prediction"
          hint="Enter values manually for one prediction"
        />
        <ModeButton
          testId="batch-prediction-link"
          active={mode === 'batch'}
          onSelect={selectBatch}
          icon={<HugeiconsIcon icon={FileEditIcon} className="w-8 h-8 text-success mx-auto mb-2" />}
          title="Batch Prediction"
          hint="Upload a CSV file for multiple predictions"
        />
      </div>
    </div>
  );
}
