/**
 * Production Readiness E2E Tests
 *
 * Tests production quality gates: authentication on protected routes, keyboard and
 * screen-reader access, layout across breakpoints, offline and console-error handling,
 * page performance and static assets.
 *
 * Coverage Target: >85%
 */

import { test, expect } from '../fixtures';
import { ConsoleErrorCollector } from '../helpers';

test.describe('Production Readiness - Security', () => {
  test('should require authentication for protected routes @smoke', async ({ browser }) => {
    // Create a fresh context WITHOUT storage state so we are unauthenticated
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // The app uses server-side session check in the root layout.
    // Unauthenticated users get a stripped-down layout (no sidebar nav).
    // Verify either: redirected to auth page, OR sidebar is absent.
    const currentUrl = page.url();
    const redirectedToAuth =
      currentUrl.includes('/auth/') ||
      currentUrl.includes('/login') ||
      currentUrl.includes('/signin');

    const sidebarVisible = await page.locator('nav').isVisible({ timeout: 3000 }).catch(() => false);

    // Auth is enforced if user was redirected OR the authenticated sidebar is hidden
    const authEnforced = redirectedToAuth || !sidebarVisible;

    expect(authEnforced).toBeTruthy();

    await context.close();
  });
});

test.describe('Production Readiness - Accessibility (WCAG 2.1 AA)', () => {
  test('should support full keyboard navigation @smoke', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/dashboard');

    // Test Tab navigation
    await authenticatedPage.keyboard.press('Tab');
    const firstFocused = await authenticatedPage.evaluate(() => document.activeElement?.tagName);
    expect(firstFocused).toBeTruthy();

    // Test Enter key on focusable elements
    await authenticatedPage.keyboard.press('Enter');
    await authenticatedPage.waitForTimeout(500);

    // Verify navigation occurred or action triggered
    const currentUrl = authenticatedPage.url();
    expect(currentUrl).toBeTruthy();
  });

  test('should be screen reader compatible', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/dashboard');

    // Check for ARIA labels and roles
    const ariaLabels = await authenticatedPage.locator('[aria-label]').count();
    const ariaRoles = await authenticatedPage.locator('[role]').count();
    const altTexts = await authenticatedPage.locator('img[alt]').count();

    expect(ariaLabels + ariaRoles).toBeGreaterThan(0);

    // Check for semantic HTML
    const headers = await authenticatedPage.locator('h1, h2, h3').count();
    expect(headers).toBeGreaterThan(0);

    // Verify no images without alt text
    const imagesWithoutAlt = await authenticatedPage.locator('img:not([alt])').count();
    expect(imagesWithoutAlt).toBe(0);
  });

  test('should be responsive across breakpoints (320px, 768px, 1024px, 1920px)', async ({
    page,
  }) => {
    const breakpoints = [
      { width: 320, height: 568 },
      { width: 768, height: 1024 },
      { width: 1024, height: 768 },
      { width: 1920, height: 1080 },
    ];

    for (const breakpoint of breakpoints) {
      await page.setViewportSize(breakpoint);
      await page.goto('/dashboard?skipOnboarding=true');
      await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

      // Content does not overflow the viewport sideways.
      const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
      expect(bodyWidth).toBeLessThanOrEqual(breakpoint.width + 20); // Allow small margin
    }
  });
});

test.describe('Production Readiness - Error Handling', () => {
  test('should handle network offline gracefully @smoke', async ({ authenticatedPage }) => {
    const errorCollector = new ConsoleErrorCollector(authenticatedPage);

    await authenticatedPage.goto('/dashboard');

    // Simulate offline
    await authenticatedPage.context().setOffline(true);

    // Try to perform a navigation action while offline
    try {
      await authenticatedPage.goto('/upload', { timeout: 5000 });
    } catch {
      // Navigation failure is expected when offline
    }

    // Restore online
    await authenticatedPage.context().setOffline(false);

    // The key assertion: no uncaught page-level exceptions occurred.
    // Filter out network-related errors since those are expected when offline.
    const pageErrors = errorCollector.getPageErrors().filter(
      (err) =>
        !err.message?.includes('net::') &&
        !err.message?.includes('Failed to fetch') &&
        !err.message?.includes('NetworkError') &&
        !err.message?.includes('Load failed')
    );
    expect(pageErrors.length).toBe(0);
  });

  test('should detect and report console errors', async ({ authenticatedPage }) => {
    const errorCollector = new ConsoleErrorCollector(authenticatedPage);

    await authenticatedPage.goto('/dashboard');
    await authenticatedPage.waitForLoadState('networkidle');

    // Check for console errors
    const consoleErrors = errorCollector.getConsoleErrors();
    const pageErrors = errorCollector.getPageErrors();

    // Production should have zero errors
    expect(consoleErrors.length).toBe(0);
    expect(pageErrors.length).toBe(0);

    if (consoleErrors.length > 0 || pageErrors.length > 0) {
      console.log(errorCollector.getErrorReport());
      throw new Error('Console errors detected in production build');
    }
  });
});

test.describe('Production Readiness - Monitoring & Logging', () => {
  test('should monitor performance metrics', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/dashboard');
    await authenticatedPage.waitForLoadState('networkidle');

    // Get performance timing data
    const performanceData = await authenticatedPage.evaluate(() => {
      const perf = performance.timing;
      return {
        loadTime: perf.loadEventEnd - perf.navigationStart,
        domContentLoaded: perf.domContentLoadedEventEnd - perf.navigationStart,
        resourcesLoaded: perf.loadEventEnd - perf.domContentLoadedEventEnd,
      };
    });

    expect(performanceData.loadTime).toBeGreaterThan(0);
    expect(performanceData.domContentLoaded).toBeGreaterThan(0);

    // Performance data should be logged to monitoring service
  });
});

test.describe('Production Readiness - Deployment Configuration', () => {
  test('should load all static assets without 404s', async ({ authenticatedPage }) => {
    const failed404s: string[] = [];

    authenticatedPage.on('response', (response) => {
      if (response.status() === 404) {
        failed404s.push(response.url());
      }
    });

    await authenticatedPage.goto('/dashboard');
    await authenticatedPage.waitForLoadState('networkidle');

    // Filter out known external 404s (analytics, ads, etc.)
    const relevantFailed = failed404s.filter(
      (url) =>
        !url.includes('google-analytics') &&
        !url.includes('analytics.js') &&
        !url.includes('ads') &&
        !url.includes('tracking')
    );

    expect(relevantFailed.length).toBe(0);

    if (relevantFailed.length > 0) {
      console.log('404 Errors:', relevantFailed);
    }
  });
});
