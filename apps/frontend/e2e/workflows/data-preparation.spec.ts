/**
 * The Data Preparation stage's two views: Chain and Visual (#999).
 *
 * These tests used to drive `/datasets/{id}/prepare`, a legacy copy of the stage that
 * no navigation reached, and asserted that page's own header. They open the stage a
 * user gets, `/prepare`, with the workflow a user has after profiling. What the
 * pipeline does with its steps (preview, apply, history, recipes) is
 * prepare-pipeline.spec.ts.
 */

import { test, expect } from '../fixtures';
import type { Page, APIRequestContext } from '@playwright/test';
import { apiAuthHeaders } from '../helpers/apiAuth';

/**
 * Seed the workflow state a real user would have after completing profiling,
 * so the DATA_PROFILING-gated prepare page is reachable.
 *
 * Since #87 the backend is the source of truth during hydration: the upload
 * flow persists a backend workflow at the data_loading stage, which would
 * override a localStorage-only seed and re-gate the page. So seed the real
 * backend workflow (no mocking — E2E uses the live API) with the session's own
 * minted JWT (#493), so the seed is owned by the user that just uploaded the
 * dataset. The localStorage seed is kept as the offline fallback layer the app
 * reads when the backend is down.
 */
async function seedPreparationWorkflow(
  page: Page,
  request: APIRequestContext,
  datasetId: string
): Promise<void> {
  const apiBase =
    process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  const headers = {
    ...(await apiAuthHeaders(request)),
    'Content-Type': 'application/json',
  };
  const workflow = {
    current_stage: 'data_preparation',
    completed_stages: ['data_loading', 'data_profiling'],
    stage_data: {},
  };
  // PUT updates the workflow the upload flow already created; fall back to POST
  // if no workflow exists yet (upload didn't persist one). Fail loudly on any
  // other status so a broken seed surfaces as a clear error here instead of a
  // confusing "element not found" once the page redirects away from /prepare.
  const put = await request.put(`${apiBase}/workflows/${datasetId}`, {
    headers,
    data: workflow,
  });
  if (put.status() === 404) {
    const post = await request.post(`${apiBase}/workflows/${datasetId}`, {
      headers,
      data: workflow,
    });
    if (!post.ok()) {
      throw new Error(
        `seedPreparationWorkflow POST failed (${post.status()}): ${await post.text()}`
      );
    }
  } else if (!put.ok()) {
    throw new Error(
      `seedPreparationWorkflow PUT failed (${put.status()}): ${await put.text()}`
    );
  }

  // addInitScript (not evaluate): a still-open page persists its own in-memory
  // state on changes and would clobber a one-time seed; the init script
  // re-seeds before app code runs on every navigation.
  await page.addInitScript((id) => {
    localStorage.setItem(
      'workflowState',
      JSON.stringify({
        currentStage: 'data_preparation',
        completedStages: ['data_loading', 'data_profiling'],
        stageData: {},
        datasetId: id,
        lastUpdated: new Date().toISOString(),
      })
    );
  }, datasetId);
}

async function openPrepare(page: Page, datasetId: string): Promise<void> {
  await page.goto(`/prepare?datasetId=${datasetId}`);
  await expect(page.getByRole('heading', { name: 'Data Preparation' })).toBeVisible({ timeout: 15000 });
}

function viewButton(page: Page, name: 'Chain' | 'Visual') {
  return page.getByRole('group', { name: 'Pipeline view' }).getByRole('button', { name });
}

test.describe('Data Preparation stage views', () => {
  let datasetId: string;

  test.beforeEach(async ({ page, request, uploadTestDataset }) => {
    // #157: upload + workflow seeding can exceed the 30s test budget (hook/fixture
    // setup counts against it) under 2-core CI contention when a parallel worker
    // is training. test.slow() triples the budget.
    test.slow();
    datasetId = await uploadTestDataset();
    await seedPreparationWorkflow(page, request, datasetId);
  });

  test.afterEach(async ({ cleanupDataset }) => {
    if (datasetId) {
      await cleanupDataset(datasetId);
    }
  });

  test('opens on the Chain view with nothing in it, and Visual one click away @smoke', async ({
    authenticatedPage,
  }) => {
    await openPrepare(authenticatedPage, datasetId);

    await expect(viewButton(authenticatedPage, 'Chain')).toHaveAttribute('aria-pressed', 'true');
    await expect(viewButton(authenticatedPage, 'Visual')).toHaveAttribute('aria-pressed', 'false');
    await expect(authenticatedPage.getByText(/No transformations added yet/i)).toBeVisible();
  });

  test('a step added in one view is the same step in the other @smoke', async ({ authenticatedPage }) => {
    await openPrepare(authenticatedPage, datasetId);
    await authenticatedPage.getByRole('button', { name: /add remove duplicates/i }).click();

    const steps = authenticatedPage.getByRole('list', { name: 'Transformation pipeline steps' });
    await expect(steps.getByRole('listitem')).toHaveCount(1);

    await viewButton(authenticatedPage, 'Visual').click();
    await expect(viewButton(authenticatedPage, 'Visual')).toHaveAttribute('aria-pressed', 'true');
    await expect(steps).toHaveCount(0);
    await expect(authenticatedPage.locator('.react-flow__node')).toHaveCount(1);

    await viewButton(authenticatedPage, 'Chain').click();
    await expect(steps.getByRole('listitem')).toHaveCount(1);
  });

  test('the chain view names its steps and their controls for a screen reader @a11y', async ({
    authenticatedPage,
  }) => {
    await openPrepare(authenticatedPage, datasetId);

    // The live region is in the page before there is anything to announce.
    await expect(authenticatedPage.getByText('No transformations in pipeline')).toHaveAttribute('aria-live', 'polite');

    await authenticatedPage.getByRole('button', { name: /add remove duplicates/i }).click();
    const step = authenticatedPage
      .getByRole('list', { name: 'Transformation pipeline steps' })
      .getByRole('listitem', { name: /^Step 1 of 1: / });
    await expect(step).toBeVisible();
    await expect(step.getByRole('button', { name: 'Edit step 1' })).toBeVisible();
    await expect(step.getByRole('button', { name: 'Delete step 1' })).toBeVisible();
  });

  for (const viewport of [
    { name: 'a phone', width: 375, height: 667 },
    { name: 'a tablet', width: 768, height: 1024 },
  ]) {
    test(`both views are reachable on ${viewport.name}`, async ({ authenticatedPage }) => {
      await authenticatedPage.setViewportSize({ width: viewport.width, height: viewport.height });
      await openPrepare(authenticatedPage, datasetId);

      await viewButton(authenticatedPage, 'Visual').click();
      await expect(viewButton(authenticatedPage, 'Visual')).toHaveAttribute('aria-pressed', 'true');
      await viewButton(authenticatedPage, 'Chain').click();
      await expect(authenticatedPage.getByText(/No transformations added yet/i)).toBeVisible();
    });
  }
});
