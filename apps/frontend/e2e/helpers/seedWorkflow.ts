import type { Page, APIRequestContext } from '@playwright/test';

/**
 * Seed the backend workflow (the source of truth since #87) up to a completed
 * MODEL_EVALUATION with the trained model id, so the prediction-gated `/predict`
 * page is reachable instead of redirecting to `/upload`.
 *
 * The `trainModel` fixture only hits `/ml/train` (it does not persist workflow
 * state), so any test that navigates a stage-gated UI page after it must seed
 * the workflow first. Mirrors the inline helper proven in predict.spec.ts.
 */
export async function seedPredictionWorkflow(
  page: Page,
  request: APIRequestContext,
  datasetId: string,
  modelId: string
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
  const completedStages = [
    'data_loading',
    'data_profiling',
    'data_preparation',
    'feature_engineering',
    'model_training',
    'model_evaluation',
  ];
  const workflow = {
    current_stage: 'prediction',
    completed_stages: completedStages,
    stage_data: {},
    model_id: modelId,
  };

  const put = await request.put(`${apiBase}/workflows/${datasetId}`, { headers, data: workflow });
  if (put.status() === 404) {
    const post = await request.post(`${apiBase}/workflows/${datasetId}`, { headers, data: workflow });
    if (!post.ok()) {
      throw new Error(`seedPredictionWorkflow POST failed (${post.status()}): ${await post.text()}`);
    }
  } else if (!put.ok()) {
    throw new Error(`seedPredictionWorkflow PUT failed (${put.status()}): ${await put.text()}`);
  }

  // Mirror into localStorage so the context hydrates before the backend fetch.
  await page.addInitScript(
    ({ id, model, stages }) => {
      localStorage.setItem(
        'workflowState',
        JSON.stringify({
          currentStage: 'prediction',
          completedStages: stages,
          stageData: {},
          datasetId: id,
          modelId: model,
          lastUpdated: new Date().toISOString(),
        })
      );
    },
    { id: datasetId, model: modelId, stages: completedStages }
  );
}
