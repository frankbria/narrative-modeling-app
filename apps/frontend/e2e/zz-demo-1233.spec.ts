import { test, expect } from '@playwright/test';

// Temporary: fails the smoke run on purpose so the #1233 artifact can be inspected. Reverted.
test('@smoke deliberate failure for the #1233 demo', async ({ page }) => {
  await page.goto('/');
  expect(1, 'deliberate failure for the #1233 demo').toBe(2);
});
