/**
 * The Prepare stage transforms a dataset uploaded through the UI (#855, #850).
 *
 * Before #850 the API refused every UI upload's id, and before #855 the page posted
 * payloads no route accepted, so preview, apply and recipe save all failed, logged
 * to the console and showed nothing. The older transform specs could not see it:
 * they drive a legacy page and swallow every failure in a try/catch. This one has no
 * try/catch; each step must succeed.
 */
import { test, expect } from '../fixtures';
import { API_BASE, apiAuthHeaders } from '../helpers/apiAuth';

test.describe('Prepare pipeline', () => {
  let datasetId: string | undefined;

  test.afterEach(async ({ cleanupDataset }) => {
    if (datasetId) await cleanupDataset(datasetId);
    datasetId = undefined;
  });

  test('a UI upload is previewed, transformed and recorded in its history @smoke', async ({
    page,
    request,
    uploadTestDataset,
  }) => {
    test.slow(); // upload + processing + two transformation round-trips on CI runners

    datasetId = await uploadTestDataset(); // lands on /explore/{id}
    await page.getByRole('button', { name: 'Complete & Continue to Data Preparation' }).click();
    await expect(page.getByRole('heading', { name: 'Data Preparation' })).toBeVisible({ timeout: 15000 });

    // Before any preview, the panel shows the dataset's own rows (GET /data/{id}/preview).
    await expect(page.locator('th', { hasText: 'age' })).toBeVisible({ timeout: 15000 });

    // The sidebar lists the registry (GET /transformations/available).
    await page.getByRole('button', { name: /add remove duplicates/i }).click();

    await page.getByRole('button', { name: /^preview$/i }).click();
    await page.getByRole('button', { name: /^after$/i }).click();
    await expect(page.locator('th', { hasText: 'age' })).toBeVisible({ timeout: 15000 });
    // The pipeline's own error, not Next's route announcer (also role=alert).
    await expect(page.getByTestId('pipeline-error')).toHaveCount(0);

    await page.getByRole('button', { name: /apply & continue/i }).click();
    await expect(page.getByText('Applied 1 transformation')).toBeVisible({ timeout: 20000 });

    const history = await request.get(`${API_BASE}/transformations/datasets/${datasetId}/history`, {
      headers: await apiAuthHeaders(request),
    });
    expect(history.status()).toBe(200);
    const body = await history.json();
    expect(body.history.map((h: { transformation_type: string }) => h.transformation_type)).toEqual([
      'remove_duplicates',
    ]);
  });
});
