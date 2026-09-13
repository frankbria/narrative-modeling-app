import { test, expect } from '../fixtures';

/**
 * Right-to-erasure is reachable from the UI and drives the real backend cascade
 * (#482). The backend has implemented erasure since #259 but nothing called it.
 *
 * This seeds a uniquely-named dataset, then erases it from the dashboard end to
 * end — the real UI -> erasureApi -> POST /datasets/{id}/erase -> manifest path.
 * It targets the test's OWN dataset (unique filename), not the account: the whole
 * e2e suite shares one authenticated test user, so a full account erase would
 * wipe the shared fixture every other spec depends on. The account-level flow
 * shares the same ErasureConfirmDialog + erasureApi, covered by the jest suite.
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
    // backend — #527). Read it from the same-origin NextAuth session endpoint.
    const session = await page.request.get('/api/auth/session').then((r) => r.json());
    const token = session?.apiToken as string | undefined;
    expect(token, 'authenticated session must carry an apiToken').toBeTruthy();

    // Seed a DatasetMetadata-backed dataset (the id-space the dashboard lists).
    const seeded = await page.request.post(`${API_BASE}/datasets/upload`, {
      headers: { Authorization: `Bearer ${token}` },
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

    // And the dataset is gone from the list once the dialog is closed.
    await page.getByRole('button', { name: 'Close' }).click();
    await expect(datasets.getByText(filename)).toHaveCount(0, { timeout: 15000 });
  });
});
