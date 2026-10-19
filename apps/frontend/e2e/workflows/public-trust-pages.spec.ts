import { test, expect } from '../fixtures';
import { gluedBoundaries } from '../helpers/gluedText';
import { COMPANY, SUB_PROCESSORS } from '../../lib/legal/company';
import { WORKFLOW_STAGES } from '../../lib/types/workflow';

/**
 * `/security` and `/how-it-works` are public (#772), observed end to end, signed out.
 *
 * The unit tests render the pages; only an anonymous document request proves
 * middleware lets exactly these two paths through, that the served HTML carries the
 * single-sourced content, that the images and video the page names are really served,
 * and that the API description the trust page links answers.
 */
test.describe('trust pages are public (#772)', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  const html = { Accept: 'text/html' };

  test('an anonymous request to /security gets the sub-processors, the refund window and the shared nav @smoke', async ({
    request,
  }) => {
    const response = await request.get('/security', { headers: html, maxRedirects: 0 });
    expect(response.status()).toBe(200);
    const body = await response.text();
    for (const processor of SUB_PROCESSORS) expect(body).toContain(processor.privacyUrl);
    // `{n} days` is served as `n<!-- --> days`.
    expect(body).toMatch(new RegExp(`${COMPANY.refundWindowDays}(?:<!-- -->)? days`));
    expect(body).toContain('aria-label="Public"');
    expect(body).not.toContain('aria-label="Sidebar"');
    expect(body).not.toMatch(/backup/i);
    expect(gluedBoundaries(body)).toEqual([]);
  });

  test('the API description it links is served and is an OpenAPI document @smoke', async ({ page, request }) => {
    await page.goto('/security');
    const href = await page.getByRole('link', { name: 'openapi.json' }).getAttribute('href');
    const spec = await request.get(href!);
    expect(spec.status()).toBe(200);
    expect((await spec.json()).openapi).toMatch(/^3\./);
  });

  test('an anonymous request to /how-it-works names every stage and serves its images and the walkthrough @smoke', async ({
    request,
    page,
  }) => {
    const response = await request.get('/how-it-works', { headers: html, maxRedirects: 0 });
    expect(response.status()).toBe(200);
    const body = await response.text();
    for (const stage of WORKFLOW_STAGES) expect(body).toContain(stage.name);
    expect(gluedBoundaries(body)).toEqual([]);

    await page.goto('/how-it-works');
    const srcs = await page.locator('img[src^="/how-it-works/"]').evaluateAll((imgs) =>
      imgs.map((img) => img.getAttribute('src')),
    );
    expect(srcs).toHaveLength(WORKFLOW_STAGES.length);
    const walkthrough = await page.locator('video source').getAttribute('src');
    for (const src of [...srcs, walkthrough]) {
      const asset = await request.get(src!, { maxRedirects: 0 });
      expect(asset.status(), src!).toBe(200);
      expect(asset.headers()['content-type'], src!).toMatch(/^(image|video)\//);
    }
  });

  test('the nav and footer links lead from one public page to the next @smoke', async ({ page }) => {
    await page.goto('/how-it-works');
    await page.getByRole('navigation', { name: 'Public' }).getByRole('link', { name: 'Security' }).click();
    await expect(page).toHaveURL(/\/security$/);
    await page.getByRole('contentinfo').getByRole('link', { name: 'How it works' }).click();
    await expect(page).toHaveURL(/\/how-it-works$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('How it works');
  });

  test('only the exact paths are public: a child path still meets the sign-in wall @smoke', async ({ request }) => {
    for (const path of ['/security/extra', '/how-it-works/extra']) {
      const response = await request.get(path, { headers: html, maxRedirects: 0 });
      expect(response.status(), path).toBe(307);
      expect(response.headers()['location'], path).toContain('/auth/signin');
    }
  });
});
