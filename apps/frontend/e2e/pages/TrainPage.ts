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
    // The model page has a <select> element for target column (no name attr)
    const select = this.page.locator('select').first();
    await select.selectOption({ label: column });
  }

  async selectAlgorithm(algorithm: string) {
    // Algorithms are rendered as buttons (e.g., "Random Forest", "XGBoost", "AutoML")
    const algoButton = this.page.locator(`button:has-text("${algorithm}")`);
    if (await algoButton.isVisible({ timeout: 3000 })) {
      await algoButton.click();
    } else {
      // Fallback to select-based approach if buttons not found
      const selector = 'select[name="algorithm"], [data-testid="algorithm-select"]';
      await this.page.click(selector);
      await this.page.click(`option:has-text("${algorithm}"), [data-algorithm="${algorithm}"]`);
    }
  }

  async setHyperparameter(name: string, value: string) {
    const input = this.page.locator(`input[name="${name}"], [data-param="${name}"]`);
    await input.fill(value);
  }

  async startTraining() {
    // The model page uses "Start Training" button text
    const startButton = this.page.locator('button:has-text("Start Training"), button:has-text("Train Model"), [data-testid="start-training"]');
    await startButton.click();
  }

  async waitForTrainingComplete(timeout: number = 120000) {
    // The model page shows "Training complete!" text at 100% progress
    await this.page.waitForSelector('text=/Training complete|Training successful|Training finished/i', { timeout });
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
