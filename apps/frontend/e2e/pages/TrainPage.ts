/**
 * Train Page Object
 *
 * Encapsulates interactions with the model training page.
 * Supports algorithm selection, hyperparameter tuning, and training monitoring.
 */

import { Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class TrainPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async selectTargetColumn(column: string) {
    const selector = 'select[name="target"], [data-testid="target-column"]';
    await this.page.click(selector);
    await this.page.click(`option:has-text("${column}"), [data-column="${column}"]`);
  }

  async selectAlgorithm(algorithm: string) {
    const selector = 'select[name="algorithm"], [data-testid="algorithm-select"]';
    await this.page.click(selector);
    await this.page.click(`option:has-text("${algorithm}"), [data-algorithm="${algorithm}"]`);
  }

  async setHyperparameter(name: string, value: string) {
    const input = this.page.locator(`input[name="${name}"], [data-param="${name}"]`);
    await input.fill(value);
  }

  async startTraining() {
    await this.page.click('button:has-text("Train Model"), [data-testid="start-training"]');
  }

  async waitForTrainingComplete(timeout: number = 120000) {
    await this.page.waitForSelector('text=/Training complete|Training successful/i', { timeout });
  }

  async waitForTrainingStatus(status: string, timeout: number = 30000) {
    await this.page.waitForSelector(`text=/${status}/i, [data-status="${status}"]`, { timeout });
  }

  async getTrainingProgress(): Promise<number> {
    const progressElement = this.page.locator('[data-testid="training-progress"], .progress-bar');
    if (await progressElement.isVisible({ timeout: 2000 })) {
      const value = await progressElement.getAttribute('value');
      return value ? parseInt(value) : 0;
    }
    return 0;
  }

  async cancelTraining() {
    await this.page.click('button:has-text("Cancel"), [data-testid="cancel-training"]');
  }

  async viewMetrics() {
    const metricsSection = this.page.locator('[data-testid="model-metrics"], .metrics-section');
    await metricsSection.scrollIntoViewIfNeeded();
  }

  async downloadModel() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.page.click('button:has-text("Download Model"), [data-testid="download-model"]');
    return await downloadPromise;
  }

  async getModelId(): Promise<string> {
    const url = this.page.url();
    const match = url.match(/\/models\/([^\/]+)/);
    return match ? match[1] : '';
  }
}
