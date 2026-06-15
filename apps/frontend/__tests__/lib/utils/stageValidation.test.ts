/**
 * Tests for the stage validation + navigation helpers (issue #88).
 */

import {
  buildStageUrl,
  getNextStage,
  getPreviousStage,
  getStageIndex,
  getFirstIncompletePrerequisite,
  validateStageCompletion,
} from '@/lib/utils/stageValidation';
import { WorkflowStage } from '@/lib/types/workflow';

describe('buildStageUrl', () => {
  it('appends the dataset id for deep-linked stages', () => {
    expect(buildStageUrl(WorkflowStage.DATA_PROFILING, 'ds-1')).toBe('/explore/ds-1');
    expect(buildStageUrl(WorkflowStage.MODEL_EVALUATION, 'ds-1')).toBe('/evaluate/ds-1');
    expect(buildStageUrl(WorkflowStage.PREDICTION, 'ds-1')).toBe('/predict/ds-1');
  });

  it('uses the bare route for stages that read the dataset id from context', () => {
    // These previously 404'd (/prepare/{id}) or mis-routed (/model/{id} -> detail viewer)
    expect(buildStageUrl(WorkflowStage.DATA_LOADING, 'ds-1')).toBe('/upload');
    expect(buildStageUrl(WorkflowStage.DATA_PREPARATION, 'ds-1')).toBe('/prepare');
    expect(buildStageUrl(WorkflowStage.FEATURE_ENGINEERING, 'ds-1')).toBe('/features');
    expect(buildStageUrl(WorkflowStage.MODEL_TRAINING, 'ds-1')).toBe('/model');
    expect(buildStageUrl(WorkflowStage.DEPLOYMENT, 'ds-1')).toBe('/deploy');
  });

  it('omits the id when no dataset id is provided', () => {
    expect(buildStageUrl(WorkflowStage.DATA_PROFILING)).toBe('/explore');
    expect(buildStageUrl(WorkflowStage.PREDICTION)).toBe('/predict');
  });
});

describe('stage ordering helpers', () => {
  it('returns the next stage in order', () => {
    expect(getNextStage(WorkflowStage.DATA_LOADING)?.id).toBe(WorkflowStage.DATA_PROFILING);
    expect(getNextStage(WorkflowStage.PREDICTION)?.id).toBe(WorkflowStage.DEPLOYMENT);
  });

  it('returns null after the final stage', () => {
    expect(getNextStage(WorkflowStage.DEPLOYMENT)).toBeNull();
  });

  it('returns the previous stage in order', () => {
    expect(getPreviousStage(WorkflowStage.DATA_PROFILING)?.id).toBe(WorkflowStage.DATA_LOADING);
    expect(getPreviousStage(WorkflowStage.DEPLOYMENT)?.id).toBe(WorkflowStage.PREDICTION);
  });

  it('returns null before the first stage', () => {
    expect(getPreviousStage(WorkflowStage.DATA_LOADING)).toBeNull();
  });

  it('orders stages canonically', () => {
    expect(getStageIndex(WorkflowStage.DATA_LOADING)).toBe(0);
    expect(getStageIndex(WorkflowStage.DEPLOYMENT)).toBe(7);
  });
});

describe('getFirstIncompletePrerequisite', () => {
  it('returns the missing prerequisite for a gated stage', () => {
    const completed = new Set<WorkflowStage>([WorkflowStage.DATA_LOADING]);
    // PREDICTION needs MODEL_EVALUATION (which needs the whole chain)
    expect(
      getFirstIncompletePrerequisite(WorkflowStage.MODEL_TRAINING, completed)
    ).toBe(WorkflowStage.DATA_PROFILING);
  });

  it('returns null when all prerequisites are complete', () => {
    const completed = new Set<WorkflowStage>([
      WorkflowStage.DATA_LOADING,
      WorkflowStage.DATA_PROFILING,
    ]);
    expect(
      getFirstIncompletePrerequisite(WorkflowStage.DATA_PREPARATION, completed)
    ).toBeNull();
  });

  it('returns null for the first stage (no prerequisites)', () => {
    expect(
      getFirstIncompletePrerequisite(WorkflowStage.DATA_LOADING, new Set())
    ).toBeNull();
  });
});

describe('validateStageCompletion', () => {
  it('requires a dataset id for data loading', () => {
    expect(validateStageCompletion(WorkflowStage.DATA_LOADING, {}).isValid).toBe(false);
    expect(
      validateStageCompletion(WorkflowStage.DATA_LOADING, { datasetId: 'ds-1' }).isValid
    ).toBe(true);
  });

  it('requires at least 2 selected features', () => {
    const tooFew = validateStageCompletion(WorkflowStage.FEATURE_ENGINEERING, {
      selectedFeatures: ['a'],
    });
    expect(tooFew.isValid).toBe(false);
    expect(tooFew.errors[0]).toMatch(/at least 2 features/i);

    expect(
      validateStageCompletion(WorkflowStage.FEATURE_ENGINEERING, {
        selectedFeatures: ['a', 'b'],
      }).isValid
    ).toBe(true);
  });

  it('requires a trained model id for model training', () => {
    expect(validateStageCompletion(WorkflowStage.MODEL_TRAINING, {}).isValid).toBe(false);
    expect(
      validateStageCompletion(WorkflowStage.MODEL_TRAINING, { modelId: 'm-1' }).isValid
    ).toBe(true);
  });

  it('requires a deployment id for deployment', () => {
    expect(validateStageCompletion(WorkflowStage.DEPLOYMENT, {}).isValid).toBe(false);
    expect(
      validateStageCompletion(WorkflowStage.DEPLOYMENT, { deploymentId: 'd-1' }).isValid
    ).toBe(true);
  });

  it('treats informational stages as always valid', () => {
    expect(validateStageCompletion(WorkflowStage.DATA_PROFILING).isValid).toBe(true);
    expect(validateStageCompletion(WorkflowStage.DATA_PREPARATION).isValid).toBe(true);
    expect(validateStageCompletion(WorkflowStage.MODEL_EVALUATION).isValid).toBe(true);
    expect(validateStageCompletion(WorkflowStage.PREDICTION).isValid).toBe(true);
  });
});
