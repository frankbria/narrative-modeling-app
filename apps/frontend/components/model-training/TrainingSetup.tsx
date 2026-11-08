import React from 'react';
import { AlertCircle, Info, PlayCircle, Zap } from 'lucide-react';
import { TrainingModeSelector } from '@/components/TrainingModeSelector';
import type { TrainingMode } from '@/lib/services/model';

/** The configuration view: what a run needs before it starts, and why the last one ended. */

const TONES = {
  red: {
    box: 'bg-destructive/10 border-destructive/30',
    icon: 'text-destructive',
    text: 'text-destructive',
  },
  blue: {
    box: 'bg-primary/10 border-primary/30',
    icon: 'text-primary',
    text: 'text-primary',
  },
  yellow: {
    box: 'bg-warning/10 border-warning/30',
    icon: 'text-warning',
    text: 'text-warning',
  },
};

interface NoticeProps {
  tone: keyof typeof TONES;
  Icon: typeof AlertCircle;
  title: string;
  text: string;
  className: string;
}

function Notice(props: NoticeProps) {
  const { Icon } = props;
  const tone = TONES[props.tone];
  return (
    <div className={`${props.className} p-3 rounded-lg border flex items-start gap-2 ${tone.box}`}>
      <Icon className={`w-5 h-5 mt-0.5 ${tone.icon}`} />
      <div className={`text-sm ${tone.text}`}>
        <p className="font-semibold">{props.title}</p>
        <p>{props.text}</p>
      </div>
    </div>
  );
}

/**
 * Shown above the form so they stay visible after a failure or a cancellation
 * returns the user to the configuration view.
 */
export function TrainingNotices(props: { error: string | null; cancelled: boolean }) {
  const { error, cancelled } = props;
  return (
    <>
      {error && (
        <Notice tone="red" Icon={AlertCircle} title="Training failed" text={error} className="mb-6" />
      )}
      {cancelled && (
        <Notice
          tone="blue"
          Icon={Info}
          title="Training cancelled"
          text="The training run was stopped. You can start a new run below."
          className="mb-6"
        />
      )}
    </>
  );
}

// An element, not a component: it takes nothing and never changes.
const AUTO_ML_INTRO = (
    <div className="p-4 bg-primary/10 rounded-lg border border-primary/30 flex items-start gap-3">
      <Zap className="w-5 h-5 text-primary mt-0.5" />
      <div className="text-sm text-primary">
        <p className="font-semibold">AI-guided AutoML</p>
        <p className="mt-1 text-primary">
          We automatically detect whether this is a classification or
          regression problem, train and cross-validate several algorithms
          (Logistic/Linear Regression, Random Forest, XGBoost and more),
          and pick the best model — with an explanation of why.
        </p>
      </div>
    </div>
);

interface TargetColumnProps {
  columns: string[];
  value: string;
  onChange(column: string): void;
}

function TargetColumn(props: TargetColumnProps) {
  const { columns, value, onChange } = props;
  const change = (e: React.ChangeEvent<HTMLSelectElement>) => onChange(e.target.value);
  return (
    <div>
      <label className="block text-sm font-medium mb-2">Target Column</label>
      <select
        value={value}
        onChange={change}
        className="w-full p-2 border border-border rounded-lg focus:ring-2 focus:ring-ring focus:border-primary"
      >
        <option value="">Select target column...</option>
        {columns.map((column) => (
          <option key={column} value={column}>
            {column}
          </option>
        ))}
      </select>
      <p className="text-xs text-muted-foreground mt-1">
        The column you want the model to predict.
      </p>
    </div>
  );
}

function StartButton(props: { ready: boolean; onStart: VoidFunction }) {
  const { ready, onStart } = props;
  const colour = ready
    ? 'bg-primary text-primary-foreground hover:bg-primary/90'
    : 'bg-muted text-muted-foreground cursor-not-allowed';
  return (
    <div className="flex justify-end pt-4">
      <button
        onClick={onStart}
        disabled={!ready}
        className={`px-6 py-2 rounded-lg font-medium flex items-center gap-2 ${colour}`}
      >
        <PlayCircle className="w-5 h-5" />
        Start Training
      </button>
    </div>
  );
}

export interface TrainingSetupProps {
  columns: string[];
  targetColumn: string;
  onTargetChange(column: string): void;
  mode: TrainingMode;
  onModeChange(mode: TrainingMode): void;
  recommendedMode: TrainingMode | undefined;
  reason: string | undefined;
  onStart: VoidFunction;
}

/**
 * AutoML auto-detects the problem type and compares several algorithms, so the
 * only required input is the target column. The training mode (issue #101)
 * tunes how many algorithms run and the time budget. Back / Continue live in
 * the shared StageNavigation footer.
 */
export function TrainingSetup(props: TrainingSetupProps) {
  const { targetColumn } = props;
  return (
    <div className="space-y-6">
      {AUTO_ML_INTRO}
      <TargetColumn columns={props.columns} value={targetColumn} onChange={props.onTargetChange} />
      <TrainingModeSelector
        value={props.mode}
        onChange={props.onModeChange}
        recommendedMode={props.recommendedMode}
        reason={props.reason}
      />
      {!targetColumn && (
        <Notice
          tone="yellow"
          Icon={AlertCircle}
          title="Target column required"
          text="Please select the column you want to predict."
          className=""
        />
      )}
      <StartButton ready={Boolean(targetColumn)} onStart={props.onStart} />
    </div>
  );
}
