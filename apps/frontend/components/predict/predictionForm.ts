import { useEffect, useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { WorkflowStage } from '@/lib/types/workflow';
import {
  modelService,
  type ModelFeatureDescriptor,
  type PredictResponse,
} from '@/lib/services/model';

/** The prediction form: its fields come from the model's schema, then the user edits them. */

export type FieldValues = Record<string, string>;

/** A field that currently fails validation. */
export interface FieldValidationError {
  name: string;
  error: string | null;
}

/** What the page shares with both prediction modes. */
export interface PredictionContext {
  modelId: string | null | undefined;
  setLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setActionError: React.Dispatch<React.SetStateAction<string | null>>;
  /** Marks the prediction stage complete the first time a prediction succeeds. */
  completePrediction(details: Record<string, unknown>): void;
}

export function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

function defaultValue(feature: ModelFeatureDescriptor): string {
  if (feature.type === 'categorical' && feature.options?.length) return String(feature.options[0]);
  return '';
}

function isBlank(raw: string | null | undefined): boolean {
  return raw === undefined || raw === null || String(raw).trim() === '';
}

function fieldError(feature: ModelFeatureDescriptor, values: FieldValues): string | null {
  const raw = values[feature.name];
  if (isBlank(raw)) return 'Required';
  if (feature.type === 'number' && Number.isNaN(Number(raw))) return 'Must be a number';
  return null;
}

function validate(features: ModelFeatureDescriptor[], values: FieldValues): FieldValidationError[] {
  return features
    .map((feature) => ({ name: feature.name, error: fieldError(feature, values) }))
    .filter((entry) => entry.error);
}

function buildRecord(features: ModelFeatureDescriptor[], values: FieldValues) {
  const record: Record<string, string | number> = {};
  for (const feature of features) {
    const raw = values[feature.name];
    record[feature.name] = feature.type === 'number' ? Number(raw) : raw;
  }
  return record;
}

async function loadFeatures(modelId: string) {
  const data = await modelService.getModelFeatures(modelId);
  const defaultInput: FieldValues = {};
  for (const feature of data.features) defaultInput[feature.name] = defaultValue(feature);
  return { features: data.features, defaultInput };
}

const NOTHING_LOADED = { features: [] as ModelFeatureDescriptor[], defaultInput: {} as FieldValues };

interface InputOverride {
  modelId: string;
  values: FieldValues;
}

function currentValues(
  override: InputOverride | null,
  modelId: string | null | undefined,
  defaults: FieldValues,
): FieldValues {
  if (override && override.modelId === modelId) return override.values;
  return defaults;
}

function nextOverride(
  update: React.SetStateAction<FieldValues>,
  values: FieldValues,
  modelId: string | null | undefined,
): InputOverride {
  return {
    modelId: modelId ?? '',
    values: typeof update === 'function' ? update(values) : update,
  };
}

function isComplete(features: ModelFeatureDescriptor[], errors: FieldValidationError[]): boolean {
  return features.length > 0 && errors.length === 0;
}

/**
 * What both prediction modes need from the page. The prediction stage is marked
 * complete the first time a prediction succeeds, and never again.
 */
export function usePredictionContext(
  setLoading: PredictionContext['setLoading'],
  setActionError: PredictionContext['setActionError'],
): PredictionContext {
  const { state, completeStage } = useWorkflow();
  const completePrediction = (details: Record<string, unknown>) => {
    if (state.completedStages.has(WorkflowStage.PREDICTION)) return;
    completeStage(WorkflowStage.PREDICTION, { ...details, timestamp: new Date().toISOString() });
  };
  return { modelId: state.modelId, setLoading, setActionError, completePrediction };
}

/** Sends the user back to training when the stage is open but no model is trained. */
export function useTrainedModelGuard(ready: boolean) {
  const { state, requestStageRedirect } = useWorkflow();
  useEffect(() => {
    // Stage access (with a helpful redirect) is handled by useStageGuard, which
    // also waits for hydration before deciding.
    if (!ready) return;
    if (!state.modelId) {
      // Accessible but no trained model in state — send the user back to train.
      requestStageRedirect(
        WorkflowStage.MODEL_TRAINING,
        'Train a model before making predictions.'
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, state.modelId]);
}

export function usePredictionForm(modelId: string | null | undefined, ready: boolean) {
  const { data, error } = useAsyncData(
    () => loadFeatures(modelId as string),
    [modelId],
    // No errorMessage override: the original surfaced err.message, and only fell
    // back to fixed copy for non-Error throws, which is the hook's default.
    { enabled: ready && !!modelId },
  );
  const { features, defaultInput } = data ?? NOTHING_LOADED;

  // The form is seeded from the model's schema and then edited, so edits are an
  // override tagged with the model they belong to — switching models resets it.
  const [override, setOverride] = useState<InputOverride | null>(null);
  const values = currentValues(override, modelId, defaultInput);
  const setValues: React.Dispatch<React.SetStateAction<FieldValues>> = (update) =>
    setOverride(nextOverride(update, values, modelId));

  const validationErrors = validate(features, values);
  return {
    features,
    values,
    setValues,
    featuresError: error,
    validationErrors,
    formValid: isComplete(features, validationErrors),
  };
}

export type PredictionForm = ReturnType<typeof usePredictionForm>;

export function useSinglePrediction(ctx: PredictionContext, form: PredictionForm) {
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);

  const predict = async () => {
    if (!form.formValid) return;
    ctx.setLoading(true);
    ctx.setActionError(null);
    setPrediction(null);
    try {
      const result = await modelService.predict(ctx.modelId as string, {
        data: [buildRecord(form.features, form.values)],
        include_probabilities: true,
        include_explanations: true,
      });
      setPrediction(result);
      ctx.completePrediction({ firstPrediction: result.predictions?.[0] });
    } catch (err) {
      ctx.setActionError(errorMessage(err, 'Prediction failed'));
    } finally {
      ctx.setLoading(false);
    }
  };

  return { prediction, predict };
}
