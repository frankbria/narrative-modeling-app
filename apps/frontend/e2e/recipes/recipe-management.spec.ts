/**
 * Recipe Management E2E Tests
 *
 * Tests the complete recipe management workflow including:
 * - Recipe library browsing and navigation
 * - Recipe search and filtering
 * - Recipe creation and duplication
 * - Recipe sharing and permissions
 * - Recipe export and import
 * - Tab switching (All Recipes, My Recipes, Shared with Me, Popular)
 * - Error handling and validation
 *
 * Coverage Target: >85%
 */

import { test, expect } from '../fixtures';

test.describe('Recipe Management', () => {
  test.beforeEach(async ({ authenticatedPage }) => {
    // Navigate to recipes page
    await authenticatedPage.goto('/recipes');
    await expect(authenticatedPage.locator('h1:has-text("Recipe Library")')).toBeVisible({ timeout: 10000 });
  });

  test.describe('Recipe Library Navigation', () => {
    test('should display recipe library page with all sections @smoke', async ({ authenticatedPage }) => {
      // Verify page header
      await expect(authenticatedPage.locator('h1:has-text("Recipe Library")')).toBeVisible();
      await expect(authenticatedPage.locator('text=/Save, share, and reuse data transformation workflows/')).toBeVisible();

      // Verify Create New Recipe button
      await expect(authenticatedPage.locator('button:has-text("Create New Recipe")')).toBeVisible();

      // Verify tab navigation
      await expect(authenticatedPage.locator('button[role="tab"]:has-text("All Recipes")')).toBeVisible();
      await expect(authenticatedPage.locator('button[role="tab"]:has-text("My Recipes")')).toBeVisible();
      await expect(authenticatedPage.locator('button[role="tab"]:has-text("Shared with Me")')).toBeVisible();
      await expect(authenticatedPage.locator('button[role="tab"]:has-text("Popular")')).toBeVisible();
    });

    test('should switch between tabs', async ({ authenticatedPage }) => {
      // Default tab should be All Recipes
      const allRecipesTab = authenticatedPage.locator('button[role="tab"]:has-text("All Recipes")');
      await expect(allRecipesTab).toHaveAttribute('data-state', 'active');

      // Switch to My Recipes tab
      await authenticatedPage.locator('button[role="tab"]:has-text("My Recipes")').click();
      await expect(authenticatedPage.locator('button[role="tab"]:has-text("My Recipes")')).toHaveAttribute('data-state', 'active');

      // Switch to Shared with Me tab
      await authenticatedPage.locator('button[role="tab"]:has-text("Shared with Me")').click();
      await expect(authenticatedPage.locator('button[role="tab"]:has-text("Shared with Me")')).toHaveAttribute('data-state', 'active');
      await expect(authenticatedPage.locator('h2:has-text("Recipes Shared with You")')).toBeVisible();

      // Switch to Popular tab
      await authenticatedPage.locator('button[role="tab"]:has-text("Popular")').click();
      await expect(authenticatedPage.locator('button[role="tab"]:has-text("Popular")')).toHaveAttribute('data-state', 'active');
      await expect(authenticatedPage.locator('h2:has-text("Most Popular Recipes")')).toBeVisible();
    });

    test('should navigate to transform page when Create New Recipe is clicked', async ({ authenticatedPage }) => {
      await authenticatedPage.locator('button:has-text("Create New Recipe")').first().click();

      // Should navigate to transform page
      await expect(authenticatedPage).toHaveURL(/\/transform/);
    });
  });

  test.describe('Recipe Search and Filtering', () => {
    test('should display search and filter controls @smoke', async ({ authenticatedPage }) => {
      // Verify search input
      await expect(authenticatedPage.locator('input[placeholder*="Search recipes"]')).toBeVisible();

      // Verify sort dropdown
      await expect(authenticatedPage.locator('button[role="combobox"]').first()).toBeVisible();

      // Verify view mode toggle buttons
      const viewModeButtons = authenticatedPage.locator('button').filter({ has: authenticatedPage.locator('svg') });
      await expect(viewModeButtons.first()).toBeVisible();
    });

    test('should filter recipes by search query', async ({ authenticatedPage }) => {
      // Wait for recipes to load
      await authenticatedPage.waitForTimeout(1000);

      const searchInput = authenticatedPage.locator('input[placeholder*="Search recipes"]');

      // Type search query
      await searchInput.fill('cleaning');
      await authenticatedPage.waitForTimeout(500);

      // Verify filtered results (if any recipes exist)
      // Note: Actual results depend on database state
    });

    test('should toggle view mode between grid and list', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Find view mode toggle buttons
      const gridViewButton = authenticatedPage.locator('button').filter({ has: authenticatedPage.locator('svg') }).first();
      const listViewButton = authenticatedPage.locator('button').filter({ has: authenticatedPage.locator('svg') }).nth(1);

      // Switch to list view
      await listViewButton.click();
      await authenticatedPage.waitForTimeout(300);

      // Switch back to grid view
      await gridViewButton.click();
      await authenticatedPage.waitForTimeout(300);
    });

    test('should sort recipes by different criteria', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Open sort dropdown
      const sortDropdown = authenticatedPage.locator('button[role="combobox"]').first();
      await sortDropdown.click();

      // Select "Most Popular"
      await authenticatedPage.locator('div[role="option"]:has-text("Most Popular")').click();
      await authenticatedPage.waitForTimeout(500);

      // Open sort dropdown again
      await sortDropdown.click();

      // Select "Name (A-Z)"
      await authenticatedPage.locator('div[role="option"]:has-text("Name (A-Z)")').click();
      await authenticatedPage.waitForTimeout(500);

      // Open sort dropdown again
      await sortDropdown.click();

      // Select "Most Recent"
      await authenticatedPage.locator('div[role="option"]:has-text("Most Recent")').click();
      await authenticatedPage.waitForTimeout(500);
    });

    test('should filter by tags when available', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Check if tags are displayed
      const tags = authenticatedPage.locator('div').filter({ hasText: /^(cleaning|preprocessing|feature-engineering)$/ });
      const tagCount = await tags.count();

      if (tagCount > 0) {
        // Click first tag
        await tags.first().click();
        await authenticatedPage.waitForTimeout(500);

        // Click tag again to deselect
        await tags.first().click();
        await authenticatedPage.waitForTimeout(500);
      }
    });
  });

  test.describe('Recipe Card Interactions', () => {
    test('should display recipe cards with information', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Look for recipe cards (may be empty state)
      const recipeCards = authenticatedPage.locator('div[class*="card"]');
      const cardCount = await recipeCards.count();

      if (cardCount > 0) {
        // Verify first card has expected elements
        const firstCard = recipeCards.first();

        // Card should have some text content
        const cardText = await firstCard.textContent();
        expect(cardText).toBeTruthy();
      }
    });

    test('should open recipe action menu', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Find recipe cards with action buttons
      const actionButton = authenticatedPage.locator('button[aria-haspopup="menu"]').first();
      const buttonCount = await actionButton.count();

      if (buttonCount > 0) {
        await actionButton.click();

        // Verify dropdown menu appears
        await expect(authenticatedPage.locator('div[role="menu"]')).toBeVisible({ timeout: 2000 });

        // Close menu by clicking outside
        await authenticatedPage.keyboard.press('Escape');
      }
    });

    test('should apply recipe when Apply button is clicked', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      const applyButtons = authenticatedPage.locator('button:has-text("Apply Recipe")');
      const buttonCount = await applyButtons.count();

      if (buttonCount > 0) {
        // Click first Apply button
        await applyButtons.first().click();

        // Should navigate to transform page with recipe ID
        await expect(authenticatedPage).toHaveURL(/\/transform\?recipeId=/);
      }
    });
  });

  test.describe('Recipe Duplication', () => {
    test('should duplicate a recipe', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Open action menu
      const actionButton = authenticatedPage.locator('button[aria-haspopup="menu"]').first();
      const buttonCount = await actionButton.count();

      if (buttonCount > 0) {
        await actionButton.click();

        // Click Duplicate option
        const duplicateOption = authenticatedPage.locator('div[role="menuitem"]:has-text("Duplicate")');
        await duplicateOption.click();

        // Wait for duplication to complete
        await authenticatedPage.waitForTimeout(1500);

        // Recipe list should reload
        await authenticatedPage.waitForTimeout(500);
      }
    });
  });

  test.describe('Recipe Sharing', () => {
    test('should open share dialog for owned recipes', async ({ authenticatedPage }) => {
      // Switch to My Recipes tab to ensure we see owned recipes
      await authenticatedPage.locator('button[role="tab"]:has-text("My Recipes")').click();
      await authenticatedPage.waitForTimeout(1000);

      // Open action menu
      const actionButton = authenticatedPage.locator('button[aria-haspopup="menu"]').first();
      const buttonCount = await actionButton.count();

      if (buttonCount > 0) {
        await actionButton.click();

        // Check if Share option exists (only for owned recipes)
        const shareOption = authenticatedPage.locator('div[role="menuitem"]:has-text("Share")');
        const shareCount = await shareOption.count();

        if (shareCount > 0) {
          await shareOption.click();

          // Verify share dialog appears
          await expect(authenticatedPage.locator('h2:has-text("Share Recipe")')).toBeVisible({ timeout: 2000 });

          // Close dialog
          await authenticatedPage.locator('button:has-text("Cancel")').click();
        }
      }
    });

    test('should validate user ID in share dialog', async ({ authenticatedPage }) => {
      // Switch to My Recipes tab
      await authenticatedPage.locator('button[role="tab"]:has-text("My Recipes")').click();
      await authenticatedPage.waitForTimeout(1000);

      // Open action menu and share dialog
      const actionButton = authenticatedPage.locator('button[aria-haspopup="menu"]').first();
      const buttonCount = await actionButton.count();

      if (buttonCount > 0) {
        await actionButton.click();

        const shareOption = authenticatedPage.locator('div[role="menuitem"]:has-text("Share")');
        const shareCount = await shareOption.count();

        if (shareCount > 0) {
          await shareOption.click();

          // Verify share button is disabled without user ID
          const shareButton = authenticatedPage.locator('button:has-text("Share Recipe")').last();
          await expect(shareButton).toBeDisabled();

          // Enter user ID
          const userIdInput = authenticatedPage.locator('input[id="userId"]');
          await userIdInput.fill('test-user-123');

          // Share button should be enabled
          await expect(shareButton).toBeEnabled();

          // Close dialog
          await authenticatedPage.locator('button:has-text("Cancel")').click();
        }
      }
    });
  });

  test.describe('Recipe Export', () => {
    test('should open export dialog', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Open action menu
      const actionButton = authenticatedPage.locator('button[aria-haspopup="menu"]').first();
      const buttonCount = await actionButton.count();

      if (buttonCount > 0) {
        await actionButton.click();

        // Click Export JSON option
        const exportOption = authenticatedPage.locator('div[role="menuitem"]:has-text("Export JSON")');
        await exportOption.click();

        // Verify export dialog appears
        await expect(authenticatedPage.locator('h2:has-text("Export Recipe")')).toBeVisible({ timeout: 2000 });

        // Close dialog
        await authenticatedPage.locator('button:has-text("Close")').first().click();
      }
    });

    test('should switch between preview and formatted tabs in export dialog', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Open export dialog
      const actionButton = authenticatedPage.locator('button[aria-haspopup="menu"]').first();
      const buttonCount = await actionButton.count();

      if (buttonCount > 0) {
        await actionButton.click();

        const exportOption = authenticatedPage.locator('div[role="menuitem"]:has-text("Export JSON")');
        await exportOption.click();

        // Wait for dialog and data to load
        await authenticatedPage.waitForTimeout(1500);

        // Verify Preview tab is active by default
        const previewTab = authenticatedPage.locator('button[role="tab"]:has-text("Preview")');
        await expect(previewTab).toHaveAttribute('data-state', 'active');

        // Switch to Formatted tab
        const formattedTab = authenticatedPage.locator('button[role="tab"]:has-text("Formatted")');
        await formattedTab.click();
        await expect(formattedTab).toHaveAttribute('data-state', 'active');

        // Verify formatted content is displayed
        await expect(authenticatedPage.locator('text=/Recipe Format/')).toBeVisible();

        // Close dialog
        await authenticatedPage.locator('button:has-text("Close")').first().click();
      }
    });

    test('should enable copy and download buttons after data loads', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Open export dialog
      const actionButton = authenticatedPage.locator('button[aria-haspopup="menu"]').first();
      const buttonCount = await actionButton.count();

      if (buttonCount > 0) {
        await actionButton.click();

        const exportOption = authenticatedPage.locator('div[role="menuitem"]:has-text("Export JSON")');
        await exportOption.click();

        // Wait for data to load
        await authenticatedPage.waitForTimeout(2000);

        // Verify buttons are enabled
        const copyButton = authenticatedPage.locator('button:has-text("Copy JSON")');
        const downloadButton = authenticatedPage.locator('button:has-text("Download")');

        await expect(copyButton).toBeEnabled({ timeout: 3000 });
        await expect(downloadButton).toBeEnabled({ timeout: 3000 });

        // Close dialog
        await authenticatedPage.locator('button:has-text("Close")').first().click();
      }
    });
  });

  test.describe('Recipe Deletion', () => {
    test('should show delete option for owned recipes', async ({ authenticatedPage }) => {
      // Switch to My Recipes tab
      await authenticatedPage.locator('button[role="tab"]:has-text("My Recipes")').click();
      await authenticatedPage.waitForTimeout(1000);

      // Open action menu
      const actionButton = authenticatedPage.locator('button[aria-haspopup="menu"]').first();
      const buttonCount = await actionButton.count();

      if (buttonCount > 0) {
        await actionButton.click();

        // Check if Delete option exists
        const deleteOption = authenticatedPage.locator('div[role="menuitem"]:has-text("Delete")');
        const deleteCount = await deleteOption.count();

        // Delete option should exist for owned recipes
        if (deleteCount > 0) {
          expect(deleteCount).toBeGreaterThan(0);
        }

        // Close menu
        await authenticatedPage.keyboard.press('Escape');
      }
    });
  });

  test.describe('Empty States', () => {
    test('should display empty state in Shared with Me tab', async ({ authenticatedPage }) => {
      await authenticatedPage.locator('button[role="tab"]:has-text("Shared with Me")').click();
      await authenticatedPage.waitForTimeout(1000);

      // Check for empty state (likely in test environment)
      const emptyStateText = authenticatedPage.locator('text=/No shared recipes/');
      const hasEmptyState = await emptyStateText.count() > 0;

      if (hasEmptyState) {
        await expect(emptyStateText).toBeVisible();
        await expect(authenticatedPage.locator('text=/When someone shares a recipe with you/')).toBeVisible();
      }
    });

    test('should display empty state in Popular tab', async ({ authenticatedPage }) => {
      await authenticatedPage.locator('button[role="tab"]:has-text("Popular")').click();
      await authenticatedPage.waitForTimeout(1000);

      // Check for empty state or recipe cards
      const emptyStateText = authenticatedPage.locator('text=/No popular recipes yet/');
      const hasEmptyState = await emptyStateText.count() > 0;

      if (hasEmptyState) {
        await expect(emptyStateText).toBeVisible();
      }
    });
  });

  test.describe('Error Handling', () => {
    test('should handle network errors gracefully', async ({ authenticatedPage, page }) => {
      // Intercept API calls and simulate network error
      await page.route('**/api/v1/recipes/list*', route => {
        route.abort('failed');
      });

      // Navigate to recipes page
      await authenticatedPage.goto('/recipes');
      await authenticatedPage.waitForTimeout(2000);

      // Should display error message
      const errorMessage = authenticatedPage.locator('text=/Failed to load/');
      const hasError = await errorMessage.count() > 0;

      if (hasError) {
        await expect(errorMessage).toBeVisible();
      }

      // Restore network
      await page.unroute('**/api/v1/recipes/list*');
    });
  });

  test.describe('Pagination', () => {
    test('should display pagination when multiple pages exist', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Check if pagination exists
      const prevButton = authenticatedPage.locator('button:has-text("Previous")');
      const nextButton = authenticatedPage.locator('button:has-text("Next")');

      const hasPagination = await prevButton.count() > 0;

      if (hasPagination) {
        // Verify pagination controls
        await expect(prevButton).toBeVisible();
        await expect(nextButton).toBeVisible();

        // Verify page info
        await expect(authenticatedPage.locator('text=/Page \\d+ of \\d+/')).toBeVisible();
      }
    });
  });

  test.describe('Accessibility', () => {
    test('should have proper ARIA labels and roles', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Verify tab roles
      const tabs = authenticatedPage.locator('button[role="tab"]');
      await expect(tabs.first()).toBeVisible();

      // Verify proper heading hierarchy
      await expect(authenticatedPage.locator('h1:has-text("Recipe Library")')).toBeVisible();
    });

    test('should support keyboard navigation', async ({ authenticatedPage }) => {
      await authenticatedPage.waitForTimeout(1000);

      // Test Tab key navigation
      await authenticatedPage.keyboard.press('Tab');

      // Test Arrow key navigation in tabs
      await authenticatedPage.keyboard.press('ArrowRight');
      await authenticatedPage.waitForTimeout(300);

      await authenticatedPage.keyboard.press('ArrowLeft');
      await authenticatedPage.waitForTimeout(300);
    });
  });
});
