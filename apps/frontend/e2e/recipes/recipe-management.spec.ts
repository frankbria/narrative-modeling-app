/**
 * Recipe Management E2E Tests
 *
 * The `/recipes` library on the real stack: tabs, search, sort, view mode, tag filter,
 * and the per-recipe actions (apply, duplicate, share, export, delete). Each test seeds
 * its own recipes through the API and removes them, and any copy made of them, after.
 * (`/recipes` has no inbound navigation yet; #738 decides whether it stays.)
 */

import { test, expect } from '../fixtures';
import type { APIRequestContext, Page } from '@playwright/test';
import { API_BASE, apiAuthHeaders } from '../helpers/apiAuth';

interface Seeded {
  id: string;
  name: string;
}

const prefix = () => `E2E recipe ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

async function createRecipe(
  request: APIRequestContext,
  name: string,
  tags: string[] = []
): Promise<Seeded> {
  const response = await request.post(`${API_BASE}/transformations/recipes`, {
    headers: await apiAuthHeaders(request),
    data: {
      name,
      description: 'Removes duplicate rows',
      steps: [{ type: 'remove_duplicates' }],
      tags,
    },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return { id: (await response.json()).id, name };
}

/** Delete every recipe of the user whose name starts with `namePrefix` (copies included). */
async function deleteRecipes(request: APIRequestContext, namePrefix: string) {
  const headers = await apiAuthHeaders(request);
  const response = await request.get(
    `${API_BASE}/transformations/recipes?include_public=false&per_page=100`,
    { headers }
  );
  const { recipes } = (await response.json()) as { recipes: Seeded[] };
  for (const recipe of recipes.filter((r) => r.name.startsWith(namePrefix))) {
    await request.delete(`${API_BASE}/transformations/recipes/${recipe.id}`, { headers });
  }
}

/** The card of the recipe with this name: the smallest block holding its title and its menu. */
const card = (page: Page, name: string) =>
  page
    .locator('div')
    .filter({ has: page.getByText(name, { exact: true }) })
    .filter({ has: page.getByRole('button', { name: 'Apply Recipe' }) })
    .last();

async function openActions(page: Page, name: string) {
  await card(page, name).getByRole('button', { name: 'Recipe actions' }).click();
  await expect(page.getByRole('menu')).toBeVisible();
}

test.describe('Recipe Management', () => {
  let namePrefix = '';
  let recipe: Seeded;

  test.beforeEach(async ({ authenticatedPage, request }) => {
    namePrefix = prefix();
    recipe = await createRecipe(request, namePrefix, [`e2e-${namePrefix.slice(-5)}`]);
    await authenticatedPage.goto('/recipes');
    await expect(authenticatedPage.locator('h1:has-text("Recipe Library")')).toBeVisible({ timeout: 10000 });
  });

  test.afterEach(async ({ request }) => {
    await deleteRecipes(request, namePrefix);
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

      // Verify view mode toggle buttons by their accessible names (a page-global
      // `button:has(svg)` locator would collide with the sidebar hamburger #282).
      await expect(authenticatedPage.getByRole('button', { name: 'Grid view' })).toBeVisible();
      await expect(authenticatedPage.getByRole('button', { name: 'List view' })).toBeVisible();
    });

    test('should filter recipes by search query', async ({ authenticatedPage: page }) => {
      const search = page.locator('input[placeholder*="Search recipes"]');
      await expect(page.getByText(recipe.name, { exact: true })).toBeVisible();

      await search.fill('no recipe is called this');
      await expect(page.getByText('No recipes found')).toBeVisible();
      await expect(page.getByText(recipe.name, { exact: true })).toBeHidden();

      await search.fill(recipe.name);
      await expect(page.getByText(recipe.name, { exact: true })).toBeVisible();
    });

    test('should toggle view mode between grid and list', async ({ authenticatedPage: page }) => {
      const grid = page.getByRole('button', { name: 'Grid view' });
      const list = page.getByRole('button', { name: 'List view' });
      await expect(grid).toHaveAttribute('aria-pressed', 'true');

      await list.click();
      await expect(list).toHaveAttribute('aria-pressed', 'true');
      await expect(grid).toHaveAttribute('aria-pressed', 'false');

      await grid.click();
      await expect(grid).toHaveAttribute('aria-pressed', 'true');
    });

    test('should sort recipes by different criteria', async ({ authenticatedPage: page }) => {
      const sort = page.locator('button[role="combobox"]').first();
      for (const option of ['Most Popular', 'Name (A-Z)', 'Most Recent']) {
        await sort.click();
        await page.getByRole('option', { name: option }).click();
        await expect(sort).toHaveText(option);
      }
    });

    test('should filter by tags', async ({ authenticatedPage: page, request }) => {
      const untagged = await createRecipe(request, `${namePrefix} untagged`);
      await page.reload();
      await expect(page.getByText(untagged.name, { exact: true })).toBeVisible();

      await page.getByText(`e2e-${namePrefix.slice(-5)}`, { exact: true }).first().click();
      await expect(page.getByText(recipe.name, { exact: true })).toBeVisible();
      await expect(page.getByText(untagged.name, { exact: true })).toBeHidden();
    });
  });

  test.describe('Recipe Card Interactions', () => {
    test('should display recipe cards with information', async ({ authenticatedPage: page }) => {
      const seeded = card(page, recipe.name);
      await expect(seeded).toContainText('Removes duplicate rows');
      await expect(seeded).toContainText(`e2e-${namePrefix.slice(-5)}`);
    });

    test('should open recipe action menu', async ({ authenticatedPage: page }) => {
      await openActions(page, recipe.name);
      for (const item of ['Apply Recipe', 'Duplicate', 'Share', 'Export JSON', 'Delete']) {
        await expect(page.getByRole('menuitem', { name: item })).toBeVisible();
      }
      await page.keyboard.press('Escape');
      await expect(page.getByRole('menu')).toBeHidden();
    });

    test('should apply recipe when Apply button is clicked', async ({ authenticatedPage: page }) => {
      await card(page, recipe.name).getByRole('button', { name: 'Apply Recipe' }).click();
      await expect(page).toHaveURL(new RegExp(`/transform\\?recipeId=${recipe.id}`));
    });
  });

  test.describe('Recipe Duplication', () => {
    test('should duplicate a recipe', async ({ authenticatedPage: page }) => {
      await openActions(page, recipe.name);
      await page.getByRole('menuitem', { name: 'Duplicate' }).click();
      await expect(page.getByText(`${recipe.name} (Copy)`, { exact: true })).toBeVisible();
    });
  });

  test.describe('Recipe Sharing', () => {
    test('should open share dialog for owned recipes', async ({ authenticatedPage: page }) => {
      await page.getByRole('tab', { name: 'My Recipes' }).click();
      await openActions(page, recipe.name);
      await page.getByRole('menuitem', { name: 'Share' }).click();

      const dialog = page.getByRole('dialog');
      await expect(dialog.getByRole('heading', { name: 'Share Recipe' })).toBeVisible();
      await dialog.getByRole('button', { name: 'Cancel' }).click();
      await expect(dialog).toBeHidden();
    });

    test('should validate user ID in share dialog', async ({ authenticatedPage: page }) => {
      await page.getByRole('tab', { name: 'My Recipes' }).click();
      await openActions(page, recipe.name);
      await page.getByRole('menuitem', { name: 'Share' }).click();

      const dialog = page.getByRole('dialog');
      const share = dialog.getByRole('button', { name: 'Share Recipe' });
      await expect(share).toBeDisabled();
      await dialog.locator('input[id="userId"]').fill('test-user-123');
      await expect(share).toBeEnabled();
      await dialog.getByRole('button', { name: 'Cancel' }).click();
    });
  });

  test.describe('Recipe Export', () => {
    async function openExport(page: Page, name: string) {
      await openActions(page, name);
      await page.getByRole('menuitem', { name: 'Export JSON' }).click();
      const dialog = page.getByRole('dialog');
      await expect(dialog.getByRole('heading', { name: 'Export Recipe' })).toBeVisible();
      return dialog;
    }

    test('should open export dialog', async ({ authenticatedPage: page }) => {
      const dialog = await openExport(page, recipe.name);
      await dialog.getByRole('button', { name: 'Close' }).first().click();
      await expect(dialog).toBeHidden();
    });

    test('should switch between preview and formatted tabs in export dialog', async ({ authenticatedPage: page }) => {
      const dialog = await openExport(page, recipe.name);
      const preview = dialog.getByRole('tab', { name: 'Preview' });
      const formatted = dialog.getByRole('tab', { name: 'Formatted' });
      await expect(preview).toHaveAttribute('data-state', 'active');

      await formatted.click();
      await expect(formatted).toHaveAttribute('data-state', 'active');
      await expect(dialog.getByText(/Recipe Format/)).toBeVisible();
    });

    test('should enable copy and download buttons after data loads', async ({ authenticatedPage: page }) => {
      const dialog = await openExport(page, recipe.name);
      await expect(dialog.getByRole('button', { name: 'Copy JSON' })).toBeEnabled();
      await expect(dialog.getByRole('button', { name: 'Download' })).toBeEnabled();
    });
  });

  test.describe('Recipe Deletion', () => {
    test('should delete an owned recipe after confirming', async ({ authenticatedPage: page }) => {
      await page.getByRole('tab', { name: 'My Recipes' }).click();
      await openActions(page, recipe.name);
      page.once('dialog', (dialog) => dialog.accept());
      await page.getByRole('menuitem', { name: 'Delete' }).click();
      await expect(page.getByText(recipe.name, { exact: true })).toBeHidden();
    });
  });

  test.describe('Empty States', () => {
    test('should display empty state in Shared with Me tab', async ({ authenticatedPage: page }) => {
      // Nothing ever shares a recipe with the shared e2e user.
      await page.getByRole('tab', { name: 'Shared with Me' }).click();
      await expect(page.getByText('No shared recipes')).toBeVisible();
      await expect(page.getByText(/When someone shares a recipe with you/)).toBeVisible();
    });
  });

  test.describe('Error Handling', () => {
    test('should show an error when the list cannot load', async ({ authenticatedPage: page }) => {
      // The UI's reaction to a failed list request, so only that request is failed.
      await page.route(
        (url) => url.pathname.endsWith('/transformations/recipes'),
        (route) => route.abort('failed')
      );
      await page.reload();
      await expect(page.getByRole('alert').filter({ hasText: /Failed to fetch/ })).toBeVisible();
    });
  });

  test.describe('Accessibility', () => {
    test('should have proper ARIA labels and roles', async ({ authenticatedPage }) => {
      // Verify tab roles
      const tabs = authenticatedPage.locator('button[role="tab"]');
      await expect(tabs.first()).toBeVisible();

      // Verify proper heading hierarchy
      await expect(authenticatedPage.locator('h1:has-text("Recipe Library")')).toBeVisible();
    });
  });
});
