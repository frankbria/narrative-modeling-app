import React from 'react';
import { AlertCircle, Info, PlayCircle, Zap } from 'lucide-react';
import { TrainingModeSelector } from '@/components/TrainingModeSelector';
import type { TrainingMode } from '@/lib/services/model';

/** The configuration view: what a run needs before it starts, and why the last one ended. */

const TONES = {
  red: {
    box: 'bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-900',
    icon: 'text-red-600',
    text: 'text-red-800 dark:text-red-200',
  },
  blue: {
    box: 'bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-900',
    icon: 'text-blue-600',
    text: 'text-blue-800 dark:text-blue-200',
  },
  yellow: {
    box: 'bg-yellow-50 dark:bg-yellow-950/40 border-yellow-200 dark:border-yellow-900',
    icon: 'text-yellow-600',
    text: 'text-yellow-800 dark:text-yellow-200',
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
    <div className="p-4 bg-indigo-50 dark:bg-indigo-950/40 rounded-lg border border-indigo-200 dark:border-indigo-900 flex items-start gap-3">
      <Zap className="w-5 h-5 text-indigo-500 mt-0.5" />
      <div className="text-sm text-indigo-900 dark:text-indigo-200">
        <p className="font-semibold">AI-guided AutoML</p>
        <p className="mt-1 text-indigo-800 dark:text-indigo-200">
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
        className="w-full p-2 border border-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
    ? 'bg-blue-600 text-white hover:bg-blue-700'
    : 'bg-gray-300 text-muted-foreground cursor-not-allowed';
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
