import { test, expect } from '../fixtures';
import type { Page } from '@playwright/test';

/**
 * #470 — the onboarding flow every first-time user is forced into must talk to the
 * backend. Before the fix its requests went to `/api/v1/onboarding/...` on the FRONTEND
 * origin (404, no auth) while the mocked e2e routes matched on `url.includes(...)` and
 * kept passing. This spec uses NO route mocks: real backend, real session, and it asserts
 * that no onboarding request answered >= 400 — the assertion that fails on main.
 */

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

async function apiToken(page: Page): Promise<string> {
  const session = await page.request.get('/api/auth/session');
  const body = await session.json();
  expect(body?.apiToken, 'the session must expose the minted API JWT').toBeTruthy();
  return body.apiToken as string;
}

test.describe('Onboarding talks to the backend (#470)', () => {
  test('a brand-new user walks onboarding to completion with no failed request @smoke', async ({
    authenticatedPage: page,
  }) => {
    // A brand-new user: reset this account's progress through the backend itself.
    const token = await apiToken(page);
    const reset = await page.request.post(`${API}/onboarding/reset`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(reset.ok(), `reset: ${reset.status()}`).toBeTruthy();

    const failed: string[] = [];
    page.on('response', (r) => {
      if (r.url().includes('/onboarding/') && r.status() >= 400) failed.push(`${r.status()} ${r.url()}`);
    });

    await page.goto('/onboarding');
    await expect(page.getByRole('button', { name: /start tutorial/i })).toBeVisible({ timeout: 20000 });
    await page.getByRole('button', { name: /start tutorial/i }).click();

    // Walk the steps: complete where the backend accepts it, otherwise skip. Seven steps.
    for (let i = 0; i < 12 && !(await page.getByText(/congratulations/i).isVisible()); i++) {
      const complete = page.getByRole('button', { name: /mark as complete/i });
      const skip = page.getByRole('button', { name: /skip step/i });
      if (await complete.isVisible()) {
        await complete.click();
        // either the next step renders, or the step refused and we skip it
        const moved = await Promise.race([
          page.waitForResponse((r) => r.url().includes('/onboarding/status'), { timeout: 8000 }).then(() => true),
          page.waitForTimeout(8000).then(() => false),
        ]);
        if (!moved && (await skip.isVisible())) await skip.click();
      } else if (await skip.isVisible()) {
        await skip.click();
      } else {
        break;
      }
      await page.waitForLoadState('networkidle');
    }

    await expect(page.getByText(/congratulations/i)).toBeVisible({ timeout: 20000 });
    expect(failed, 'onboarding requests that failed').toEqual([]);
  });
});
