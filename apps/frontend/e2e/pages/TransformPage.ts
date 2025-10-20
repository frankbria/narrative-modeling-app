/**
 * Transform Page Object
 *
 * Encapsulates interactions with the data transformation page.
 * Supports various transformation types: encoding, scaling, imputation, feature engineering.
 */

import { Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class TransformPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async addTransformation(type: string) {
    // Click add transformation button
    await this.page.click('button:has-text("Add Transformation"), [data-testid="add-transformation"]');

    // Select transformation type
    await this.page.click(`[data-transform-type="${type}"], button:has-text("${type}")`);
  }

  async selectColumn(column: string) {
    // Select single column
    const selector = 'select[name="column"], [data-testid="column-select"]';
    await this.page.click(selector);
    await this.page.click(`option:has-text("${column}"), [data-column="${column}"]`);
  }

  async selectColumns(columns: string[]) {
    // Select multiple columns (checkbox-based selection)
    for (const column of columns) {
      const checkbox = this.page.locator(`input[type="checkbox"][value="${column}"], input[data-column="${column}"]`);
      if (await checkbox.isVisible()) {
        await checkbox.check();
      }
    }
  }

  async setEncoding(method: string) {
    const selector = 'select[name="encoding"], [data-testid="encoding-method"]';
    await this.page.click(selector);
    await this.page.click(`option:has-text("${method}"), [data-encoding="${method}"]`);
  }

  async setScaling(method: string) {
    const selector = 'select[name="scaling"], [data-testid="scaling-method"]';
    await this.page.click(selector);
    await this.page.click(`option:has-text("${method}"), [data-scaling="${method}"]`);
  }

  async setImputationStrategy(strategy: string) {
    const selector = 'select[name="imputation"], [data-testid="imputation-strategy"]';
    await this.page.click(selector);
    await this.page.click(`option:has-text("${strategy}"), [data-strategy="${strategy}"]`);
  }

  async previewTransformation() {
    await this.page.click('button:has-text("Preview"), [data-testid="preview-transformation"]');

    // Wait for preview to load
    await this.page.waitForSelector('[data-testid="preview-result"], .preview-table, text=/Preview/i', {
      timeout: 10000,
    });
  }

  async applyTransformation() {
    await this.page.click('button:has-text("Apply"), [data-testid="apply-transformation"]');

    // Wait for transformation to complete
    await this.page.waitForSelector('text=/Transformation applied|Success|Complete/i', {
      timeout: 30000,
    });
  }

  async removeTransformation(index: number = 0) {
    const removeButtons = this.page.locator('button:has-text("Remove"), [data-testid="remove-transformation"]');
    await removeButtons.nth(index).click();
  }

  async getTransformationCount(): Promise<number> {
    const transformations = this.page.locator('[data-testid="transformation-item"], .transformation-card');
    return await transformations.count();
  }

  async clearAllTransformations() {
    const clearButton = this.page.locator('button:has-text("Clear All"), [data-testid="clear-transformations"]');
    if (await clearButton.isVisible()) {
      await clearButton.click();
    }
  }

  async saveTransformationPipeline(name: string) {
    await this.page.click('button:has-text("Save Pipeline"), [data-testid="save-pipeline"]');
    await this.page.fill('input[name="pipeline-name"], [data-testid="pipeline-name"]', name);
    await this.page.click('button:has-text("Save"), [data-testid="confirm-save"]');
  }

  async loadTransformationPipeline(name: string) {
    await this.page.click('button:has-text("Load Pipeline"), [data-testid="load-pipeline"]');
    await this.page.click(`[data-pipeline="${name}"], button:has-text("${name}")`);
  }
}
