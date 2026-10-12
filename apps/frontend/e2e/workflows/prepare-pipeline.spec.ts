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

    // Export Code downloads a script for the same step (#860: it posted to a route that did not exist).
    const downloading = page.waitForEvent('download');
    await page.getByTitle('Export as Code').click();
    const script = await downloading;
    expect(script.suggestedFilename()).toBe('transformation_pipeline.py');
    const source = await (await import('node:fs/promises')).readFile(await script.path(), 'utf8');
    expect(source).toContain('def transform(df: pd.DataFrame)');
    expect(source).toContain('# Step 1: Remove Duplicates');
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

  // #859: Browse listed from a route that does not exist and was always empty, and a
  // recipe was loaded from a field the API does not send.
  test('a saved recipe is listed in Browse and loads back as the same steps @smoke', async ({
    page,
    request,
    uploadTestDataset,
  }) => {
    test.slow();
    const name = `Tidy ${Date.now()}`; // the e2e user's recipes outlive a run on a local database

    datasetId = await uploadTestDataset();
    await page.getByRole('button', { name: 'Complete & Continue to Data Preparation' }).click();
    await expect(page.getByRole('heading', { name: 'Data Preparation' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: /add remove duplicates/i }).click();
    await page.getByRole('button', { name: /add trim whitespace/i }).click();

    await page.getByTitle('Manage Recipes').click();
    await page.getByRole('button', { name: 'Save Recipe' }).first().click();
    await page.getByPlaceholder('Enter a descriptive name').fill(name);
    await page.getByPlaceholder('Describe what this recipe does...').fill('drops duplicate rows, trims text');
    await page.getByRole('button', { name: 'Save Recipe' }).last().click();
    await expect(page.getByText(`Saved recipe "${name}"`)).toBeVisible({ timeout: 15000 });

    // A fresh page: the pipeline is empty, so what Preview sends can only come from the recipe.
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Data Preparation' })).toBeVisible({ timeout: 15000 });
    await page.getByTitle('Manage Recipes').click();
    const card = page.getByRole('button', { name: new RegExp(name) });
    await expect(card).toBeVisible({ timeout: 15000 });
    await expect(card).toContainText('2 steps');
    await page.getByRole('button', { name: 'My Recipes' }).click();
    await expect(card).toBeVisible({ timeout: 15000 });

    await card.click();
    await expect(page.getByText('Recipe Manager')).toHaveCount(0);
    const previewed = page.waitForRequest(
      (r) => r.url().endsWith('/transformations/preview') && r.method() === 'POST'
    );
    await page.getByRole('button', { name: /^preview$/i }).click();
    expect((await previewed).postDataJSON().transformation_steps).toEqual([
      { transformation_type: 'remove_duplicates', parameters: {} },
      { transformation_type: 'trim_whitespace', parameters: {} },
    ]);
    await expect(page.getByTestId('pipeline-error')).toHaveCount(0);

    // Leave the shared user's recipe list as it was found.
    const headers = await apiAuthHeaders(request);
    const listed = await (await request.get(`${API_BASE}/transformations/recipes?include_public=false`, { headers })).json();
    const saved = listed.recipes.find((r: { name: string }) => r.name === name);
    expect(saved).toBeDefined();
    await request.delete(`${API_BASE}/transformations/recipes/${saved.id}`, { headers });
  });
});
