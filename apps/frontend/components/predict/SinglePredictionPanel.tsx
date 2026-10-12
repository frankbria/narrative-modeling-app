import React from 'react';
import { Send } from 'lucide-react';
import type { ModelFeatureDescriptor, PredictResponse } from '@/lib/services/model';
import { PredictionResult } from './PredictionResult';
import type { FieldValidationError, FieldValues } from './predictionForm';

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
  /** The field's validation error, if it has one. */
  error?: string;
  /** An error is shown only once the field is touched, so a pristine form has none. */
  touched?: boolean;
  onChange(name: string, value: string): void;
  onTouched(name: string): void;
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
  const { feature, index, value, onChange, onTouched } = props;
  const error = (props.touched && props.error) || null;
  const attrs: FieldAttrs = {
    ...fieldAttrs(feature, index, error),
    value,
    onBlur: () => onTouched(feature.name),
    onChange: (e) => onChange(feature.name, e.target.value),
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

type TouchedFields = Record<string, boolean>;

function errorsByName(validationErrors: FieldValidationError[]) {
  const errors: Record<string, string> = {};
  for (const { name, error } of validationErrors) {
    if (error) errors[name] = error;
  }
  return errors;
}

export interface SinglePredictionPanelProps {
  features: ModelFeatureDescriptor[];
  values: FieldValues;
  setValues: React.Dispatch<React.SetStateAction<FieldValues>>;
  touched: TouchedFields;
  setTouched: React.Dispatch<React.SetStateAction<TouchedFields>>;
  validationErrors: FieldValidationError[];
  prediction: PredictResponse | null;
  loading: boolean;
  formValid: boolean;
  onSubmit: VoidFunction;
}

export function SinglePredictionPanel(props: SinglePredictionPanelProps) {
  const { features, values, touched, setValues, setTouched } = props;
  const errors = errorsByName(props.validationErrors);
  const onChange = (name: string, value: string) =>
    setValues((prev) => ({ ...prev, [name]: value }));
  const onTouched = (name: string) => setTouched((prev) => ({ ...prev, [name]: true }));
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
            error={errors[feature.name]}
            touched={touched[feature.name]}
            onChange={onChange}
            onTouched={onTouched}
          />
        ))}
      </div>
      {props.prediction && <PredictionResult prediction={props.prediction} />}
      <SubmitButton loading={props.loading} formValid={props.formValid} onSubmit={props.onSubmit} />
    </div>
  );
}
