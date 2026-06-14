/**
 * Workflow navigation (setCurrentStage / completeStage auto-advance) pushes
 * `/predict/{datasetId}` when a dataset is loaded, but the prediction page
 * reads everything it needs (modelId) from the workflow context — so this
 * route simply renders the same page. Without it, in-workflow navigation to
 * Prediction 404s (mirrors the /evaluate/[datasetId] re-export, issue #82).
 */
export { default } from '../page'
