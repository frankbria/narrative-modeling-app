import { WorkflowStage } from '@/lib/types/workflow'

/**
 * One screenshot per stage, captured from a clean demo account by
 * `e2e/capture/how-it-works.capture.ts` (see docs/dev/E2E_TESTING_GUIDE.md). The main
 * column only: the sidebar, where the signed-in account is named, is cropped out.
 * Keyed by the enum so a ninth stage fails the type check until it has a shot.
 */
export const STAGE_SHOTS: Record<WorkflowStage, string> = {
  [WorkflowStage.DATA_LOADING]: '/how-it-works/data_loading.webp',
  [WorkflowStage.DATA_PROFILING]: '/how-it-works/data_profiling.webp',
  [WorkflowStage.DATA_PREPARATION]: '/how-it-works/data_preparation.webp',
  [WorkflowStage.FEATURE_ENGINEERING]: '/how-it-works/feature_engineering.webp',
  [WorkflowStage.MODEL_TRAINING]: '/how-it-works/model_training.webp',
  [WorkflowStage.MODEL_EVALUATION]: '/how-it-works/model_evaluation.webp',
  [WorkflowStage.PREDICTION]: '/how-it-works/prediction.webp',
  [WorkflowStage.DEPLOYMENT]: '/how-it-works/deployment.webp',
}

/** The captured size; `STAGE_SHOTS` files are all this size. */
export const SHOT_SIZE = { width: 1680, height: 860 } as const

export const WALKTHROUGH_SRC = '/how-it-works/churn-walkthrough.webm'
