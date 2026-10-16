/**
 * Three surfaces of a trained model, on the real stack (#1063): the Training Jobs
 * history, the feature-importance chart on the evaluation dashboard, and the Versions
 * tab of the model page.
 *
 * One training run serves all three (CI has two cores), so they are steps of one test.
 * The uploaded dataset is erased after the test by the `eraseUploads` fixture, and its
 * model and training job go with it (#943). Nothing here is mocked.
 */

import { test, expect } from '../fixtures';
import { API_BASE, apiAuthHeaders } from '../helpers/apiAuth';
import { seedEvaluationWorkflow } from '../helpers/seedWorkflow';
import { expectLandedOnStage } from '../helpers/landing';
import { EvaluatePage } from '../pages/EvaluatePage';

const TRAINABLE_DATASET = 'ai-test-datasets/binary-classification-small.csv';
const TARGET_COLUMN = 'churned';

test.describe('A trained model', () => {
  test('appears in Training Jobs, draws its feature importances and lists its version', async ({
    authenticatedPage: page,
    request,
    uploadTestDataset,
    trainModel,
  }) => {
    test.setTimeout(240000); // a real AutoML run on a 2-core runner
    const datasetId = await uploadTestDataset(TRAINABLE_DATASET);
    const modelId = await trainModel(datasetId, TARGET_COLUMN);
    const headers = await apiAuthHeaders(request);

    await test.step('Training Jobs lists the run as completed', async () => {
      await page.getByRole('link', { name: 'Training Jobs' }).click();
      await expect(page).toHaveURL(/\/training$/);
      await expect(page.getByRole('heading', { name: 'Training Jobs' })).toBeVisible();

      // The model is saved a moment before its job is marked completed, and the
      // history lists only finished jobs, so read it again until the row is there.
      const row = page.getByRole('row').filter({ hasText: `Dataset ${datasetId}` });
      await expect(async () => {
        await page.reload();
        await expect(row).toHaveCount(1, { timeout: 5000 });
      }).toPass({ timeout: 60000 });
      await expect(row.getByRole('cell').nth(0)).toHaveText('completed');
      await expect(row.getByRole('cell').nth(1)).toContainText(TARGET_COLUMN);
      await expect(row.getByRole('cell').nth(4)).toHaveText(/^\d\.\d{3}$/);
    });

    await test.step('the evaluation dashboard draws the model’s feature importances', async () => {
      const evaluation = await request.get(`${API_BASE}/ml/${modelId}/evaluation`, { headers });
      expect(evaluation.ok()).toBe(true);
      const importances = (await evaluation.json()).feature_importance as Record<string, number>;
      const ranked = Object.entries(importances).sort(([, a], [, b]) => b - a).map(([name]) => name);
      expect(ranked.length).toBeGreaterThan(0);

      await seedEvaluationWorkflow(page, request, datasetId, modelId);
      await page.goto(`/evaluate/${datasetId}`);
      await expectLandedOnStage(page, new RegExp(`/evaluate/${datasetId}`), 'Model Evaluation');
      await new EvaluatePage(page).waitForDashboard();

      const chart = page
        .getByRole('heading', { name: 'Feature Importance', exact: true })
        .locator('xpath=ancestor::div[contains(@class, "w-full")][1]');
      await expect(chart).toContainText(
        `Showing ${ranked.length} feature${ranked.length === 1 ? '' : 's'}`
      );
      await expect(chart.locator('.recharts-bar-rectangle')).toHaveCount(ranked.length, {
        timeout: 15000,
      });
      // recharts thins crowded category ticks and draws a label's words as separate
      // tspans (so their spaces vanish from textContent): every drawn label is a feature
      // the model reported, in the order of its importance.
      const bare = (name: string) => name.replace(/\s/g, '');
      const labels = await chart.locator('.recharts-yAxis-tick-labels text').allTextContents();
      expect(labels.length).toBeGreaterThan(0);
      expect(labels).toEqual(ranked.map(bare).filter((name) => labels.includes(name)));
    });

    await test.step('the Versions tab lists the model as version 1 of its family', async () => {
      // Direct navigation: no page reaches /model/{id} for a trained model (see the
      // fixme below), so a user cannot click their way here today.
      await page.goto(`/model/${modelId}`);
      await page.getByRole('tab', { name: 'Versions' }).click();

      const table = page.getByTestId('versions-table');
      await expect(table).toBeVisible({ timeout: 15000 });
      await expect(page.getByText(/^1 version of /)).toBeVisible();
      const rows = table.locator('tbody tr');
      await expect(rows).toHaveCount(1);
      await expect(rows.getByRole('link', { name: 'v1' })).toHaveAttribute('href', `/model/${modelId}`);
      await expect(rows.getByText('Active', { exact: true })).toBeVisible();
      await expect(page.getByTestId(`promote-${modelId}`)).toBeEnabled();
    });
  });

  test.fixme(
    'is reachable from the dashboard’s Recent Models',
    // The dashboard's Recent Models reads GET /models (the legacy ModelConfig surface,
    // which training never writes), so a trained MLModel is never listed there, and that
    // list is the only navigation into /model/{id}.
    async ({ authenticatedPage: page, request, uploadTestDataset, trainModel }) => {
      test.setTimeout(240000);
      const datasetId = await uploadTestDataset(TRAINABLE_DATASET);
      const modelId = await trainModel(datasetId, TARGET_COLUMN);
      const model = await request.get(`${API_BASE}/ml/${modelId}`, {
        headers: await apiAuthHeaders(request),
      });
      const { name } = (await model.json()) as { name: string };

      await page.goto('/dashboard?skipOnboarding=true');
      await page.getByRole('button', { name }).first().click();
      await expect(page).toHaveURL(new RegExp(`/model/${modelId}$`));
    }
  );
});
