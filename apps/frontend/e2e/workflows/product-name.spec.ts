import { test, expect } from '../fixtures';

/**
 * One product name on the surfaces a person meets first (#765, #770).
 *
 * The browser title, the sidebar and the onboarding copy each carried a different
 * name, and the sign-up page was two buttons with no word about the product. The
 * jest suites read the same constant the pages do, so only the served pages can
 * show what a person actually sees.
 */
test.describe('one product name (#765)', () => {
  test('the signed-in app carries it in the title, the sidebar and the dashboard @smoke', async ({
    authenticatedPage: page,
  }) => {
    await expect(page).toHaveTitle('SheetPredict');
    await expect(
      page.getByRole('complementary', { name: 'Sidebar' }).getByRole('heading', { level: 1 }),
    ).toHaveText('SheetPredict');
    await expect(page.getByTestId('dashboard')).toContainText('Welcome to SheetPredict.');
  });

  test.describe('before an account exists', () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    test('the sign-up page says what the product does @smoke', async ({ request }) => {
      const response = await request.get('/auth/new-user', { headers: { Accept: 'text/html' } });
      expect(response.status()).toBe(200);
      const body = await response.text();
      expect(body).toContain('<title>SheetPredict</title>');
      expect(body).toContain('turns a spreadsheet into a validated, explained, deployable model in minutes');
    });
  });
});
