/**
 * Evaluate Page Object
 *
 * Encapsulates interactions with the model evaluation dashboard (issue #79):
 * metric cards, tab navigation, confusion-matrix drill-down, model comparison
 * and CSV/PDF export buttons.
 */

import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';

export class EvaluatePage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async gotoEvaluate() {
    await this.goto('/evaluate');
  }

  /** True once the dashboard header (not the loading spinner) is visible. */
  async waitForDashboard(timeout: number = 30000) {
    await this.page.waitForSelector('text=/Model Evaluation/i', { timeout });
  }

  /** Whether the workflow gating redirected away from /evaluate. */
  wasRedirected(): boolean {
    const url = this.page.url();
    return url.includes('/upload') || url.includes('/model');
  }

  tab(name: string | RegExp): Locator {
    return this.page.getByRole('tab', { name });
  }

  async switchToTab(name: string | RegExp) {
    await this.tab(name).click();
  }

  /** Metric card value next to a label, e.g. metricValue('Accuracy'). */
  metricCard(label: string | RegExp): Locator {
    return this.page.locator('div', { hasText: label }).locator('.text-2xl');
  }

  async hasMetric(label: string | RegExp): Promise<boolean> {
    return this.isVisible(`text=${label}`);
  }

  /** Confusion-matrix cell by its accessible name. */
  confusionCell(actual: string, predicted: string): Locator {
    return this.page.getByRole('button', {
      name: new RegExp(`Actual ${actual}, predicted ${predicted}`, 'i'),
    });
  }

  async clickConfusionCell(actual: string, predicted: string) {
    await this.confusionCell(actual, predicted).click();
  }

  confusionCellDetail(): Locator {
    return this.page.getByTestId('confusion-cell-detail');
  }

  exportCSVButton(): Locator {
    return this.page.getByRole('button', { name: /export csv/i });
  }

  exportPDFButton(): Locator {
    return this.page.getByRole('button', { name: /export pdf/i });
  }

  async exportCSV() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.exportCSVButton().click();
    return downloadPromise;
  }

  /** Compare tab: toggle a model checkbox by visible name. */
  async selectCompareModel(name: string | RegExp) {
    await this.page.getByRole('checkbox', { name }).click();
  }

  compareButton(): Locator {
    return this.page.getByRole('button', { name: /^Compare$/ });
  }

  async runComparison() {
    await this.compareButton().click();
  }

  proceedButton(): Locator {
    return this.page.getByRole('button', { name: /proceed to prediction/i });
  }

  backToTrainingButton(): Locator {
    return this.page.getByRole('button', { name: /back to training/i });
  }
}
