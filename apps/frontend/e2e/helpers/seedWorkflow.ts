import type { Page, APIRequestContext } from '@playwright/test';

/**
 * Seed the backend workflow (the source of truth since #87) for a model trained
 * via the `trainModel` fixture, so a stage-gated UI page is reachable instead of
 * redirecting to `/upload`.
 *
 * The `trainModel` fixture only hits `/ml/train` (it does not persist workflow
 * state), so any test that navigates a stage-gated page after it must seed the
 * workflow first. Mirrors the inline helper proven in predict.spec.ts.
 */
async function seedWorkflow(
  page: Page,
  request: APIRequestContext,
  datasetId: string,
  modelId: string,
  currentStage: string,
  completedStages: string[]
): Promise<void> {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  // The `dev-user-default` token differs from the fixtures' `e2e-test-token`,
  // but under SKIP_AUTH both resolve to the same default user — so the seeded
  // workflow is owned by the user the page loads as. (Same equivalence noted in
  // data-preparation.spec.ts.)
  const headers = {
    Authorization: 'Bearer dev-user-default',
    'Content-Type': 'application/json',
  };
  const workflow = {
    current_stage: currentStage,
    completed_stages: completedStages,
    stage_data: {},
    model_id: modelId,
  };

  const put = await request.put(`${apiBase}/workflows/${datasetId}`, { headers, data: workflow });
  if (put.status() === 404) {
    const post = await request.post(`${apiBase}/workflows/${datasetId}`, { headers, data: workflow });
    if (!post.ok()) {
      throw new Error(`seedWorkflow POST failed (${post.status()}): ${await post.text()}`);
    }
  } else if (!put.ok()) {
    throw new Error(`seedWorkflow PUT failed (${put.status()}): ${await put.text()}`);
  }

  // Mirror into localStorage so the context hydrates before the backend fetch.
  await page.addInitScript(
    ({ id, model, stage, stages }) => {
      localStorage.setItem(
        'workflowState',
        JSON.stringify({
          currentStage: stage,
          completedStages: stages,
          stageData: {},
          datasetId: id,
          modelId: model,
          lastUpdated: new Date().toISOString(),
        })
      );
    },
    { id: datasetId, model: modelId, stage: currentStage, stages: completedStages }
  );
}

/**
 * Seed up to a completed MODEL_EVALUATION so the prediction-gated `/predict`
 * page is reachable.
 */
export async function seedPredictionWorkflow(
  page: Page,
  request: APIRequestContext,
  datasetId: string,
  modelId: string
): Promise<void> {
  await seedWorkflow(page, request, datasetId, modelId, 'prediction', [
    'data_loading',
    'data_profiling',
    'data_preparation',
    'feature_engineering',
    'model_training',
    'model_evaluation',
  ]);
}

/**
 * Seed the workflow at the MODEL_EVALUATION stage (#234) so the stage-gated
 * `/evaluate/[datasetId]` dashboard renders for a model trained via the API
 * fixture. The evaluate page gates on MODEL_TRAINING being complete and the
 * context carrying `state.modelId` — both satisfied here.
 */
export async function seedEvaluationWorkflow(
  page: Page,
  request: APIRequestContext,
  datasetId: string,
  modelId: string
): Promise<void> {
  await seedWorkflow(page, request, datasetId, modelId, 'model_evaluation', [
    'data_loading',
    'data_profiling',
    'data_preparation',
    'feature_engineering',
    'model_training',
  ]);
}
