import { test, expect } from '../fixtures';
import { gluedBoundaries } from '../helpers/gluedText';
import { COMPANY } from '../../lib/legal/company';
import { PLANS, priceLabel } from '../../lib/billing/plans';

/**
 * `/` is the public landing page (#766) — observed end to end, signed out.
 *
 * The unit tests render the page; only a real anonymous document request proves
 * middleware lets it through, that the served HTML has the hero and a price from
 * the shared plan source, and that the crawler files are reachable and say the
 * right thing for this environment. test-e2e.sh sets no ENVIRONMENT, which is
 * exactly the non-production case robots.txt must hide.
 */
test.describe('landing page is public (#766)', () => {
  // Drop the pre-authenticated storage state from playwright.config: these
  // requests must carry no session cookie at all.
  test.use({ storageState: { cookies: [], origins: [] } });

  const html = { Accept: 'text/html' };

  test('an anonymous request to / gets the hero, the CTA and a price from PLANS @smoke', async ({ request }) => {
    const response = await request.get('/', { headers: html, maxRedirects: 0 });
    expect(response.status()).toBe(200);
    const body = await response.text();
    expect(body).toContain(COMPANY.valueLine);
    expect(body).toContain('href="/auth/signin"');
    const paid = PLANS.find((plan) => plan.price_usd_per_month);
    expect(paid).toBeDefined();
    expect(body).toContain(priceLabel(paid!));
    // Signed-out branch of the root layout: no app chrome.
    expect(body).not.toContain('aria-label="Sidebar"');
    expect(gluedBoundaries(body)).toEqual([]);
  });

  test('the hero is visible and its CTA leads to sign-in @smoke', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(COMPANY.valueLine);
    await page.getByRole('link', { name: 'Get started' }).click();
    await expect(page).toHaveURL(/\/auth\/signin/);
  });

  test('robots.txt hides a non-production site from crawlers @smoke', async ({ request }) => {
    const response = await request.get('/robots.txt', { maxRedirects: 0 });
    expect(response.status()).toBe(200);
    const body = await response.text();
    expect(body).toMatch(/Disallow: \/\s*$/m);
    expect(body).not.toMatch(/Allow:/);
    expect(body).not.toMatch(/Sitemap:/i);
  });

  test('sitemap.xml lists the public pages @smoke', async ({ request }) => {
    const response = await request.get('/sitemap.xml', { maxRedirects: 0 });
    expect(response.status()).toBe(200);
    const body = await response.text();
    for (const path of ['/pricing', '/legal/terms', '/legal/privacy']) {
      // Any host: test-e2e.sh starts the dev server without NEXTAUTH_URL, so the
      // host here is the fallback; the runtime host is pinned in the unit tests.
      expect(body).toMatch(new RegExp(`<loc>https?://[^<]+${path}</loc>`));
    }
  });

  test('the sign-in wall still stands behind it @smoke', async ({ request }) => {
    const response = await request.get('/dashboard', { headers: html, maxRedirects: 0 });
    expect(response.status()).toBe(307);
    expect(response.headers()['location']).toContain('/auth/signin');
  });
});

test('a signed-in visitor to / keeps the dashboard redirect @smoke', async ({ authenticatedPage: page }) => {
  await page.goto('/');
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByTestId('dashboard')).toBeVisible();
});
