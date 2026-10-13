import { test, expect } from '../fixtures';
import { seedFeaturesWorkflow } from '../helpers/seedWorkflow';

/**
 * The Feature Engineering stage on the real stack (#969).
 *
 * The page used to call three backend routes that did not answer, and the specs
 * that pass through it served all three from mocks, so nothing noticed that the
 * guided workflow could not get from here to training. Nothing on this page or
 * the next is mocked: the columns come from the upload, and the choice has to
 * arrive in the training request the backend accepts.
 */
test.describe('Feature Engineering stage', () => {
  test("lists the upload's columns, and a column left out is left out of training @smoke", async ({
    authenticatedPage: page,
    request,
    uploadTestDataset,
    cleanupDataset,
  }) => {
    test.slow();
    const datasetId = await uploadTestDataset();
    await seedFeaturesWorkflow(page, request, datasetId);

    await page.goto('/features');
    const age = page.getByRole('checkbox', { name: 'age', exact: true });
    await expect(age).toBeChecked({ timeout: 30000 });
    await expect(page.getByRole('checkbox', { name: 'purchased', exact: true })).toBeChecked();
    await expect(page.getByTestId('continue-button')).toBeDisabled();

    await age.uncheck();
    await page.getByTestId('use-columns-button').click();
    await expect(page.getByTestId('choice-recorded')).toBeVisible();
    await page.getByTestId('continue-button').click();

    await expect(page).toHaveURL(/\/model$/, { timeout: 30000 });
    await expect(page.getByTestId('left-out-columns')).toContainText('age');
    const target = page.getByRole('combobox');
    await expect(target.getByRole('option', { name: 'purchased' })).toBeAttached({ timeout: 30000 });
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
      feature_config: { exclude_columns: ['age'] },
    });

    await cleanupDataset(datasetId);
  });
});
