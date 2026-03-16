import { Page } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Versioning Page Object
 * Handles dataset version management interactions
 */
export class VersioningPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to dataset versions page
   * Note: /datasets/{id}/versions does not exist as a route.
   * Falls back to /explore/{id} which shows dataset detail and may have versioning controls.
   */
  async gotoVersions(datasetId: string) {
    await this.goto(`/explore/${datasetId}`);
  }

  /**
   * Create a new version of the dataset
   */
  async createVersion(versionName: string, description?: string) {
    // Click create version button
    await this.click('button:has-text("Create Version"), [data-testid="create-version"]');

    // Fill version details
    await this.fill('input[name="version-name"], [data-testid="version-name"]', versionName);

    if (description) {
      await this.fill('textarea[name="description"], [data-testid="version-description"]', description);
    }

    // Submit
    await this.click('button:has-text("Create"), button[type="submit"], [data-testid="submit-version"]');

    // Wait for creation to complete
    await this.waitForElement('text=/Version created|Success/i', 10000);
  }

  /**
   * Get version count from the version list
   */
  async getVersionCount(): Promise<number> {
    const versions = this.page.locator('[data-testid="version-item"], .version-card, [data-version-id]');
    return await versions.count();
  }

  /**
   * View version history
   */
  async viewVersionHistory() {
    await this.click('button:has-text("Version History"), [data-testid="version-history"]');
    await this.waitForElement('[data-testid="history-list"], .version-history');
  }

  /**
   * Select a version for comparison
   */
  async selectVersionForComparison(versionId: string, position: 'first' | 'second' = 'first') {
    const selector = position === 'first'
      ? '[data-testid="compare-version-1"], [data-testid="version-select-1"]'
      : '[data-testid="compare-version-2"], [data-testid="version-select-2"]';

    await this.page.click(selector);
    await this.page.click(`[data-version-id="${versionId}"], option[value="${versionId}"]`);
  }

  /**
   * Compare two versions
   */
  async compareVersions(version1Id: string, version2Id: string) {
    await this.selectVersionForComparison(version1Id, 'first');
    await this.selectVersionForComparison(version2Id, 'second');

    // Click compare button
    await this.click('button:has-text("Compare"), [data-testid="compare-versions"]');

    // Wait for comparison results
    await this.waitForElement('[data-testid="comparison-result"], .comparison-view', 30000);
  }

  /**
   * View transformation lineage
   */
  async viewLineage(versionId?: string) {
    if (versionId) {
      await this.page.click(`[data-version-id="${versionId}"] button:has-text("Lineage"), [data-testid="lineage-${versionId}"]`);
    } else {
      await this.click('button:has-text("View Lineage"), [data-testid="view-lineage"]');
    }

    // Wait for lineage graph to load
    await this.waitForElement('[data-testid="lineage-graph"], .lineage-visualization, svg[data-lineage]', 15000);
  }

  /**
   * Restore a previous version
   */
  async restoreVersion(versionId: string) {
    // Find the version and click restore
    await this.page.click(`[data-version-id="${versionId}"] button:has-text("Restore"), [data-testid="restore-${versionId}"]`);

    // Confirm restoration
    await this.click('button:has-text("Confirm"), [data-testid="confirm-restore"]');

    // Wait for restoration to complete
    await this.waitForElement('text=/Restored|Version restored successfully/i', 10000);
  }

  /**
   * Branch from a version (create alternative version chain)
   */
  async branchFromVersion(versionId: string, branchName: string) {
    // Click branch button for specific version
    await this.page.click(`[data-version-id="${versionId}"] button:has-text("Branch"), [data-testid="branch-${versionId}"]`);

    // Fill branch details
    await this.fill('input[name="branch-name"], [data-testid="branch-name"]', branchName);

    // Create branch
    await this.click('button:has-text("Create Branch"), [data-testid="create-branch"]');

    // Wait for branch creation
    await this.waitForElement('text=/Branch created|Success/i', 10000);
  }

  /**
   * Delete a version
   */
  async deleteVersion(versionId: string) {
    // Click delete button
    await this.page.click(`[data-version-id="${versionId}"] button:has-text("Delete"), [data-testid="delete-${versionId}"]`);

    // Confirm deletion
    await this.click('button:has-text("Confirm"), [data-testid="confirm-delete"]');
  }

  /**
   * Check if version deletion warning is displayed
   */
  async hasVersionInUseWarning(): Promise<boolean> {
    return await this.isVisible('text=/in use|cannot delete|version is active/i');
  }

  /**
   * Get schema differences from comparison view
   */
  async getSchemaDiff(): Promise<{ added: string[]; removed: string[]; modified: string[] }> {
    const added: string[] = [];
    const removed: string[] = [];
    const modified: string[] = [];

    // Look for schema diff sections
    const addedColumns = this.page.locator('[data-diff="added"], .schema-added, [data-change="added"]');
    const removedColumns = this.page.locator('[data-diff="removed"], .schema-removed, [data-change="removed"]');
    const modifiedColumns = this.page.locator('[data-diff="modified"], .schema-modified, [data-change="modified"]');

    // Extract text content
    const addedCount = await addedColumns.count();
    for (let i = 0; i < addedCount; i++) {
      const text = await addedColumns.nth(i).textContent();
      if (text) added.push(text.trim());
    }

    const removedCount = await removedColumns.count();
    for (let i = 0; i < removedCount; i++) {
      const text = await removedColumns.nth(i).textContent();
      if (text) removed.push(text.trim());
    }

    const modifiedCount = await modifiedColumns.count();
    for (let i = 0; i < modifiedCount; i++) {
      const text = await modifiedColumns.nth(i).textContent();
      if (text) modified.push(text.trim());
    }

    return { added, removed, modified };
  }

  /**
   * Get row count delta from comparison view
   */
  async getRowCountDelta(): Promise<{ before: number; after: number; delta: number }> {
    const deltaText = await this.getText('[data-testid="row-count-delta"], .row-delta');

    // Parse delta text (e.g., "1000 → 950 (-50)")
    const match = deltaText.match(/(\d+)\s*→\s*(\d+)\s*\(([+-]?\d+)\)/);

    if (match) {
      return {
        before: parseInt(match[1]),
        after: parseInt(match[2]),
        delta: parseInt(match[3])
      };
    }

    return { before: 0, after: 0, delta: 0 };
  }

  /**
   * Check if lineage graph displays correctly
   */
  async verifyLineageGraph(expectedVersionCount: number): Promise<boolean> {
    // Check for lineage nodes
    const nodes = this.page.locator('[data-testid="lineage-node"], .lineage-node, circle[data-version]');
    const nodeCount = await nodes.count();

    return nodeCount >= expectedVersionCount;
  }

  /**
   * Get version details
   */
  async getVersionDetails(versionId: string): Promise<{
    name: string;
    createdAt: string;
    parentId: string | null;
  }> {
    const versionElement = this.page.locator(`[data-version-id="${versionId}"]`);

    const name = await versionElement.locator('[data-field="name"], .version-name').textContent() || '';
    const createdAt = await versionElement.locator('[data-field="created"], .version-date').textContent() || '';
    const parentElement = versionElement.locator('[data-field="parent"], [data-parent-id]');

    let parentId: string | null = null;
    if (await parentElement.count() > 0) {
      parentId = await parentElement.getAttribute('data-parent-id');
    }

    return {
      name: name.trim(),
      createdAt: createdAt.trim(),
      parentId
    };
  }

  /**
   * Navigate to specific page in version history (for pagination testing)
   */
  async goToVersionPage(pageNumber: number) {
    const pageButton = this.page.locator(`button:has-text("${pageNumber}"), [data-page="${pageNumber}"]`);

    if (await pageButton.isVisible({ timeout: 5000 })) {
      await pageButton.click();
      await this.page.waitForTimeout(1000); // Wait for page to load
    } else {
      // Try next/previous navigation
      for (let i = 1; i < pageNumber; i++) {
        await this.click('button:has-text("Next"), [data-testid="next-page"]');
        await this.page.waitForTimeout(500);
      }
    }
  }

  /**
   * Check for comparison error
   */
  async hasComparisonError(): Promise<boolean> {
    return await this.isVisible('text=/cannot compare|incompatible|comparison failed/i');
  }
}
