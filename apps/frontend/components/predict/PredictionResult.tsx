import React, { useEffect, useRef } from 'react';
import { HugeiconsIcon } from '@/components/ui/icon';
import { Alert02Icon, CheckmarkCircle01Icon } from '@hugeicons/core-free-icons';
import { describeDriver, driverText } from './driverLabel';
import { classLabel } from '@/lib/evaluation/classLabels';
import type { InputWarning, PredictResponse } from '@/lib/services/model';

/** The result card of a single prediction: the value and what qualifies it. */

const WARNING_BOX =
  'mt-2 flex gap-2 rounded-md border border-warning/30 bg-warning/10 p-2 text-sm text-warning';

const WARNING_TEXT: Record<InputWarning, string> = {
  unseen: 'this value was not in the training data',
  missing: 'no value was given, so a typical training value was used',
};

function Confidence(props: { prediction: PredictResponse }) {
  const { prediction } = props;
  const confidence = prediction.confidence?.[0];
  if (confidence == null) return null;
  return (
    <div className="mt-2">
      <span className="text-sm text-muted-foreground">Confidence: </span>
      <span data-testid="confidence-score" className="confidence font-medium">
        {(confidence * 100).toFixed(1)}%
      </span>
      {prediction.is_calibrated && (
        <span className="ml-2 text-xs text-muted-foreground">(calibrated)</span>
      )}
    </div>
  );
}

function LowConfidence(props: { prediction: PredictResponse }) {
  const { prediction } = props;
  if (!prediction.low_confidence?.[0]) return null;
  const threshold = prediction.confidence_threshold;
  return (
    <div data-testid="low-confidence-warning" className={`${WARNING_BOX} items-center`}>
      <HugeiconsIcon icon={Alert02Icon} className="w-4 h-4 shrink-0" />
      <span>
        Low confidence — this prediction is below the{' '}
        {threshold != null ? `${(threshold * 100).toFixed(0)}%` : 'recommended'} confidence
        threshold. Treat it with caution.
      </span>
    </div>
  );
}

/**
 * Inputs the model did not learn this value from (#838). The backend names each
 * column and why; a clean record sends an empty object and nothing is shown.
 */
export function InputWarnings(props: { warnings?: Record<string, InputWarning> | null }) {
  const entries = Object.entries(props.warnings ?? {});
  if (entries.length === 0) return null;
  return (
    <div data-testid="input-warnings" className={`${WARNING_BOX} items-start`}>
      <HugeiconsIcon icon={Alert02Icon} className="w-4 h-4 shrink-0 mt-0.5" />
      <div>
        <p className="font-medium">
          The model had not seen some of these inputs. Treat the prediction with caution.
        </p>
        <ul className="mt-1 list-disc pl-4">
          {entries.map(([column, reason]) => (
            <li key={column} data-testid={`input-warning-${column}`}>
              <span className="font-medium">{column}</span>: {WARNING_TEXT[reason] ?? reason}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/** Regression prediction interval (#83). */
function Interval(props: { prediction: PredictResponse }) {
  const interval = props.prediction.prediction_intervals?.[0];
  if (!interval) return null;
  return (
    <div className="mt-2 text-sm text-foreground">
      <span className="text-muted-foreground">Estimated range: </span>
      <span data-testid="prediction-interval" className="font-medium">
        {interval[0].toFixed(2)} – {interval[1].toFixed(2)}
      </span>
    </div>
  );
}

function Probabilities(props: { prediction: PredictResponse }) {
  const { prediction } = props;
  const probabilities = prediction.probabilities?.[0];
  if (!probabilities) return null;
  return (
    <div className="mt-3 space-y-1">
      <p className="text-sm text-muted-foreground">Class Probabilities:</p>
      {probabilities.map((prob, idx) => (
        <div key={idx} className="flex justify-between text-sm">
          <span>{classLabel(prediction.class_labels?.[idx] ?? `Class ${idx}`, prediction.model_info.target_column)}:</span>
          <span className="font-medium">{(prob * 100).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

const EFFECT_TEXT = {
  true: 'pushes the result up',
  false: 'pushes the result down',
};

/** Which way the input pushed. The size is a model-internal number, so it is not shown. */
function Contribution(props: { value: number }) {
  const up = props.value >= 0;
  const colour = up ? 'text-success' : 'text-destructive';
  return <span className={`font-medium ${colour}`}>{EFFECT_TEXT[`${up}`]}</span>;
}

/** What drove the prediction, in the dataset's own column names and values (#83, #1170). */
// `columns` are the form's raw inputs: the response's `feature_names` are the model's
// engineered inputs (one-hot `<column>_<value>`), so they cannot split a name apart.
function Explanation(props: { prediction: PredictResponse; columns: string[] }) {
  const { prediction, columns } = props;
  const explanation = prediction.explanations?.[0];
  if (!explanation) return null;
  return (
    <div data-testid="prediction-explanation" className="mt-4 border-t border-border pt-3">
      <p className="text-sm font-medium text-foreground mb-2">What drove this prediction</p>
      <div className="space-y-1">
        {explanation.top_features.map((f) => (
          <div key={f.feature_name} className="flex justify-between gap-4 text-sm">
            <span>{driverText(describeDriver(f.feature_name, columns), f.feature_value)}</span>
            <Contribution value={f.contribution} />
          </div>
        ))}
      </div>
    </div>
  );
}

/** A new result is brought into view: the form above it is long. */
function useScrollIntoView(prediction: PredictResponse) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
  }, [prediction]);
  return ref;
}

// JSON spells a boolean `true` where the backend's class label says `True` (and `1` for `1.0`).
const sameClass = (label: string, raw: unknown) =>
  label.toLowerCase() === String(raw).toLowerCase() || Number(label) === Number(raw);

/** The prediction spelled as its class label, so the result and the probability rows agree. */
function asClassLabel(raw: unknown, labels: string[] | null | undefined) {
  return labels?.find((label) => sameClass(label, raw)) ?? String(raw);
}

/** The predicted value; a class is named against the target, a quantity stays bare (#1187). */
function predictedText(prediction: PredictResponse) {
  const value = asClassLabel(prediction.predictions?.[0], prediction.class_labels);
  return prediction.model_info.problem_type.includes('classification') ? classLabel(value, prediction.model_info.target_column) : value;
}

export function PredictionResult(props: { prediction: PredictResponse; columns: string[] }) {
  const { prediction, columns } = props;
  const ref = useScrollIntoView(prediction);
  return (
    <div
      ref={ref}
      data-testid="prediction-result"
      className="prediction-output mt-6 p-4 bg-card rounded-lg border border-border"
    >
      <h4 className="font-semibold mb-2 flex items-center gap-2">
        <HugeiconsIcon icon={CheckmarkCircle01Icon} className="w-5 h-5 text-primary" />
        Predicted {prediction.model_info.target_column}
      </h4>
      <div
        data-testid="prediction-value"
        className="prediction-value inline-block rounded px-2 text-2xl font-bold bg-highlight text-highlight-foreground"
      >
        {predictedText(prediction)}
      </div>
      <Confidence prediction={prediction} />
      <LowConfidence prediction={prediction} />
      <InputWarnings warnings={prediction.input_warnings?.[0]} />
      <Interval prediction={prediction} />
      <Probabilities prediction={prediction} />
      <Explanation prediction={prediction} columns={columns} />
    </div>
  );
}
