import { chromium, FullConfig } from '@playwright/test';
import path from 'path';

/**
 * Global setup for Playwright tests
 * Authenticates once and saves the session state
 * This is more secure and efficient than using SKIP_AUTH
 */
async function globalSetup(config: FullConfig) {
  const { baseURL } = config.projects[0].use;
  const storageStatePath = path.join(__dirname, '.auth', 'user.json');

  // Test user credentials
  const testEmail = process.env.TEST_USER_EMAIL || 'test@narrativeml.com';
  const testPassword = process.env.TEST_USER_PASSWORD || 'test-password-123';

  console.log('🔐 Setting up authentication for E2E tests...');
  console.log(`   Test user: ${testEmail}`);

  // Launch browser and create new page
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Navigate to sign-in page
    await page.goto(`${baseURL}/auth/signin`);
    await page.waitForLoadState('networkidle');

    // The signin page shows test user login in development mode
    // Fill in the email and password fields
    const emailInput = page.locator('input[id="email"]');
    const passwordInput = page.locator('input[id="password"]');

    await emailInput.waitFor({ state: 'visible', timeout: 10000 });
    await emailInput.fill(testEmail);
    await passwordInput.fill(testPassword);

    // Click the "Sign In with Test User" button and wait for navigation
    const signInButton = page.locator('button:has-text("Sign In with Test User")');

    // Wait for navigation after clicking sign-in
    await Promise.all([
      page.waitForResponse(
        response => response.url().includes('/api/auth/callback/credentials') && response.status() === 200,
        { timeout: 10000 }
      ),
      signInButton.click(),
    ]);

    // Give NextAuth time to set the cookie and complete the redirect
    await page.waitForTimeout(2000);

    // Wait for redirect to complete - check if we're no longer on the signin page
    await page.waitForURL(url => !url.toString().includes('/auth/signin'), { timeout: 15000 });

    // Verify we're authenticated by checking for session cookie
    const cookies = await context.cookies();
    const hasSessionCookie = cookies.some(
      cookie => cookie.name.includes('authjs.session-token')
    );

    if (!hasSessionCookie) {
      throw new Error('Authentication failed - no session cookie found');
    }

    console.log('✅ Authentication successful');
    console.log(`   Redirected to: ${page.url()}`);

    // Save the authenticated state
    await context.storageState({ path: storageStatePath });
    console.log(`💾 Saved auth state to: ${storageStatePath}`);

  } catch (error) {
    console.error('❌ Authentication setup failed:', error);
    throw error;
  } finally {
    await browser.close();
  }
}

export default globalSetup;
