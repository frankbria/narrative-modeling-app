import { test, expect } from '../fixtures';
import { API_BASE, apiAuthHeaders, signInAs } from '../helpers/apiAuth';

/**
 * A real plan-limit 402 reaches the user as the PlanLimitDialog (#767 AC2/AC5).
 *
 * Every spec shares one FREE user whose ceilings test-e2e.sh lifts to the
 * thousands, and a limit is per tier, so the shared user can never hit one.
 * The second identity (#613) is seeded on PRO (scripts/seed_e2e_data.py) and
 * PRO's upload ceiling is `PLAN_PRO_UPLOADS=2` in test-e2e.sh; nothing else
 * uploads as that tenant. Usage persists across runs on a local Mongo, so the
 * spec uploads until the dialog appears (at most ceiling + 1 attempts) rather
 * than assuming a fresh counter.
 */
test.describe('plan-limit dialog (#767)', () => {
  test('a tenant at their upload ceiling sees the dialog with the backend numbers @smoke', async ({
    browser,
    baseURL,
  }) => {
    const email = process.env.TEST_ADMIN_EMAIL;
    const secret = process.env.TEST_ADMIN_PASSWORD;
    expect(email, 'TEST_ADMIN_EMAIL must be exported (test-e2e.sh does)').toBeTruthy();
    expect(secret, 'TEST_ADMIN_PASSWORD must be exported (test-e2e.sh does)').toBeTruthy();

    const context = await signInAs(browser, baseURL as string, email as string, secret as string);
    try {
      // Prove the tenant is on the small ceiling first, so a dialog that never
      // appears is a real failure and a 402 that never comes is not "flaky".
      const headers = await apiAuthHeaders(context.request);
      const status = await context.request.get(`${API_BASE}/billing/status`, { headers });
      expect(status.ok(), await status.text()).toBeTruthy();
      const billing = await status.json();
      expect(billing.tier).toBe('pro');
      const ceiling: number = billing.limits.uploads;
      expect(ceiling).toBeGreaterThan(0);
      expect(ceiling).toBeLessThanOrEqual(5);

      const page = await context.newPage();
      const dialog = page.getByTestId('plan-limit-dialog');

      for (let attempt = 0; attempt <= ceiling; attempt += 1) {
        await page.goto('/upload');
        await page.getByTestId('upload-dropzone').waitFor({ state: 'visible', timeout: 10000 });
        await page.getByTestId('file-input').setInputFiles({
          name: `plan-limit-${attempt}.csv`,
          mimeType: 'text/csv',
          buffer: Buffer.from('age,income,purchased\n25,50000,yes\n35,75000,no\n45,60000,yes\n'),
        });
        const uploadButton = page.getByTestId('upload-button');
        await uploadButton.and(page.locator(':not([disabled])')).waitFor({ state: 'visible', timeout: 5000 });
        await uploadButton.click();
        // On a 402 the inline error panel and the dialog appear together, so
        // `.first()` keeps the union out of strict mode.
        await page
          .getByTestId('upload-status')
          .or(page.getByTestId('upload-error'))
          .or(dialog)
          .first()
          .waitFor({ state: 'visible', timeout: 30000 });
        if (await dialog.isVisible()) break;
      }

      await expect(dialog).toBeVisible();
      await expect(dialog).toContainText("Pro plan's uploads limit");
      // The numbers are the backend's: used has reached the ceiling.
      await expect(page.getByTestId('plan-limit-usage')).toHaveText(`${ceiling} of ${ceiling}`);
      await expect(dialog).toContainText(/resets on/);
      // PRO has no upgrade; the action is the Enterprise contact link.
      const contact = dialog.getByRole('link', { name: /contact us/i });
      await expect(contact).toBeVisible();
      expect(await contact.getAttribute('href')).toMatch(/^mailto:/);
      await expect(dialog.getByRole('link', { name: /upgrade/i })).toHaveCount(0);

      // The inline error stays informative too — the backend's own sentence.
      await expect(page.getByTestId('upload-error-message')).toContainText(/used all/i);
    } finally {
      await context.close();
    }
  });
});
