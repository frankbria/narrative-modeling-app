/**
 * The training form when a run cannot start or cannot finish (#991).
 *
 * Replaces the training-error cases that train.spec.ts and error-scenarios.spec.ts
 * each wrote against a page that does not exist (`/datasets/{id}/train`).
 */

import { test, expect } from '../fixtures';
import { chooseTarget, seedTrainingWorkflow } from '../helpers/seedWorkflow';

test.describe('Training errors', () => {
  let datasetId = '';

  test.beforeEach(async ({ authenticatedPage: page, request, uploadTestDataset }) => {
    test.slow();
    datasetId = await uploadTestDataset();
    await seedTrainingWorkflow(page, request, datasetId);
    await page.goto('/model');
    await expect(page.getByRole('combobox').getByRole('option', { name: 'purchased' })).toBeAttached({
      timeout: 30000,
    });
  });

  test.afterEach(async ({ cleanupDataset }) => {
    await cleanupDataset(datasetId);
  });

  test('a run needs a target column', async ({ authenticatedPage: page }) => {
    const start = page.getByRole('button', { name: /Start Training/ });
    await expect(page.getByText('Target column required')).toBeVisible();
    await expect(start).toBeDisabled();

    await page.getByRole('combobox').selectOption('purchased');
    await expect(start).toBeEnabled();
    await expect(page.getByText('Target column required')).toBeHidden();
  });

  test('a refused start is shown and the form keeps its choice', async ({ authenticatedPage: page }) => {
    // The UI's reaction to the backend refusing the run, so this one route is mocked.
    await page.route(
      (url) => url.pathname.endsWith('/ml/train'),
      (route) =>
        route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Target column has a single value' }),
        })
    );
    await chooseTarget(page, 'purchased');
    await page.getByRole('button', { name: /Start Training/ }).click();

    await expect(page.getByText('Training failed')).toBeVisible();
    await expect(page.getByText('Target column has a single value')).toBeVisible();
    await expect(page.getByRole('combobox')).toHaveValue('purchased');
  });

  test('a run that fails on the backend returns to the form and says so', async ({
    authenticatedPage: page,
  }) => {
    // sample.csv has five rows: the real job starts and fails.
    await chooseTarget(page, 'purchased');
    await page.getByRole('button', { name: /Start Training/ }).click();

    await expect(page.getByText('Training failed').first()).toBeVisible({ timeout: 90000 });
    await expect(page.getByRole('button', { name: /Start Training/ })).toBeVisible();
    await expect(page.getByRole('combobox')).toHaveValue('purchased');
  });

  // App bug: the problem detector answers `unknown` ("Not enough samples") for a
  // five-row file, the engine fits anyway, feature selection raises a numpy TypeError
  // on the text target, and job_failures does not classify that, so the user reads
  // "The job failed due to an unexpected error" instead of why.
  test.fixme('a dataset too small to train says why', async ({ authenticatedPage: page }) => {
    await chooseTarget(page, 'purchased');
    await page.getByRole('button', { name: /Start Training/ }).click();

    await expect(page.getByText('Training failed').first()).toBeVisible({ timeout: 90000 });
    await expect(page.getByText(/too few|Not enough samples/i).first()).toBeVisible();
  });
});
