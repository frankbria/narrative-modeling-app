/**
 * Model Evaluation Dashboard E2E Tests (issue #79)
 *
 * A model trained through the API, the workflow seeded at MODEL_EVALUATION, and the
 * dashboard at /evaluate/{datasetId} driven on the live stack: metric cards, tabs,
 * the confusion-matrix drill-down, export, model comparison and the way on to
 * /predict.
 *
 * These tests FAIL LOUDLY (#921). The previous version trained through a form shape
 * that no longer exists and returned early whenever that, the workflow gate or a tab
 * was missing, so every test passed without opening the dashboard.
 */

import { test, expect } from '../fixtures';
import { EvaluatePage } from '../pages/EvaluatePage';
import { seedEvaluationWorkflow } from '../helpers/seedWorkflow';
import { expectLandedOnStage } from '../helpers/landing';

const TRAINABLE_DATASET = 'ai-test-datasets/binary-classification-small.csv';
const TARGET_COLUMN = 'churned';

test.describe('Model Evaluation Dashboard', () => {
  let datasetId: string;
  let modelId: string;

  test.beforeEach(async ({ page, request, uploadTestDataset, trainModel }) => {
    // Real AutoML training + artifact-save poll is slow on 2-core CI runners.
    test.setTimeout(180000);
    datasetId = await uploadTestDataset(TRAINABLE_DATASET);
    modelId = await trainModel(datasetId, TARGET_COLUMN);
    await seedEvaluationWorkflow(page, request, datasetId, modelId);
  });

  test.afterEach(async ({ cleanupDataset }) => {
    if (datasetId) {
      await cleanupDataset(datasetId);
    }
  });

  async function openDashboard(page: import('@playwright/test').Page): Promise<EvaluatePage> {
    await page.goto(`/evaluate/${datasetId}`);
    await expectLandedOnStage(page, new RegExp(`/evaluate/${datasetId}`), 'Model Evaluation');
    const evaluatePage = new EvaluatePage(page);
    await evaluatePage.waitForDashboard();
    return evaluatePage;
  }

  test('renders the metric cards and every tab of a classification model @smoke', async ({
    authenticatedPage,
  }) => {
    const evaluatePage = await openDashboard(authenticatedPage);

    await expect(authenticatedPage.getByText('Accuracy', { exact: true }).first()).toBeVisible();
    await expect(evaluatePage.tab(/overview/i)).toBeVisible();

    await evaluatePage.switchToTab(/confusion matrix/i);
    await expect(authenticatedPage.locator('svg[aria-label="Confusion matrix"]')).toBeVisible({
      timeout: 10000,
    });

    await evaluatePage.switchToTab(/curves/i);
    await expect(
      authenticatedPage.locator('text=/ROC Curve|Precision-Recall Curve/i').first()
    ).toBeVisible({ timeout: 10000 });

    await evaluatePage.switchToTab(/compare/i);
    await expect(authenticatedPage.locator('text=/Select models to compare/i')).toBeVisible({
      timeout: 10000,
    });
  });

  test('drills into a confusion-matrix cell, exports, and proceeds to prediction', async ({
    authenticatedPage,
  }) => {
    const evaluatePage = await openDashboard(authenticatedPage);

    await evaluatePage.switchToTab(/confusion matrix/i);
    await authenticatedPage.getByRole('button', { name: /^Actual /i }).first().click();
    await expect(evaluatePage.confusionCellDetail()).toBeVisible({ timeout: 5000 });
    await expect(evaluatePage.confusionCellDetail()).toContainText(/Count/i);

    await expect(evaluatePage.exportPDFButton()).toBeEnabled();
    const download = await evaluatePage.exportCSV();
    expect(download.suggestedFilename()).toBe(`evaluation-${modelId}.csv`);

    await expect(evaluatePage.backToTrainingButton()).toBeVisible();
    await evaluatePage.proceedButton().click();
    await expect(authenticatedPage).toHaveURL(/\/predict/, { timeout: 15000 });
  });

  test('compares two models trained on the dataset', async ({ authenticatedPage, trainModel }) => {
    test.setTimeout(300000); // a second real training on top of beforeEach's
    await trainModel(datasetId, TARGET_COLUMN);
    const evaluatePage = await openDashboard(authenticatedPage);

    await evaluatePage.switchToTab(/compare/i);
    const checkboxes = authenticatedPage.getByRole('checkbox');
    await expect(checkboxes).toHaveCount(2, { timeout: 15000 });
    await checkboxes.nth(0).click();
    await checkboxes.nth(1).click();

    await expect(evaluatePage.compareButton()).toBeEnabled();
    await evaluatePage.runComparison();
    await expect(authenticatedPage.locator('text=/Comparison results/i')).toBeVisible({ timeout: 15000 });
    await expect(authenticatedPage.locator('text=Best').first()).toBeVisible();
  });
});
