import { Page } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Dataset Page Object
 * Handles dataset metadata view and management interactions
 */
export class DatasetPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to dataset list page
   */
  async gotoDatasetList() {
    await this.goto('/datasets');
  }

  /**
   * Navigate to specific dataset detail page
   */
  async gotoDatasetDetail(datasetId: string) {
    await this.goto(`/datasets/${datasetId}`);
  }

  /**
   * Get dataset metadata from the page
   */
  async getDatasetMetadata() {
    const filename = await this.getText('[data-testid="dataset-filename"], .dataset-filename');
    const rowCount = await this.getText('[data-testid="row-count"], .row-count');
    const columnCount = await this.getText('[data-testid="column-count"], .column-count');

    return { filename, rowCount, columnCount };
  }

  /**
   * Update dataset description
   */
  async updateDescription(description: string) {
    // Click edit button
    await this.click('button:has-text("Edit"), [data-testid="edit-description"]');

    // Fill description
    await this.fill('textarea[name="description"], [data-testid="description-input"]', description);

    // Save changes
    await this.click('button:has-text("Save"), [data-testid="save-description"]');

    // Wait for save confirmation
    await this.waitForElement('text=/Saved|Updated|Success/i', 5000);
  }

  /**
   * Add tags to dataset
   */
  async addTag(tag: string) {
    // Click add tag button or input
    const tagInput = this.locator('input[name="tag"], [data-testid="tag-input"]');
    await tagInput.fill(tag);
    await tagInput.press('Enter');

    // Wait for tag to appear
    await this.waitForElement(`text=${tag}`, 5000);
  }

  /**
   * Remove tag from dataset
   */
  async removeTag(tag: string) {
    const tagElement = this.locator(`[data-tag="${tag}"] button, button[aria-label*="Remove ${tag}"]`);
    await tagElement.click();
  }

  /**
   * Delete dataset with confirmation
   */
  async deleteDataset() {
    // Click delete button
    await this.click('button:has-text("Delete"), [data-testid="delete-dataset"]');

    // Wait for confirmation dialog
    await this.waitForElement('text=/Are you sure|Confirm delete/i', 5000);

    // Confirm deletion
    await this.click('button:has-text("Confirm"), button:has-text("Delete"), [data-testid="confirm-delete"]');

    // Wait for deletion to complete
    await this.waitForElement('text=/Deleted|Removed/i', 10000);
  }

  /**
   * Filter datasets by search term
   */
  async filterDatasets(searchTerm: string) {
    const searchInput = this.locator('input[type="search"], input[placeholder*="Search"], [data-testid="dataset-search"]');
    await searchInput.fill(searchTerm);

    // Wait for filtering to complete
    await this.page.waitForTimeout(500);
  }

  /**
   * Get number of visible datasets in list
   */
  async getDatasetCount(): Promise<number> {
    const datasets = this.locator('[data-testid="dataset-item"], .dataset-card, tr[data-dataset-id]');
    return await datasets.count();
  }

  /**
   * Check if schema is displayed
   */
  async isSchemaVisible(): Promise<boolean> {
    return await this.isVisible('[data-testid="dataset-schema"], .schema-table, text=/Schema|Columns/i');
  }

  /**
   * Get schema column names
   */
  async getSchemaColumns(): Promise<string[]> {
    const columnElements = this.locator('[data-testid="column-name"], .column-name, [data-column]');
    const count = await columnElements.count();

    const columns: string[] = [];
    for (let i = 0; i < count; i++) {
      const text = await columnElements.nth(i).textContent();
      if (text) columns.push(text.trim());
    }

    return columns;
  }

  /**
   * Check if missing values warning is displayed
   */
  async hasMissingValuesWarning(): Promise<boolean> {
    return await this.isVisible('text=/missing values|incomplete data/i');
  }

  /**
   * Wait for schema inference to complete
   */
  async waitForSchemaInference(timeout: number = 30000) {
    await this.waitForElement('[data-testid="schema-complete"], text=/Schema inferred|Inference complete/i', timeout);
  }

  /**
   * Get file size from metadata
   */
  async getFileSize(): Promise<string> {
    return await this.getText('[data-testid="file-size"], .file-size');
  }

  /**
   * Check if S3 URL is displayed
   */
  async hasS3Url(): Promise<boolean> {
    return await this.isVisible('[data-testid="s3-url"], text=/s3:\\/\\//i');
  }

  /**
   * Download dataset
   */
  async downloadDataset() {
    const downloadButton = this.locator('button:has-text("Download"), [data-testid="download-dataset"], a[download]');
    await downloadButton.click();
  }

  /**
   * Navigate to dataset transformation page
   */
  async gotoTransform(datasetId: string) {
    await this.goto(`/datasets/${datasetId}/transform`);
  }

  /**
   * Navigate to dataset training page
   */
  async gotoTrain(datasetId: string) {
    await this.goto(`/datasets/${datasetId}/train`);
  }
}
