/**
 * What the dashboard does when its backend calls fail (#991).
 *
 * Each recent list has its own failed state with a Retry button
 * (`components/dashboard/RecentLists.tsx`). The failures are mocked, since the UI's
 * reaction to them is the subject; each mock matches one pathname only.
 * Training errors are in training-errors.spec.ts.
 */

import { test, expect } from '../fixtures';
import type { Page } from '@playwright/test';

const isList = (name: string) => (url: URL) => url.pathname.endsWith(`/api/v1/${name}`);

/** Fail one list; returns the matcher, since unroute removes only the same reference. */
async function failList(page: Page, name: string) {
  const matcher = isList(name);
  await page.route(matcher, (route) =>
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Internal server error' }),
    })
  );
  return matcher;
}

test.describe('Dashboard error handling', () => {
  test('a failed list offers a retry that loads it', async ({ authenticatedPage: page }) => {
    const datasets = page.getByTestId('recent-datasets');
    const failing = await failList(page, 'datasets');
    await page.reload();
    await expect(datasets.getByText('Unable to load datasets')).toBeVisible();

    await page.unroute(failing);
    const reloaded = page.waitForResponse((r) => isList('datasets')(new URL(r.url())));
    await datasets.getByRole('button', { name: 'Retry' }).click();
    // The retry reaches the real backend, not the mock.
    expect((await reloaded).status()).toBe(200);
    await expect(datasets.getByText('Unable to load datasets')).toBeHidden();
  });

  test('both lists failing at once are each reported', async ({ authenticatedPage: page }) => {
    const pageErrors: Error[] = [];
    page.on('pageerror', (error) => pageErrors.push(error));
    await failList(page, 'datasets');
    await failList(page, 'models');
    await page.reload();

    await expect(page.getByTestId('recent-datasets').getByText('Unable to load datasets')).toBeVisible();
    await expect(page.getByTestId('recent-models').getByText('Unable to load models')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    expect(pageErrors).toEqual([]);
  });
});
