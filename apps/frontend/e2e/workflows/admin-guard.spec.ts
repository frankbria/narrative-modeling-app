import { test, expect } from '../fixtures';
import { signInAs } from '../helpers/apiAuth';

/**
 * /admin is authorised, not just authenticated (#477) — observed end to end (#613).
 *
 * middleware.ts rewrites a non-admin's /admin to Next's internal not-found route;
 * the unit test can only see the rewrite header, and Next has shipped soft-200
 * not-found regressions before. These two document requests pin the status the
 * browser actually gets. test-e2e.sh puts the admin identity on ADMIN_EMAILS and
 * leaves the ordinary test user off it, so both cases live in one server process.
 */
test.describe('/admin guard (#477, #613)', () => {
  test('an authenticated non-admin gets a hard 404 with no admin content @smoke', async ({
    authenticatedPage,
  }) => {
    // A document request through the page's own cookies — not a client-side
    // navigation, whose RSC fetch legitimately answers 200 with a not-found tree.
    const response = await authenticatedPage.request.get('/admin', {
      headers: { Accept: 'text/html' },
      maxRedirects: 0,
    });
    expect(response.status()).toBe(404);
    const body = await response.text();
    expect(body).not.toContain('Admin Dashboard');
  });

  test('a listed admin gets 200 and the dashboard heading @smoke', async ({ browser, baseURL }) => {
    // Both come from test-e2e.sh (which also puts the email on ADMIN_EMAILS);
    // there is deliberately no default for the secret.
    const adminEmail = process.env.TEST_ADMIN_EMAIL;
    const adminSecret = process.env.TEST_ADMIN_PASSWORD;
    expect(adminEmail, 'TEST_ADMIN_EMAIL must be exported (test-e2e.sh does)').toBeTruthy();
    expect(adminSecret, 'TEST_ADMIN_PASSWORD must be exported (test-e2e.sh does)').toBeTruthy();
    const context = await signInAs(browser, baseURL as string, adminEmail as string, adminSecret as string);
    try {
      const response = await context.request.get('/admin', {
        headers: { Accept: 'text/html' },
        maxRedirects: 0,
      });
      expect(response.status()).toBe(200);
      expect(await response.text()).toContain('Admin Dashboard');
    } finally {
      await context.close();
    }
  });
});
