/**
 * Workflow navigation (setCurrentStage / completeStage auto-advance) pushes
 * `/evaluate/{datasetId}` when a dataset is loaded, but the evaluation page
 * reads everything it needs (modelId) from the workflow context — so this
 * route simply renders the same page. Without it, in-workflow navigation to
 * Model Evaluation 404s.
 */
export { default } from '../page'
