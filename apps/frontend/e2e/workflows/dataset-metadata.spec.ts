/**
 * What the Explore pages show about an uploaded dataset, on the real stack (#991).
 *
 * `uploadTestDataset` lands on `/explore/{id}`, whose heading is the file's name.
 * Every dataset is erased afterwards.
 */

import { test, expect } from '../fixtures';
import type { Page } from '@playwright/test';

/** The value on the explore page's stat card with this label. */
const statCard = (page: Page, label: string) =>
  page.getByText(label, { exact: true }).locator('..');

/** The explore page runs `/data/process` for a fresh upload; wait until it has. */
async function processed(page: Page) {
  await expect(page.getByText('Processing Dataset')).toBeHidden({ timeout: 60000 });
}

test.describe('Dataset metadata', () => {
  const created: string[] = [];

  test.beforeEach(() => {
    test.slow();
  });

  test.afterEach(async ({ cleanupDataset }) => {
    for (const id of created.splice(0)) await cleanupDataset(id);
  });

  test('shows the dataset name, its shape and a preview', async ({
    authenticatedPage: page,
    uploadTestDataset,
  }) => {
    created.push(await uploadTestDataset());

    await expect(page.getByRole('heading', { level: 1, name: 'sample.csv', exact: true })).toBeVisible();
    await expect(statCard(page, 'Rows')).toContainText('5');
    await expect(statCard(page, 'Columns')).toContainText('3');
    await expect(page.locator('table').first()).toBeVisible();
  });

  test('infers a schema for every column', async ({ authenticatedPage: page, uploadTestDataset }) => {
    created.push(await uploadTestDataset());
    await processed(page);

    await page.getByRole('tab', { name: 'Schema' }).click();
    const panel = page.getByRole('tabpanel');
    await expect(panel.getByRole('columnheader', { name: 'Data Type' })).toBeVisible();
    for (const column of ['age', 'income', 'purchased']) {
      await expect(panel.getByRole('cell', { name: column, exact: true })).toBeVisible();
    }
  });

  test("lists the user's datasets", async ({ authenticatedPage: page, uploadTestDataset }) => {
    created.push(await uploadTestDataset());
    created.push(await uploadTestDataset());

    await page.goto('/explore');
    for (const id of created) {
      await expect(page.locator(`a[href="/explore/${id}"]`)).toBeVisible();
    }
  });

  // large-dataset.csv carries emails and phone numbers, so /upload stops at the high-risk
  // PII warning, which crashes the page today (app/upload/page.tsx reads
  // `affected_columns`, a field the backend does not send). #1054 fixes the warning;
  // this test then needs to confirm it before it can wait for the upload.
  test.fixme('reads a 10,000-row dataset', async ({ authenticatedPage: page, uploadTestDataset }) => {
    created.push(await uploadTestDataset('large-dataset.csv'));

    await expect(statCard(page, 'Rows')).toContainText('10,000');
    await expect(statCard(page, 'Columns')).toContainText('16');
  });

  test('reports missing values in the quality report', async ({
    authenticatedPage: page,
    uploadTestDataset,
  }) => {
    created.push(await uploadTestDataset('missing-values.csv'));
    await processed(page);

    await page.getByRole('tab', { name: 'Quality' }).click();
    await expect(page.getByText(/Missing values detected in column/).first()).toBeVisible();
  });

  test('keeps a filename with spaces and brackets', async ({
    authenticatedPage: page,
    uploadTestDataset,
  }) => {
    // No such file exists in test-data, so the fixture uploads its inline CSV under this name.
    created.push(await uploadTestDataset('test-data_2024-01-15 (final).csv'));

    await expect(
      page.getByRole('heading', { level: 1, name: 'test-data_2024-01-15 (final).csv', exact: true })
    ).toBeVisible();
  });
});
