import { test, expect } from '../fixtures';

/**
 * Right-to-erasure is reachable from the UI and drives the real backend cascade
 * (#482). The backend has implemented erasure since #259 but nothing called it.
 *
 * This uploads a uniquely-named dataset and erases it from the dashboard end to
 * end — the real UI -> erasureApi -> POST /datasets/{id}/erase -> manifest path.
 * It deliberately targets the test's OWN dataset (unique filename) rather than
 * the account: under SKIP_AUTH the e2e backend collapses every identity to one
 * user, so a full account erase would wipe the shared fixture every other spec
 * depends on. The account-level flow shares the same ErasureConfirmDialog +
 * erasureApi, covered by the jest suite.
 */
test.describe('right-to-erasure UI (#482)', () => {
  test('erases a dataset end to end from the dashboard @smoke', async ({ authenticatedPage: page }) => {
    const filename = `erase-e2e-${Date.now()}.csv`;

    // Upload a small, uniquely-named CSV (no PII, so no confirmation gate).
    await page.goto('/upload');
    await page
      .locator('input[type="file"]')
      .setInputFiles({ name: filename, mimeType: 'text/csv', buffer: Buffer.from('a,b\n1,2\n3,4\n') });
    const uploadButton = page.getByTestId('upload-button');
    await uploadButton.waitFor({ state: 'visible', timeout: 10000 });
    await uploadButton.click();
    await page.getByTestId('file-id').waitFor({ state: 'visible', timeout: 20000 });

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

    // And the dataset is gone from the list once the dialog is closed.
    await page.getByRole('button', { name: 'Close' }).click();
    await expect(datasets.getByText(filename)).toHaveCount(0, { timeout: 15000 });
  });
});
