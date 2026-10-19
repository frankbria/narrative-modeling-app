import { execFileSync } from 'child_process';
import { mkdirSync } from 'fs';
import path from 'path';
import { test, expect } from '../fixtures';
import { API_BASE, apiAuthHeaders } from '../helpers/apiAuth';
import { isolatedEmail, isolatedState } from '../isolatedUsers';

/**
 * Re-records the public /how-it-works media (#772): the eight stage screenshots and the
 * silent churn walkthrough. Run `npm run capture:how-it-works` (docs/dev/E2E_TESTING_GUIDE.md).
 *
 * One pass through the real UI on the real stack, as the isolated `onboarding` user
 * (a new account: no history, not an admin, so no Admin nav). The signed-in account is
 * named at the bottom of the sidebar, so every frame is cropped above it (CROP_HEIGHT)
 * and to the left of the empty chat gutter (CROP_WIDTH): no address is ever in an image.
 * The walkthrough trains in Quick mode so it stays near a minute and a half.
 */
const VIEWPORT = { width: 2000, height: 1100 };
const CROP_WIDTH = 1680;
const CROP_HEIGHT = 860;
const PUBLIC_DIR = path.resolve(__dirname, '../../public/how-it-works');
// Time a viewer gets on each stage in the recording.
const DWELL_MS = 3500;
const WALKTHROUGH = path.join(PUBLIC_DIR, 'churn-walkthrough.webm');

test.use({
  storageState: isolatedState('onboarding'),
  viewport: VIEWPORT,
  video: { mode: 'on', size: VIEWPORT },
});

test('capture the eight stages and the churn walkthrough', async ({ authenticatedPage: page, request }, testInfo) => {
  test.setTimeout(420_000);
  mkdirSync(PUBLIC_DIR, { recursive: true });
  const headers = await apiAuthHeaders(page.request);
  await page.request.post(`${API_BASE}/onboarding/reset`, { headers });

  // The signed-in account (name and address) is shown in the sidebar. Fail the capture
  // unless every place it appears lies wholly outside the kept rectangle, so a layout
  // change cannot ship the test identity in an image or the video.
  const account = page.getByText(new RegExp(`${isolatedEmail('onboarding').replace(/[+.]/g, '\\$&')}|Test User`));
  const assertAccountCropped = async () => {
    await expect(account.first()).toBeVisible();
    for (const element of await account.all()) {
      const box = (await element.boundingBox())!;
      expect(box.y >= CROP_HEIGHT || box.x >= CROP_WIDTH, `account text at y=${box.y} is inside the crop`).toBe(true);
    }
  };

  // Wait for the page to settle, then write the cropped frame as <stage>.webp.
  const shoot = async (stage: string) => {
    await page.waitForLoadState('networkidle');
    await assertAccountCropped();
    await expect(page.locator('.animate-spin')).toHaveCount(0, { timeout: 30_000 });
    await page.waitForTimeout(1500);
    const png = testInfo.outputPath(`${stage}.png`);
    await page.screenshot({ path: png, clip: { x: 0, y: 0, width: CROP_WIDTH, height: CROP_HEIGHT } });
    execFileSync('ffmpeg', ['-y', '-i', png, '-c:v', 'libwebp', '-quality', '80', path.join(PUBLIC_DIR, `${stage}.webp`)]);
    await page.waitForTimeout(DWELL_MS);
  };
  const next = async (stageUrl: RegExp) => {
    await page.getByTestId('continue-button').click();
    await expect(page).toHaveURL(stageUrl, { timeout: 20_000 });
  };

  await page.goto('/upload');
  await shoot('data_loading');

  await page.goto('/onboarding');
  await page.getByText('Upload Your First Dataset', { exact: true }).first().click();
  await page.getByRole('button', { name: /browse samples/i }).click();
  await expect(page.getByText('Customer Churn Prediction')).toBeVisible({ timeout: 20_000 });
  await page.getByRole('button', { name: /^use this$/i }).first().click();
  await expect(page).toHaveURL(/\/explore\/[0-9a-f]{24}/, { timeout: 30_000 });
  const datasetId = page.url().match(/\/explore\/([0-9a-f]{24})/)![1];
  await expect(page.locator('th', { hasText: 'monthly_charges' }).first()).toBeVisible({ timeout: 30_000 });
  await shoot('data_profiling');

  await page.getByRole('button', { name: /Continue to Data Preparation/ }).click();
  await expect(page).toHaveURL(/\/prepare/);
  await page.getByText('Remove Duplicates', { exact: true }).first().click();
  await page.getByRole('button', { name: /Apply & Continue/ }).click();
  await expect(page.getByTestId('continue-button')).toBeEnabled({ timeout: 20_000 });
  await shoot('data_preparation');
  await next(/\/features/);

  await page.getByRole('button', { name: /^Use these \d+ columns$/ }).click();
  await shoot('feature_engineering');
  await next(/\/model/);

  const target = page.getByRole('combobox');
  await expect(target.getByRole('option', { name: 'churn' })).toBeAttached({ timeout: 30_000 });
  await target.selectOption('churn');
  await shoot('model_training');
  await page.getByText('Quick', { exact: true }).first().click();
  await page.getByRole('button', { name: /Start Training/ }).click();
  await expect(page.getByTestId('continue-button')).toBeEnabled({ timeout: 240_000 });
  await page.waitForTimeout(2000);
  await next(/\/evaluate/);

  await shoot('model_evaluation');
  await next(/\/predict/);

  await page.getByLabel('tenure', { exact: true }).fill('12');
  await page.getByLabel('monthly_charges', { exact: true }).fill('70');
  await page.getByLabel('total_charges', { exact: true }).fill('840');
  await page.getByRole('button', { name: 'Make Prediction' }).click();
  await expect(page.getByTestId('continue-button')).toBeEnabled({ timeout: 30_000 });
  // The result sits below the form: bring it up under the stage bar.
  await page.getByText('Prediction Result').evaluate((el) => window.scrollBy(0, el.getBoundingClientRect().top - 280));
  await shoot('prediction');
  await next(/\/deploy/);
  await shoot('deployment');

  // The walkthrough: the recording of this same pass, cropped like the screenshots.
  const video = page.video()!;
  await page.close();
  const raw = testInfo.outputPath('walkthrough-raw.webm');
  await video.saveAs(raw);
  execFileSync('ffmpeg', [
    '-y', '-ss', '1', '-i', raw,
    '-vf', `crop=${CROP_WIDTH}:${CROP_HEIGHT}:0:0,scale=1280:-2`,
    '-c:v', 'libvpx-vp9', '-crf', '42', '-b:v', '0', '-an',
    WALKTHROUGH,
  ]);

  await request.delete(`${API_BASE}/user_data/${datasetId}`, { headers });
});
