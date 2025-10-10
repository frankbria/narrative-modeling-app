/**
 * Predict Page Object
 *
 * Encapsulates interactions with the prediction page.
 * Supports single predictions and batch predictions.
 */

import { Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class PredictPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async fillFeatureValue(featureName: string, value: string) {
    const input = this.page.locator(`input[name="${featureName}"], [data-feature="${featureName}"]`);
    await input.fill(value);
  }

  async predict() {
    await this.page.click('button:has-text("Predict"), [data-testid="make-prediction"]');
  }

  async waitForPredictionResult(timeout: number = 10000) {
    await this.page.waitForSelector('[data-testid="prediction-result"], .prediction-output', { timeout });
  }

  async getPredictionValue(): Promise<string> {
    const resultElement = this.page.locator('[data-testid="prediction-value"], .prediction-value');
    return await resultElement.textContent() || '';
  }

  async getConfidenceScore(): Promise<number> {
    const confidenceElement = this.page.locator('[data-testid="confidence-score"], .confidence');
    const text = (await confidenceElement.textContent()) || '0';
    const match = text.match(/[\d.]+/);
    return match ? parseFloat(match[0]) : 0;
  }

  async navigateToBatchPrediction() {
    await this.page.click('a:has-text("Batch"), [data-testid="batch-prediction-link"]');
  }

  async uploadBatchFile(filePath: string) {
    const fileInput = this.page.locator('input[type="file"]');
    await fileInput.setInputFiles(filePath);
  }

  async startBatchPrediction() {
    await this.page.click('button:has-text("Start"), [data-testid="start-batch-prediction"]');
  }

  async waitForBatchComplete(timeout: number = 60000) {
    await this.page.waitForSelector('text=/Batch prediction complete|Complete/i', { timeout });
  }

  async downloadPredictions() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.page.click('button:has-text("Download"), [data-testid="download-predictions"]');
    return await downloadPromise;
  }

  async getBatchResultCount(): Promise<number> {
    const rows = this.page.locator('tbody tr, [data-testid="prediction-row"]');
    return await rows.count();
  }
}
