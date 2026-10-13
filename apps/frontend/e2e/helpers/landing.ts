import { expect, type Page } from '@playwright/test';

const GUARD_SETTLE_MS = 1000;

/**
 * The page landed on a workflow stage and stayed there (#810).
 *
 * `toHaveURL` / `waitForURL` pass the instant the address matches. A stage-gated page
 * decides whether the user may be there only once the workflow state has loaded, and
 * then bounces them to the earliest unfinished stage: a spec that stops at the address
 * passes while the user ends up on /upload. That is how a loaded sample that never
 * completed Data Loading went unseen (#770).
 *
 * So, in order: the address; the stage bar naming this stage as the current one (it
 * names only the current stage, the others show their number, and it follows the
 * same workflow state the guard reads, so it turns only once that state has loaded);
 * then a moment for a guard to act, after which there must be no guard banner and
 * still the same address.
 */
export async function expectLandedOnStage(page: Page, url: RegExp, stage: string): Promise<void> {
  await expect(page).toHaveURL(url, { timeout: 30000 });
  await expect(page.getByRole('button', { name: stage, exact: true })).toHaveText(stage, { timeout: 15000 });
  // A fixed wait on purpose: there is nothing to wait FOR when a guard does not fire, and
  // after a client-side transition the document is already idle. The guard redirects in
  // the effect that follows the workflow state loading, well inside this.
  await page.waitForTimeout(GUARD_SETTLE_MS);
  await expect(page.getByTestId('stage-guard-banner')).toHaveCount(0);
  await expect(page).toHaveURL(url);
}
