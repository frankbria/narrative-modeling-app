import React from 'react';
import { AlertTriangle, CheckCircle } from 'lucide-react';
import type { InputWarning, PredictResponse } from '@/lib/services/model';

/** The result card of a single prediction: the value and what qualifies it. */

const WARNING_BOX =
  'mt-2 flex gap-2 rounded-md border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 p-2 text-sm text-amber-800 dark:text-amber-200';

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
      <AlertTriangle className="w-4 h-4 shrink-0" />
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
      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
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
          <span>{prediction.class_labels?.[idx] ?? `Class ${idx}`}:</span>
          <span className="font-medium">{(prob * 100).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

function Contribution(props: { value: number }) {
  const { value } = props;
  const up = value >= 0;
  const colour = up ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300';
  return (
    <span className={`font-medium ${colour}`}>
      {up ? '+' : ''}
      {value.toFixed(3)}
    </span>
  );
}

/** Plain-language explanation + feature contributions (#83). */
function Explanation(props: { prediction: PredictResponse }) {
  const explanation = props.prediction.explanations?.[0];
  if (!explanation) return null;
  return (
    <div
      data-testid="prediction-explanation"
      className="mt-4 border-t border-green-200 dark:border-green-900 pt-3"
    >
      <p className="text-sm font-medium text-foreground mb-1">What drove this prediction</p>
      <p className="text-sm text-muted-foreground mb-2">{explanation.explanation_text}</p>
      <div className="space-y-1">
        {explanation.top_features.map((f) => (
          <div key={f.feature_name} className="flex justify-between text-sm">
            <span>{f.feature_name}</span>
            <Contribution value={f.contribution} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function PredictionResult(props: { prediction: PredictResponse }) {
  const { prediction } = props;
  return (
    <div
      data-testid="prediction-result"
      className="prediction-output mt-6 p-4 bg-green-50 dark:bg-green-950/40 rounded-lg border border-green-200 dark:border-green-900"
    >
      <h4 className="font-semibold mb-2 flex items-center gap-2">
        <CheckCircle className="w-5 h-5 text-green-600" />
        Prediction Result
      </h4>
      <div
        data-testid="prediction-value"
        className="prediction-value text-2xl font-bold text-foreground"
      >
        {String(prediction.predictions?.[0])}
      </div>
      <Confidence prediction={prediction} />
      <LowConfidence prediction={prediction} />
      <InputWarnings warnings={prediction.input_warnings?.[0]} />
      <Interval prediction={prediction} />
      <Probabilities prediction={prediction} />
      <Explanation prediction={prediction} />
    </div>
  );
}
