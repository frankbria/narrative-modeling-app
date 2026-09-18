import { test, expect } from '../fixtures';

/**
 * /pricing is public (#475) — observed end to end.
 *
 * middleware.ts exempts the exact path from the deny-by-default session wall;
 * the unit test mocks getToken, so only a real anonymous document request can
 * prove the page is reachable before an account exists. The lookalike check is
 * the other half: the exemption is a path, not a prefix.
 */
test.describe('/pricing is public (#475)', () => {
  // Drop the pre-authenticated storage state from playwright.config: these
  // requests must carry no session cookie at all.
  test.use({ storageState: { cookies: [], origins: [] } });

  test('an anonymous document request gets the pricing page @smoke', async ({ request }) => {
    const response = await request.get('/pricing', {
      headers: { Accept: 'text/html' },
      maxRedirects: 0,
    });
    expect(response.status()).toBe(200);
    const body = await response.text();
    expect(body).toContain('Pricing');
    expect(body).toContain('$49');
    // Signed-out branch of the root layout: no app chrome.
    expect(body).not.toContain('aria-label="Sidebar"');
  });

  test('a lookalike path is still behind the session wall @smoke', async ({ request }) => {
    const response = await request.get('/pricingx', {
      headers: { Accept: 'text/html' },
      maxRedirects: 0,
    });
    expect(response.status()).toBe(307);
    expect(response.headers()['location']).toContain('/auth/signin');
  });
});
