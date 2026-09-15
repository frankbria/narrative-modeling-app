import type { APIRequestContext, Browser, BrowserContext } from '@playwright/test';

/**
 * Direct backend calls from e2e specs authenticate exactly like the app does.
 *
 * The e2e backend runs with REAL auth (#493) — `test-e2e.sh` no longer sets
 * `SKIP_AUTH`, so a made-up bearer (`e2e-test-token`, `dev-user-default`) is a
 * 401. The only credential the backend accepts is the HS256 JWT the NextAuth
 * session callback mints (`session.apiToken`, #527), so read it from the
 * same-origin session endpoint of whichever context is signed in.
 *
 * Playwright's bare `request` fixture qualifies: the test runner merges the
 * project's `storageState` and `baseURL` into every `playwright.request.newContext()`
 * (`runBeforeCreateRequestContext` in playwright/lib/index.js), so it carries the
 * pre-authenticated session from global-setup exactly like `page.request` does.
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function apiAuthHeaders(
  request: APIRequestContext,
): Promise<{ Authorization: string }> {
  const session = await request.get('/api/auth/session');
  const body = (await session.json().catch(() => null)) as { apiToken?: unknown } | null;
  const token = body?.apiToken;
  if (typeof token !== 'string' || token.length === 0) {
    throw new Error(
      `apiAuthHeaders: /api/auth/session (${session.status()}) carries no apiToken — ` +
        'the request context is not signed in (storage state missing or expired).',
    );
  }
  return { Authorization: `Bearer ${token}` };
}

/**
 * A fresh, signed-in browser context for a SECOND tenant via the dev/test
 * credentials provider (`auth.ts`). `browser.newContext()` would inherit the
 * project's storageState (the pre-authenticated test user) and the sign-in page
 * bounces an authenticated visitor back into the app, so start empty.
 * The caller closes the context.
 */
export async function signInAs(
  browser: Browser,
  baseURL: string,
  email: string,
  password: string,
): Promise<BrowserContext> {
  const context = await browser.newContext({
    baseURL,
    storageState: { cookies: [], origins: [] },
  });
  const page = await context.newPage();
  await page.goto('/auth/signin');
  await page.locator('input[id="email"]').fill(email);
  await page.locator('input[id="password"]').fill(password);
  await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes('/api/auth/callback/credentials') && r.status() === 200,
      { timeout: 20000 },
    ),
    page.locator('button:has-text("Sign In with Test User")').click(),
  ]);
  // The callback set the session cookie on this context; the post-login
  // redirect target is irrelevant to requests made with the context's cookies.
  await page.close();
  return context;
}
