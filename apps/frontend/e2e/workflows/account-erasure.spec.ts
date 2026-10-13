import { test, expect } from '../fixtures';
import { apiAuthHeaders } from '../helpers/apiAuth';
import { isolatedState } from '../isolatedUsers';

/**
 * Right-to-erasure is reachable from the UI and drives the real backend cascade
 * (#482). The backend has implemented erasure since #259 but nothing called it.
 *
 * This seeds a uniquely-named dataset, then erases it from the dashboard end to
 * end — the real UI -> erasureApi -> POST /datasets/{id}/erase -> manifest path.
 * It targets the test's OWN dataset (unique filename), not the account: this test
 * is the shared test user, and a full account erase would wipe what every other
 * spec depends on. The account-level erase is the second describe, as a user no
 * other spec shares (#743).
 *
 * Seeding goes through POST /datasets/upload (which creates a DatasetMetadata,
 * the id-space the dashboard lists) rather than the /upload page, which posts to
 * /upload/secure (the legacy UserData space that does NOT surface in the recent
 * datasets list).
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

test.describe('right-to-erasure UI (#482)', () => {
  test('erases a dataset end to end from the dashboard @smoke', async ({ authenticatedPage: page }) => {
    const filename = `erase-e2e-${Date.now()}.csv`;

    // The backend verifies the minted API JWT, so seed with the logged-in
    // session's token (session.apiToken, the only credential that may reach the
    // backend — #527).
    // Seed a DatasetMetadata-backed dataset (the id-space the dashboard lists).
    const seeded = await page.request.post(`${API_BASE}/datasets/upload`, {
      headers: await apiAuthHeaders(page.request),
      multipart: {
        file: { name: filename, mimeType: 'text/csv', buffer: Buffer.from('a,b\n1,2\n3,4\n') },
      },
    });
    expect(seeded.ok(), `seed upload failed: ${seeded.status()}`).toBeTruthy();

    // It appears in the dashboard's recent datasets.
    await page.goto('/dashboard');
    const datasets = page.getByTestId('recent-datasets');
    await expect(datasets.getByText(filename).first()).toBeVisible({ timeout: 15000 });

    // Erase it: the row's trash button opens the confirm dialog, which requires
    // typing the exact dataset name.
    await page.locator(`button[aria-label="Delete dataset ${filename}"]`).click();
    const confirm = page.getByTestId('confirm-erasure');
    await expect(confirm).toBeDisabled();
    await page.getByLabel(/type/i).fill(filename);
    await expect(confirm).toBeEnabled();
    await confirm.click();

    // The manifest is surfaced as a success summary (not a bare redirect).
    await expect(page.getByText(/Done\. Removed/i)).toBeVisible({ timeout: 20000 });

    // And the dataset is gone from the list once the dialog is closed. (Use the
    // testid: Radix's built-in dialog X also exposes an accessible name "Close".)
    await page.getByTestId('erasure-close').click();
    await expect(datasets.getByText(filename)).toHaveCount(0, { timeout: 15000 });
  });
});

test.describe('account erasure, as a user of its own (#743)', () => {
  test.use({ storageState: isolatedState('erasure') });

  test("erases everything the account holds from Settings, and the account still works @smoke", async ({
    authenticatedPage: page,
  }) => {
    const headers = await apiAuthHeaders(page.request);
    const seeded = await page.request.post(`${API_BASE}/datasets/upload`, {
      headers,
      multipart: {
        file: { name: `erase-account-${Date.now()}.csv`, mimeType: 'text/csv', buffer: Buffer.from('a,b\n1,2\n3,4\n') },
      },
    });
    expect(seeded.ok(), `seed upload failed: ${seeded.status()}`).toBeTruthy();
    const { dataset_id: datasetId } = await seeded.json();

    await page.goto('/settings');
    await page.getByTestId('delete-account').click();
    const confirm = page.getByTestId('confirm-erasure');
    await expect(confirm).toBeDisabled();
    await page.getByLabel(/type/i).fill('DELETE');
    await confirm.click();
    await expect(page.getByText(/Done\. Removed/i)).toBeVisible({ timeout: 30000 });

    // Gone for its owner, through the same session: erasure removes data, not the account.
    expect((await page.request.get(`${API_BASE}/datasets/${datasetId}`, { headers })).status()).toBe(404);
    const remaining = await page.request.get(`${API_BASE}/datasets`, { headers });
    expect(remaining.status()).toBe(200);
    expect((await remaining.json()).datasets).toEqual([]);
  });
});
