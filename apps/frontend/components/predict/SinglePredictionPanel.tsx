import React from 'react';
import { Send } from 'lucide-react';
import type { ModelFeatureDescriptor, PredictResponse } from '@/lib/services/model';
import { PredictionResult } from './PredictionResult';

/** The single-prediction form: one field per raw input feature, then the result. */

const FIELD = 'w-full p-2 border rounded-lg focus:ring-2 focus:ring-blue-500';

/**
 * Index-based ids are inherently ID-safe and unique: a raw name with spaces would
 * break aria-describedby (a space-separated IDREF list), and two names that
 * sanitize alike would collide (#282). data-feature carries the raw name for e2e
 * selectors.
 */
function fieldAttrs(feature: ModelFeatureDescriptor, index: number, error: string | null) {
  const base = { id: `field-${index}`, name: feature.name, 'data-feature': feature.name };
  if (!error) return { ...base, className: `${FIELD} border-border` };
  return {
    ...base,
    'aria-invalid': true,
    'aria-describedby': `field-error-${index}`,
    className: `${FIELD} border-red-400`,
  };
}

interface FeatureFieldProps {
  feature: ModelFeatureDescriptor;
  index: number;
  value: string;
  /** Shown only once the field is touched, so a pristine form has no errors. */
  error: string | null;
  onChange(value: string): void;
  onBlur: VoidFunction;
}

type FieldAttrs = ReturnType<typeof fieldAttrs> & {
  value: string;
  onBlur: VoidFunction;
  onChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>): void;
};

function OptionSelect(props: { attrs: FieldAttrs; options: string[] }) {
  const { attrs, options } = props;
  return (
    <select {...attrs}>
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  );
}

function FieldError(props: { index: number; name: string; error: string | null }) {
  const { index, name, error } = props;
  if (!error) return null;
  return (
    <p
      id={`field-error-${index}`}
      role="alert"
      className="mt-1 text-xs text-red-600"
      data-testid={`field-error-${name}`}
    >
      {error}
    </p>
  );
}

/** A dropdown when the model knows the column's categories, a typed input otherwise. */
function FieldControl(props: { feature: ModelFeatureDescriptor; attrs: FieldAttrs }) {
  const { feature, attrs } = props;
  if (feature.type === 'categorical' && feature.options?.length) {
    return <OptionSelect attrs={attrs} options={feature.options} />;
  }
  return <input {...attrs} type={feature.type === 'number' ? 'number' : 'text'} />;
}

function FeatureField(props: FeatureFieldProps) {
  const { feature, index, value, error, onChange, onBlur } = props;
  const attrs: FieldAttrs = {
    ...fieldAttrs(feature, index, error),
    value,
    onBlur,
    onChange: (e) => onChange(e.target.value),
  };
  return (
    <div>
      <label className="block text-sm font-medium mb-1" htmlFor={attrs.id}>
        {feature.name}
      </label>
      <FieldControl feature={feature} attrs={attrs} />
      <FieldError index={index} name={feature.name} error={error} />
    </div>
  );
}

function SubmitButton(props: { loading: boolean; formValid: boolean; onSubmit: VoidFunction }) {
  const { loading, formValid, onSubmit } = props;
  const enabled = !loading && formValid;
  const colour = enabled
    ? 'bg-blue-600 text-white hover:bg-blue-700'
    : 'bg-gray-300 text-muted-foreground cursor-not-allowed';
  return (
    <button
      type="button"
      data-testid="make-prediction"
      onClick={onSubmit}
      disabled={!enabled}
      className={`w-full py-2 rounded-lg font-medium flex items-center justify-center gap-2 ${colour}`}
    >
      <Send className="w-5 h-5" />
      {loading ? 'Making Prediction...' : 'Make Prediction'}
    </button>
  );
}

export interface SinglePredictionPanelProps {
  features: ModelFeatureDescriptor[];
  values: Record<string, string>;
  touched: Record<string, boolean>;
  /** The current validation error of each field that has one, by feature name. */
  errors: Record<string, string>;
  onChange(name: string, value: string): void;
  onTouched(name: string): void;
  prediction: PredictResponse | null;
  loading: boolean;
  formValid: boolean;
  onSubmit: VoidFunction;
}

export function SinglePredictionPanel(props: SinglePredictionPanelProps) {
  const { features, values, touched, errors, onChange, onTouched } = props;
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-lg">Enter Feature Values</h3>
      <div className="grid grid-cols-2 gap-4">
        {features.map((feature, index) => (
          <FeatureField
            key={feature.name}
            feature={feature}
            index={index}
            value={values[feature.name] ?? ''}
            error={touched[feature.name] ? (errors[feature.name] ?? null) : null}
            onChange={(value) => onChange(feature.name, value)}
            onBlur={() => onTouched(feature.name)}
          />
        ))}
      </div>
      {props.prediction && <PredictionResult prediction={props.prediction} />}
      <SubmitButton loading={props.loading} formValid={props.formValid} onSubmit={props.onSubmit} />
    </div>
  );
}
