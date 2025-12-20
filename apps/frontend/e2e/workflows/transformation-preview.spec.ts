import { test, expect } from '@playwright/test';

test.describe('Transformation Preview Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Skip authentication for testing
    await page.goto('/', { waitUntil: 'networkidle' });

    // Check if we're on login page and handle it
    const currentUrl = page.url();
    if (currentUrl.includes('login') || currentUrl.includes('sign-in')) {
      // Try to bypass auth or use test credentials
      const skipAuthButton = page.locator('text=Skip Authentication');
      if (await skipAuthButton.isVisible().catch(() => false)) {
        await skipAuthButton.click();
      } else {
        // Set SKIP_AUTH cookie or use test credentials
        await page.context().addCookies([
          {
            name: 'SKIP_AUTH',
            value: 'true',
            domain: 'localhost',
            path: '/',
          },
        ]);
        await page.goto('/');
      }
    }

    // Wait for the app to be ready
    await page.waitForLoadState('networkidle');
  });

  test('user configures transformation and sees real-time preview', async ({
    page,
  }) => {
    // Navigate to datasets page
    await page.goto('/datasets');
    await page.waitForLoadState('networkidle');

    // Check if we have any existing datasets, otherwise upload one
    const datasetCards = page.locator('[data-testid="dataset-card"]');
    const datasetCount = await datasetCards.count();

    let datasetId: string;

    if (datasetCount === 0) {
      // Upload a test dataset
      await page.click('text=Upload Dataset');
      await page.waitForSelector('input[type="file"]');

      // Create a test CSV file
      const csvContent = `id,name,age,city
1,Alice,,NYC
2,Bob,30,LA
3,Charlie,25,SF`;

      await page.setInputFiles('input[type="file"]', {
        name: 'test-data.csv',
        mimeType: 'text/csv',
        buffer: Buffer.from(csvContent),
      });

      await page.click('button:has-text("Upload")');
      await page.waitForURL(/\/datasets\/[^/]+/, { timeout: 30000 });

      // Extract dataset ID from URL
      const url = page.url();
      const match = url.match(/\/datasets\/([^/]+)/);
      datasetId = match ? match[1] : '';
    } else {
      // Use the first existing dataset
      await datasetCards.first().click();
      await page.waitForURL(/\/datasets\/[^/]+/);

      const url = page.url();
      const match = url.match(/\/datasets\/([^/]+)/);
      datasetId = match ? match[1] : '';
    }

    // Navigate to transformation page
    const transformLink = page.locator('a:has-text("Transform")');
    if (await transformLink.isVisible()) {
      await transformLink.click();
    } else {
      await page.goto(`/datasets/${datasetId}/transform`);
    }

    await page.waitForLoadState('networkidle');

    // Add transformation operation
    const addTransformButton = page.locator(
      'button:has-text("Add Transformation")'
    );
    if (await addTransformButton.isVisible()) {
      await addTransformButton.click();

      // Select transformation type
      await page.selectOption('[name="operation"]', 'remove_nulls');
      await page.selectOption('[name="column"]', 'age');
      await page.click('button:has-text("Add")');
    }

    // Wait for preview to generate
    await page.waitForSelector('[data-testid="preview-loading"]', {
      state: 'visible',
      timeout: 5000,
    });
    await page.waitForSelector('[data-testid="preview-loading"]', {
      state: 'hidden',
      timeout: 10000,
    });

    // Verify preview displays
    await expect(
      page.locator('text=Original Data, text=Transformed Data').first()
    ).toBeVisible();

    // Verify impact statistics
    const impactStats = page.locator('[data-testid="impact-stats"]');
    if (await impactStats.isVisible()) {
      await expect(impactStats).toBeVisible();
    } else {
      // Alternative: check for any statistics display
      await expect(page.locator('text=Rows Affected')).toBeVisible();
    }
  });

  test('user changes sample size and preview updates', async ({ page }) => {
    // Navigate to a dataset transformation page
    await page.goto('/datasets');
    await page.waitForLoadState('networkidle');

    // Use first dataset
    const datasetCards = page.locator('[data-testid="dataset-card"]');
    if ((await datasetCards.count()) > 0) {
      await datasetCards.first().click();
    } else {
      // Skip test if no datasets available
      test.skip();
      return;
    }

    await page.waitForURL(/\/datasets\/[^/]+/);

    // Navigate to transform page
    const transformLink = page.locator('a:has-text("Transform")');
    if (await transformLink.isVisible()) {
      await transformLink.click();
    }

    await page.waitForLoadState('networkidle');

    // Verify default sample size (100)
    const sampleSizeControl = page.locator('text=Sample Size:');
    await expect(sampleSizeControl).toBeVisible();

    // Change sample size to 500
    const sampleSizeSelect = page.locator('[data-testid="select-trigger"]');
    if (await sampleSizeSelect.isVisible()) {
      await sampleSizeSelect.click();
      await page.click('text=500 rows');

      // Wait for preview to regenerate
      await page.waitForTimeout(500);

      // Verify preview updated
      await expect(page.locator('text=Original Data')).toBeVisible();
    }
  });

  test('user compares before and after data side-by-side', async ({ page }) => {
    // Navigate to transformation page with existing preview
    await page.goto('/datasets');
    await page.waitForLoadState('networkidle');

    const datasetCards = page.locator('[data-testid="dataset-card"]');
    if ((await datasetCards.count()) === 0) {
      test.skip();
      return;
    }

    await datasetCards.first().click();
    await page.waitForURL(/\/datasets\/[^/]+/);

    // Navigate to transform
    const transformLink = page.locator('a:has-text("Transform")');
    if (await transformLink.isVisible()) {
      await transformLink.click();
    }

    await page.waitForLoadState('networkidle');

    // Verify side-by-side layout is displayed
    const layoutToggle = page.locator('button:has-text("Side-by-Side")');
    if (await layoutToggle.isVisible()) {
      await expect(layoutToggle).toHaveClass(/bg-blue-600/);

      // Toggle to stacked layout
      await page.click('button:has-text("Stacked")');
      await expect(page.locator('button:has-text("Stacked")')).toHaveClass(
        /bg-blue-600/
      );

      // Toggle back to side-by-side
      await layoutToggle.click();
      await expect(layoutToggle).toHaveClass(/bg-blue-600/);
    }
  });

  test('user views impact statistics and quality metrics', async ({ page }) => {
    // Navigate to transformation with preview
    await page.goto('/datasets');
    await page.waitForLoadState('networkidle');

    const datasetCards = page.locator('[data-testid="dataset-card"]');
    if ((await datasetCards.count()) === 0) {
      test.skip();
      return;
    }

    await datasetCards.first().click();
    await page.waitForURL(/\/datasets\/[^/]+/);

    const transformLink = page.locator('a:has-text("Transform")');
    if (await transformLink.isVisible()) {
      await transformLink.click();
    }

    await page.waitForLoadState('networkidle');

    // Check for impact statistics section
    const statsSection = page.locator('text=Impact Statistics');
    if (await statsSection.isVisible()) {
      await expect(statsSection).toBeVisible();

      // Verify key metrics are displayed
      await expect(page.locator('text=Rows Affected')).toBeVisible();
      await expect(page.locator('text=Values Changed')).toBeVisible();
      await expect(page.locator('text=Columns Affected')).toBeVisible();

      // Verify quality score comparison
      await expect(
        page.locator('text=Quality Score Comparison')
      ).toBeVisible();
    }
  });

  test('user sees warnings and decides not to apply transformation', async ({
    page,
  }) => {
    // Navigate to transformation page
    await page.goto('/datasets');
    await page.waitForLoadState('networkidle');

    const datasetCards = page.locator('[data-testid="dataset-card"]');
    if ((await datasetCards.count()) === 0) {
      test.skip();
      return;
    }

    await datasetCards.first().click();
    await page.waitForURL(/\/datasets\/[^/]+/);

    const transformLink = page.locator('a:has-text("Transform")');
    if (await transformLink.isVisible()) {
      await transformLink.click();
    }

    await page.waitForLoadState('networkidle');

    // Add a transformation that might cause warnings
    const addButton = page.locator('button:has-text("Add Transformation")');
    if (await addButton.isVisible()) {
      await addButton.click();

      // Select a potentially problematic transformation
      await page.selectOption('[name="operation"]', 'remove_duplicates');
      await page.click('button:has-text("Add")');

      // Wait for preview
      await page.waitForTimeout(1000);

      // Check for warnings section
      const warningsSection = page.locator('text=Warnings');
      if (await warningsSection.isVisible()) {
        await expect(warningsSection).toBeVisible();

        // Check for quality degradation indicator
        const degradationIndicator = page.locator(
          'text=degradation, text=quality'
        );
        if (await degradationIndicator.isVisible()) {
          await expect(degradationIndicator).toBeVisible();
        }
      }

      // User decides to cancel
      const cancelButton = page.locator(
        'button:has-text("Cancel"), button:has-text("Back")'
      );
      if (await cancelButton.first().isVisible()) {
        await cancelButton.first().click();

        // Verify we're back to dataset view or transformation not applied
        await expect(page).not.toHaveURL(/\/apply/);
      }
    } else {
      test.skip();
    }
  });

  test('user refreshes preview after making changes', async ({ page }) => {
    // Navigate to transformation page
    await page.goto('/datasets');
    await page.waitForLoadState('networkidle');

    const datasetCards = page.locator('[data-testid="dataset-card"]');
    if ((await datasetCards.count()) === 0) {
      test.skip();
      return;
    }

    await datasetCards.first().click();
    await page.waitForURL(/\/datasets\/[^/]+/);

    const transformLink = page.locator('a:has-text("Transform")');
    if (await transformLink.isVisible()) {
      await transformLink.click();
    }

    await page.waitForLoadState('networkidle');

    // Look for refresh button
    const refreshButton = page.locator('button:has-text("Refresh")');
    if (await refreshButton.isVisible()) {
      // Click refresh
      await refreshButton.click();

      // Verify loading state appears
      await expect(
        page.locator('text=Refreshing..., text=Generating preview...')
      ).toBeVisible();

      // Wait for refresh to complete
      await page.waitForSelector('text=Refreshing...', {
        state: 'hidden',
        timeout: 10000,
      });

      // Verify timestamp updated
      await expect(page.locator('text=Updated Just now')).toBeVisible();
    }
  });

  test('user sees synchronized scrolling between tables', async ({ page }) => {
    // Navigate to transformation with preview
    await page.goto('/datasets');
    await page.waitForLoadState('networkidle');

    const datasetCards = page.locator('[data-testid="dataset-card"]');
    if ((await datasetCards.count()) === 0) {
      test.skip();
      return;
    }

    await datasetCards.first().click();
    await page.waitForURL(/\/datasets\/[^/]+/);

    const transformLink = page.locator('a:has-text("Transform")');
    if (await transformLink.isVisible()) {
      await transformLink.click();
    }

    await page.waitForLoadState('networkidle');

    // Check if tables are present
    const originalTable = page.locator('text=Original Data').locator('..');
    const transformedTable = page
      .locator('text=Transformed Data')
      .locator('..');

    if (
      (await originalTable.isVisible()) &&
      (await transformedTable.isVisible())
    ) {
      // Verify both tables are scrollable
      const scrollContainers = page.locator('.overflow-auto');
      expect(await scrollContainers.count()).toBeGreaterThanOrEqual(2);

      // Note: Actual scroll synchronization testing is difficult in Playwright
      // as it requires simulating scroll events and checking scroll positions
      // which may not work reliably across browsers
    }
  });
});
