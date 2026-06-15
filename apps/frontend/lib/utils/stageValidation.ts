/**
 * Stage validation + navigation helpers for the 8-stage workflow (issue #88).
 *
 * Centralizes three concerns that used to be scattered across stage pages and
 * `WorkflowContext`:
 *  - **Route-aware URL building** (`buildStageUrl`). Stage routes are not
 *    uniform: `data_profiling` (`/explore/[id]`), `model_evaluation`
 *    (`/evaluate/[datasetId]`) and `prediction` (`/predict/[datasetId]`) are
 *    deep-linked with the dataset id, while the rest render at their bare route
 *    and read the dataset id from context. Pushing `/{route}/{datasetId}`
 *    blindly (the previous behaviour) 404'd `/prepare/{id}` and mis-routed
 *    `/model/{id}` to the model *detail* viewer.
 *  - **Ordering helpers** (`getNextStage`, `getPreviousStage`,
 *    `getFirstIncompletePrerequisite`) driven by `WORKFLOW_STAGES`.
 *  - **Completion validation** (`validateStageCompletion`) so a "Continue" CTA
 *    can block a transition until the current stage actually has the data the
 *    next stage needs.
 */

import { WorkflowStage, WORKFLOW_STAGES, StageConfig } from '@/lib/types/workflow';

export interface StageValidationResult {
  isValid: boolean;
  errors: string[];
}

/**
 * Stages whose route carries the dataset id as a path segment (a deep-link
 * page). Every other stage renders at its bare route and reads the dataset id
 * from `WorkflowContext`.
 */
const DATASET_PARAM_STAGES = new Set<WorkflowStage>([
  WorkflowStage.DATA_PROFILING,
  WorkflowStage.MODEL_EVALUATION,
  WorkflowStage.PREDICTION,
]);

/** Resolve the `StageConfig` for a stage (or `null` if unknown). */
export function getStageConfig(stage: WorkflowStage): StageConfig | null {
  return WORKFLOW_STAGES.find((s) => s.id === stage) ?? null;
}

/**
 * Build the in-app navigation URL for a stage. Appends the dataset id only for
 * stages whose route expects it; otherwise returns the bare route.
 */
export function buildStageUrl(stage: WorkflowStage, datasetId?: string): string {
  const config = getStageConfig(stage);
  if (!config) return '/';
  if (datasetId && DATASET_PARAM_STAGES.has(stage)) {
    return `${config.route}/${datasetId}`;
  }
  return config.route;
}

/** Index of a stage in the canonical workflow order (`-1` if unknown). */
export function getStageIndex(stage: WorkflowStage): number {
  return WORKFLOW_STAGES.findIndex((s) => s.id === stage);
}

/** The stage immediately after `stage`, or `null` if it is the last stage. */
export function getNextStage(stage: WorkflowStage): StageConfig | null {
  const index = getStageIndex(stage);
  if (index === -1 || index >= WORKFLOW_STAGES.length - 1) return null;
  return WORKFLOW_STAGES[index + 1];
}

/** The stage immediately before `stage`, or `null` if it is the first stage. */
export function getPreviousStage(stage: WorkflowStage): StageConfig | null {
  const index = getStageIndex(stage);
  if (index <= 0) return null;
  return WORKFLOW_STAGES[index - 1];
}

/**
 * The first required stage (in workflow order) that is not yet completed — i.e.
 * where a user who landed on a gated stage should be redirected. Returns `null`
 * when every prerequisite is already complete.
 */
export function getFirstIncompletePrerequisite(
  stage: WorkflowStage,
  completedStages: Set<WorkflowStage>
): WorkflowStage | null {
  const index = getStageIndex(stage);
  if (index <= 0) return null;
  // The workflow is a strict linear chain, so every stage before `stage` is a
  // (transitive) prerequisite. Return the earliest one not yet completed so the
  // user is redirected straight to the right step rather than cascading back
  // through several gated pages.
  for (let i = 0; i < index; i++) {
    if (!completedStages.has(WORKFLOW_STAGES[i].id)) {
      return WORKFLOW_STAGES[i].id;
    }
  }
  return null;
}

/**
 * Validate that a stage has the data the next stage relies on. Lenient by
 * design: stages that are purely informational (profiling, preparation,
 * evaluation, prediction) always pass, while stages that gate downstream work
 * (loading, feature engineering, training, deployment) enforce the minimum
 * artifact. `stageData` is the per-stage payload recorded by `completeStage`.
 */
export function validateStageCompletion(
  stage: WorkflowStage,
  stageData?: unknown
): StageValidationResult {
  const data = (stageData ?? {}) as Record<string, unknown>;
  const errors: string[] = [];

  switch (stage) {
    case WorkflowStage.DATA_LOADING:
      if (!data.datasetId) {
        errors.push('Upload a dataset before continuing.');
      }
      break;
    case WorkflowStage.FEATURE_ENGINEERING: {
      const selected = data.selectedFeatures;
      if (!Array.isArray(selected) || selected.length < 2) {
        errors.push('Select at least 2 features for effective modeling.');
      }
      break;
    }
    case WorkflowStage.MODEL_TRAINING:
      if (!data.modelId) {
        errors.push('Train a model before continuing.');
      }
      break;
    case WorkflowStage.DEPLOYMENT:
      if (!data.deploymentId) {
        errors.push('Deploy the model before continuing.');
      }
      break;
    // DATA_PROFILING, DATA_PREPARATION, MODEL_EVALUATION, PREDICTION are
    // informational gates — completing the page is enough.
    default:
      break;
  }

  return { isValid: errors.length === 0, errors };
}
