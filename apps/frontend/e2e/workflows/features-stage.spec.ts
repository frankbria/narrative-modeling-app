import { test, expect } from '../fixtures';
import { seedFeaturesWorkflow } from '../helpers/seedWorkflow';

/**
 * The Feature Engineering stage on the real stack (#969).
 *
 * The page used to call three backend routes that did not answer, and the specs
 * that pass through it served all three from mocks, so nothing noticed that the
 * guided workflow could not get from here to training. Nothing on this page or
 * the next is mocked: the columns come from the upload, and the choice has to
 * arrive in the training request the backend accepts. The "also try interaction
 * features" switch (#974) rides in the same request as `create_interactions`.
 */
test.describe('Feature Engineering stage', () => {
  test("lists the upload's columns, and a column left out and the interaction switch reach training @smoke", async ({
    authenticatedPage: page,
    request,
    uploadTestDataset,
    cleanupDataset,
  }) => {
    test.slow();
    // Ten columns: with the target set apart, leaving one out still leaves the two-column minimum.
    const datasetId = await uploadTestDataset('ai-test-datasets/binary-classification-small.csv');
    await seedFeaturesWorkflow(page, request, datasetId);

    await page.goto('/features');
    const age = page.getByRole('checkbox', { name: 'age', exact: true });
    await expect(age).toBeChecked({ timeout: 30000 });
    await expect(page.getByTestId('continue-button')).toBeDisabled();
    await page.getByLabel('Column to predict').selectOption('churned');
    await expect(page.getByRole('checkbox', { name: 'churned', exact: true })).toHaveCount(0);

    await age.uncheck();
    const interactions = page.getByRole('switch', { name: 'Also try interaction features' });
    await expect(interactions).not.toBeChecked();
    await interactions.click();
    await expect(interactions).toBeChecked();
    await expect(page.getByTestId('choice-recorded')).toBeVisible();
    await page.getByTestId('continue-button').click();

    await expect(page).toHaveURL(/\/model$/, { timeout: 30000 });
    await expect(page.getByTestId('left-out-columns')).toContainText('age');
    const target = page.getByRole('combobox');
    await expect(target.getByRole('option', { name: 'churned' })).toBeAttached({ timeout: 30000 });
    await target.selectOption('churned');

    const started = page.waitForResponse(
      (response) =>
        response.url().endsWith('/ml/train') && response.request().method() === 'POST'
    );
    await page.getByRole('button', { name: /Start Training/ }).click();
    const response = await started;
    expect(response.status()).toBe(200);
    expect(response.request().postDataJSON()).toMatchObject({
      dataset_id: datasetId,
      target_column: 'churned',
      feature_config: { exclude_columns: ['age'], create_interactions: true },
    });

    await cleanupDataset(datasetId);
  });
});
