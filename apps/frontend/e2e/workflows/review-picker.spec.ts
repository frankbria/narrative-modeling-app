import { test, expect } from '../fixtures';

/**
 * Review Data with no dataset in the address (#1167): it used to be a dead end that
 * also printed the backend's raw validation error in the chat. It now lists the
 * user's datasets, and picking one opens it in Explore.
 */
test('Review Data lists an uploaded dataset and opens it in Explore @smoke', async ({
  authenticatedPage: page,
  uploadTestDataset,
  cleanupDataset,
}) => {
  test.slow();
  const datasetId = await uploadTestDataset();
  try {
    await page.goto('/review');
    // The newest upload is first, so .first() is the one just uploaded, not a leftover.
    const pick = page.getByRole('button', { name: /sample\.csv/ }).first();
    await expect(pick).toBeVisible({ timeout: 20000 });
    await expect(page.getByText(/"detail"|value_error/)).toHaveCount(0);

    await pick.click();
    await expect(page).toHaveURL(new RegExp(`/explore/${datasetId}`), { timeout: 20000 });
  } finally {
    await cleanupDataset(datasetId);
  }
});
