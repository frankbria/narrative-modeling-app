import { WorkflowStage } from '@/lib/types/workflow'

/**
 * One line per stage, written for the public pages: longer than the in-app stage
 * descriptions and held to the do-not-claim list. Keyed by the enum so a ninth stage
 * fails the type check until it is described here.
 */
export const STAGE_BLURBS: Record<WorkflowStage, string> = {
  [WorkflowStage.DATA_LOADING]: 'Upload a CSV or XLSX file.',
  [WorkflowStage.DATA_PROFILING]: 'See distributions, correlations and quality problems before you model.',
  [WorkflowStage.DATA_PREPARATION]: 'Clean the data, with a full history you can undo.',
  [WorkflowStage.FEATURE_ENGINEERING]: 'Choose which columns the model may use, or let it try interaction features.',
  [WorkflowStage.MODEL_TRAINING]: 'About ten algorithms, cross-validated, with a baseline to beat.',
  [WorkflowStage.MODEL_EVALUATION]: 'Read the leaderboard and the SHAP drivers behind the winner.',
  [WorkflowStage.PREDICTION]: 'Score one record or a whole file.',
  [WorkflowStage.DEPLOYMENT]: 'Serve it from a secured endpoint with API keys, or export it as Python or Docker.',
}
