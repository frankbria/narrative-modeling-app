import { test, expect } from '../fixtures';
import { apiAuthHeaders } from '../helpers/apiAuth';
import { isolatedState } from '../isolatedUsers';
import { textLayoutProblems } from '../helpers/layoutProblems';
import { expectLandedOnStage } from '../helpers/landing';

/**
 * #470 — the onboarding flow every first-time user is forced into must talk to the
 * backend. Before the fix its requests went to `/api/v1/onboarding/...` on the FRONTEND
 * origin (404, no auth) while the mocked e2e routes matched on `url.includes(...)` and
 * kept passing. This spec uses NO route mocks: real backend, real session, and it asserts
 * that no onboarding request answered >= 400 — the assertion that fails on main.
 */

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// This spec resets its user's onboarding progress, so it is its own user (#743): as the
// shared one, every other spec's dashboard visit bounced to /onboarding while it ran.
test.use({ storageState: isolatedState('onboarding') });

// Both tests reset that one user's progress, so they must not interleave.
test.describe.configure({ mode: 'serial' });

test.describe('Onboarding talks to the backend (#470)', () => {
  test('a brand-new user walks onboarding to completion with no failed request @smoke', async ({
    authenticatedPage: page,
  }) => {
    // A brand-new user: reset this account's progress through the backend itself.
    const reset = await page.request.post(`${API}/onboarding/reset`, {
      headers: await apiAuthHeaders(page.request),
    });
    expect(reset.ok(), `reset: ${reset.status()}`).toBeTruthy();

    const failed: string[] = [];
    page.on('response', (r) => {
      if (r.url().includes('/onboarding/') && r.status() >= 400) failed.push(`${r.status()} ${r.url()}`);
    });

    await page.goto('/onboarding');
    // After a reset the backend already points at the first step, so the page renders the
    // step panel directly; the "Start Tutorial" landing card shows only when it does not.
    const start = page.getByRole('button', { name: /start tutorial/i });
    const complete = page.getByRole('button', { name: /mark as complete/i });
    await expect(start.or(complete).first()).toBeVisible({ timeout: 20000 });
    if (await start.isVisible()) await start.click();

    // Walk the seven steps: complete where the backend accepts it, otherwise skip.
    for (let i = 0; i < 12 && !(await page.getByText(/congratulations/i).isVisible()); i++) {
      const skip = page.getByRole('button', { name: /skip step/i });
      if (await complete.isVisible()) {
        const statusRefetch = page
          .waitForResponse((r) => r.url().includes('/onboarding/status'), { timeout: 8000 })
          .then(() => true, () => false);
        await complete.click();
        // the page refetches status on success; a refused step is skipped instead
        if (!(await statusRefetch) && (await skip.isVisible())) await skip.click();
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

/**
 * #770 AC2 — the sample datasets used to be 14 rows, so step 4 ("Train Your First Model")
 * ran AutoML on data too small to train. This loads a sample the way a new user does (from
 * step 2's "Browse Samples"), trains it on the real backend in quick mode, checks the model
 * clears the score the catalogue quotes, and marks step 4 complete in the UI. No route mocks.
 */
test.describe('Onboarding sample trains (#770)', () => {
  test('a new user loads a sample in onboarding and trains it to the quoted score @smoke', async ({
    authenticatedPage: page,
    trainModel,
  }) => {
    test.setTimeout(180_000);
    const headers = await apiAuthHeaders(page.request);
    expect((await page.request.post(`${API}/onboarding/reset`, { headers })).ok()).toBeTruthy();

    const failed: string[] = [];
    page.on('response', (r) => {
      if (r.url().includes('/onboarding/') && r.status() >= 400) failed.push(`${r.status()} ${r.url()}`);
    });

    // Step 2 offers the samples. The catalogue lists churn first.
    await page.goto('/onboarding');
    await page.getByText('Upload Your First Dataset', { exact: true }).first().click();
    await page.getByRole('button', { name: /browse samples/i }).click();
    await expect(page.getByText('Customer Churn Prediction')).toBeVisible({ timeout: 20000 });
    await expect(page.getByText('2,000', { exact: true }).first()).toBeVisible();
    await page.getByRole('button', { name: /^use this$/i }).first().click();

    // Loading creates the user's own dataset and moves them to it, and they stay there:
    // the address alone matched for an instant before the stage guard sent a user whose
    // load had not completed Data Loading back to /upload (#810).
    await expectLandedOnStage(page, /\/explore\/[0-9a-f]{24}/, 'Data Profiling');
    // ...with the sample's own rows on the page (the Overview tab's preview table).
    await expect(page.locator('th', { hasText: 'monthly_charges' }).first()).toBeVisible({ timeout: 30000 });
    const datasetId = page.url().match(/\/explore\/([0-9a-f]{24})/)![1];

    // Step 4's work, on the real backend: a quick-mode AutoML run.
    const modelId = await trainModel(datasetId, 'churn', { training_mode: 'quick' });
    const model = await (await page.request.get(`${API}/ml/${modelId}`, { headers })).json();
    const samples = await (await page.request.get(`${API}/onboarding/sample-datasets`, { headers })).json();
    const churn = samples.find((s: { dataset_id: string }) => s.dataset_id === 'customer_churn');
    expect(model.problem_type).toBe('binary_classification');
    expect(model.test_score).toBeGreaterThanOrEqual(churn.expected_accuracy);

    // ...and the user marks step 4 done.
    await page.goto('/onboarding');
    await page.getByText('Train Your First Model', { exact: true }).first().click();
    const saved = page.waitForResponse((r) => r.url().includes('/onboarding/steps/train_model/complete'));
    await page.getByRole('button', { name: /mark as complete/i }).click();
    expect((await saved).ok()).toBeTruthy();

    const steps = await (await page.request.get(`${API}/onboarding/steps`, { headers })).json();
    expect(steps.find((s: { step_id: string }) => s.step_id === 'train_model').status).toBe('completed');
    expect(failed, 'onboarding requests that failed').toEqual([]);
  });
});

/**
 * #809 — the page sits beside the app sidebar, so its own width is far less than the
 * viewport's. Keyed to the viewport, the progress column was about 120px at 1280: step
 * titles cut to "Welc…", the points badge out of its row, the two count labels on top of
 * each other. Measured in a real browser at the three widths the issue names.
 */
test.describe('Onboarding progress card at desktop widths (#809)', () => {
  test('nothing in the progress card is cut off, outside it, or overlapping @smoke', async ({
    authenticatedPage: page,
  }) => {
    const headers = await apiAuthHeaders(page.request);
    expect((await page.request.post(`${API}/onboarding/reset`, { headers })).ok()).toBeTruthy();
    // An achievement puts the points badge and the two count labels on the card.
    const steps = await (await page.request.get(`${API}/onboarding/steps`, { headers })).json();
    let earned = 0;
    for (const step of steps as Array<{ step_id: string }>) {
      await page.request.post(`${API}/onboarding/steps/${step.step_id}/complete`, { headers, data: {} });
      const achievements = await (await page.request.get(`${API}/onboarding/achievements`, { headers })).json();
      earned = (achievements.achievements || []).length;
      if (earned > 0) break;
    }
    // The setup this test stands on, said plainly if the achievement rules ever change:
    // one achievement on the card, and a tutorial still in progress (a finished one shows
    // the completion screen, which has no progress card).
    const status = await (await page.request.get(`${API}/onboarding/status`, { headers })).json();
    expect(earned, 'completing early steps should earn an achievement to put on the card').toBeGreaterThan(0);
    expect(status.is_onboarding_complete, 'the tutorial must still be in progress').toBe(false);

    for (const width of [1024, 1280, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto('/onboarding');
      await expect(page.getByText('Tutorial Steps')).toBeVisible({ timeout: 20000 });
      await expect(page.getByText(/points$/).first()).toBeVisible();
      expect(await textLayoutProblems(page, 'Your Progress'), `at ${width}px`).toEqual([]);
    }
  });
});
