import { test, expect } from '../fixtures';
import { seedTrainingWorkflow } from '../helpers/seedWorkflow';

/**
 * The training form on the real stack (#919).
 *
 * The other training specs start their runs through the API, and the ones that
 * drive `/model` return early when the target cannot be picked, so nothing else
 * noticed that the form offered no target column at all.
 */
test.describe('Training form', () => {
  test("offers the upload's columns as targets and starts a run @smoke", async ({
    authenticatedPage: page,
    request,
    uploadTestDataset,
    cleanupDataset,
  }) => {
    test.slow();
    const datasetId = await uploadTestDataset();
    await seedTrainingWorkflow(page, request, datasetId);

    await page.goto('/model');
    const target = page.getByRole('combobox');
    await expect(target.getByRole('option', { name: 'purchased' })).toBeAttached({
      timeout: 30000,
    });
    await target.selectOption('purchased');

    const started = page.waitForResponse(
      (response) =>
        response.url().endsWith('/ml/train') && response.request().method() === 'POST'
    );
    await page.getByRole('button', { name: /Start Training/ }).click();
    const response = await started;
    expect(response.status()).toBe(200);
    expect(response.request().postDataJSON()).toMatchObject({
      dataset_id: datasetId,
      target_column: 'purchased',
    });

    await cleanupDataset(datasetId);
  });
});
