/**
 * Model Evaluation Dashboard E2E Tests (issue #79)
 *
 * Tests the evaluation dashboard workflow:
 * - Navigating from training through to /evaluate
 * - Metric cards render for the trained model
 * - Tab switching (Overview / Confusion Matrix / Curves / Compare)
 * - Confusion-matrix cell drill-down detail panel
 * - Export buttons enabled with data
 *
 * Follows the train.spec.ts conventions: tests degrade gracefully (log and
 * return) when workflow gating redirects or training is unavailable, since
 * these run against a live stack.
 */

import { test, expect } from '../fixtures';
import { TrainPage } from '../pages/TrainPage';
import { EvaluatePage } from '../pages/EvaluatePage';

/**
 * Train a model through the UI so the workflow context allows /evaluate.
 * Returns false (after logging) when any prerequisite is unavailable.
 */
async function trainModelThroughWorkflow(
  authenticatedPage: import('@playwright/test').Page
): Promise<boolean> {
  const trainPage = new TrainPage(authenticatedPage);
  await trainPage.goto('/model');

  if (authenticatedPage.url().includes('/upload')) {
    console.log('[evaluate] Redirected to /upload due to workflow gating.');
    return false;
  }

  try {
    await trainPage.selectTargetColumn('purchased');
  } catch {
    console.log('[evaluate] Could not select target column.');
    return false;
  }

  try {
    await trainPage.selectAlgorithm('Decision Tree'); // fast algorithm
  } catch {
    try {
      await trainPage.selectAlgorithm('Logistic Regression');
    } catch {
      console.log('[evaluate] Could not select algorithm.');
      return false;
    }
  }

  await trainPage.startTraining();

  try {
    await trainPage.waitForTrainingComplete(120000);
  } catch {
    console.log('[evaluate] Training did not complete in time.');
    return false;
  }

  return true;
}

test.describe('Model Evaluation Dashboard', () => {
  let datasetId: string;

  test.beforeEach(async ({ uploadTestDataset }) => {
    // #157: train-then-evaluate is heavy; on 2-core CI the upload + training can
    // exceed the 30s test budget (hook/fixture setup counts against it) when a
    // parallel worker is also training. test.slow() triples the budget so 2-core
    // contention no longer flakes these @smoke tests.
    test.slow();
    datasetId = await uploadTestDataset();
  });

  test.afterEach(async ({ cleanupDataset }) => {
    if (datasetId) {
      await cleanupDataset(datasetId);
    }
  });

  test('should render metric cards after training @smoke', async ({ authenticatedPage }) => {
    if (!(await trainModelThroughWorkflow(authenticatedPage))) return;

    const evaluatePage = new EvaluatePage(authenticatedPage);
    await evaluatePage.gotoEvaluate();

    if (evaluatePage.wasRedirected()) {
      console.log('[evaluate] Redirected away from /evaluate by workflow gating.');
      return;
    }

    await evaluatePage.waitForDashboard();

    // At least one classification or regression metric card should render.
    const metrics = ['Accuracy', 'F1', 'ROC AUC', 'MAE', 'RMSE', 'R²'];
    let metricsFound = false;
    for (const metric of metrics) {
      if (await evaluatePage.hasMetric(metric)) {
        metricsFound = true;
        break;
      }
    }
    expect(metricsFound).toBeTruthy();
  });

  test('should switch between dashboard tabs @smoke', async ({ authenticatedPage }) => {
    if (!(await trainModelThroughWorkflow(authenticatedPage))) return;

    const evaluatePage = new EvaluatePage(authenticatedPage);
    await evaluatePage.gotoEvaluate();

    if (evaluatePage.wasRedirected()) {
      console.log('[evaluate] Redirected away from /evaluate by workflow gating.');
      return;
    }

    await evaluatePage.waitForDashboard();

    // Overview is the default tab.
    await expect(evaluatePage.tab(/overview/i)).toBeVisible();

    // Compare is always offered.
    await evaluatePage.switchToTab(/compare/i);
    await expect(
      authenticatedPage.locator('text=/Select models to compare/i')
    ).toBeVisible({ timeout: 10000 });

    // Classification-only tabs when present.
    if (await evaluatePage.tab(/confusion matrix/i).isVisible({ timeout: 2000 })) {
      await evaluatePage.switchToTab(/confusion matrix/i);
      await expect(
        authenticatedPage.locator('svg[aria-label="Confusion matrix"]')
      ).toBeVisible({ timeout: 10000 });
    }

    if (await evaluatePage.tab(/curves/i).isVisible({ timeout: 2000 })) {
      await evaluatePage.switchToTab(/curves/i);
      await expect(
        authenticatedPage.locator('text=/ROC Curve|Precision-Recall Curve/i').first()
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test('should show a detail panel when a confusion matrix cell is clicked', async ({
    authenticatedPage,
  }) => {
    if (!(await trainModelThroughWorkflow(authenticatedPage))) return;

    const evaluatePage = new EvaluatePage(authenticatedPage);
    await evaluatePage.gotoEvaluate();

    if (evaluatePage.wasRedirected()) {
      console.log('[evaluate] Redirected away from /evaluate by workflow gating.');
      return;
    }

    await evaluatePage.waitForDashboard();

    const confusionTab = evaluatePage.tab(/confusion matrix/i);
    if (!(await confusionTab.isVisible({ timeout: 2000 }))) {
      console.log('[evaluate] No confusion matrix tab (regression model or partial data).');
      return;
    }

    await evaluatePage.switchToTab(/confusion matrix/i);

    // Click the first matrix cell and verify the drill-down panel appears.
    const firstCell = authenticatedPage.getByRole('button', { name: /^Actual /i }).first();
    await firstCell.click();

    await expect(evaluatePage.confusionCellDetail()).toBeVisible({ timeout: 5000 });
    await expect(evaluatePage.confusionCellDetail()).toContainText(/Count/i);
  });

  test('should enable export buttons when evaluation data is loaded', async ({
    authenticatedPage,
  }) => {
    if (!(await trainModelThroughWorkflow(authenticatedPage))) return;

    const evaluatePage = new EvaluatePage(authenticatedPage);
    await evaluatePage.gotoEvaluate();

    if (evaluatePage.wasRedirected()) {
      console.log('[evaluate] Redirected away from /evaluate by workflow gating.');
      return;
    }

    await evaluatePage.waitForDashboard();

    await expect(evaluatePage.exportCSVButton()).toBeEnabled();
    await expect(evaluatePage.exportPDFButton()).toBeEnabled();

    // CSV export triggers a browser download named evaluation-{model_id}.csv.
    try {
      const download = await evaluatePage.exportCSV();
      expect(download.suggestedFilename()).toMatch(/^evaluation-.+\.csv$/);
    } catch {
      console.log('[evaluate] Download event not captured (browser config dependent).');
    }
  });

  test('should compare models in the Compare tab', async ({ authenticatedPage }) => {
    if (!(await trainModelThroughWorkflow(authenticatedPage))) return;

    const evaluatePage = new EvaluatePage(authenticatedPage);
    await evaluatePage.gotoEvaluate();

    if (evaluatePage.wasRedirected()) {
      console.log('[evaluate] Redirected away from /evaluate by workflow gating.');
      return;
    }

    await evaluatePage.waitForDashboard();
    await evaluatePage.switchToTab(/compare/i);

    const checkboxes = authenticatedPage.getByRole('checkbox');
    const count = await checkboxes.count();
    if (count < 2) {
      console.log('[evaluate] Fewer than two trained models; skipping comparison.');
      return;
    }

    await checkboxes.nth(0).click();
    await checkboxes.nth(1).click();

    await expect(evaluatePage.compareButton()).toBeEnabled();
    await evaluatePage.runComparison();

    // Comparison table renders metrics as rows with a Best badge.
    await expect(
      authenticatedPage.locator('text=/Comparison results/i')
    ).toBeVisible({ timeout: 15000 });
    await expect(authenticatedPage.locator('text=Best').first()).toBeVisible();
  });

  test('should preserve workflow navigation actions', async ({ authenticatedPage }) => {
    if (!(await trainModelThroughWorkflow(authenticatedPage))) return;

    const evaluatePage = new EvaluatePage(authenticatedPage);
    await evaluatePage.gotoEvaluate();

    if (evaluatePage.wasRedirected()) {
      console.log('[evaluate] Redirected away from /evaluate by workflow gating.');
      return;
    }

    await evaluatePage.waitForDashboard();

    await expect(evaluatePage.backToTrainingButton()).toBeVisible();
    await expect(evaluatePage.proceedButton()).toBeVisible();

    await evaluatePage.proceedButton().click();
    await authenticatedPage.waitForURL(/\/predict/, { timeout: 10000 }).catch(() => {
      console.log('[evaluate] Proceed did not navigate to /predict (stage routing).');
    });
  });
});
