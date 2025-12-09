import { Page } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Model Config Page Object
 * Handles model training configuration and management interactions
 */
export class ModelConfigPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to model training page for a dataset
   */
  async gotoTraining(datasetId: string) {
    await this.goto(`/datasets/${datasetId}/train`);
  }

  /**
   * Navigate to model list page
   */
  async gotoModelList() {
    await this.goto('/models');
  }

  /**
   * Navigate to model detail page
   */
  async gotoModelDetail(modelId: string) {
    await this.goto(`/models/${modelId}`);
  }

  /**
   * Select target column for training
   */
  async selectTargetColumn(column: string) {
    const selector = 'select[name="target"], [data-testid="target-column-select"]';
    await this.page.click(selector);
    await this.page.click(`option:has-text("${column}"), [data-column="${column}"]`);
  }

  /**
   * Select algorithm for training
   */
  async selectAlgorithm(algorithm: string) {
    const selector = 'select[name="algorithm"], [data-testid="algorithm-select"]';
    await this.page.click(selector);
    await this.page.click(`option:has-text("${algorithm}"), [data-algorithm="${algorithm}"]`);
  }

  /**
   * Set problem type (classification or regression)
   */
  async setProblemType(problemType: 'classification' | 'regression') {
    const selector = 'select[name="problem_type"], [data-testid="problem-type-select"]';
    await this.page.click(selector);
    await this.page.click(`option:has-text("${problemType}"), [data-problem-type="${problemType}"]`);
  }

  /**
   * Configure hyperparameters
   */
  async setHyperparameter(name: string, value: string | number) {
    const input = this.locator(`input[name="${name}"], [data-param="${name}"]`);
    await input.fill(String(value));
  }

  /**
   * Request AI algorithm recommendation
   */
  async requestAIRecommendation() {
    await this.click('button:has-text("Recommend"), button:has-text("AI Suggest"), [data-testid="ai-recommend-algorithm"]');

    // Wait for recommendations to load
    await this.waitForElement('text=/Recommended|Suggestions|AI recommends/i', 120000);
  }

  /**
   * Start model training
   */
  async startTraining() {
    await this.click('button:has-text("Train"), button:has-text("Start Training"), [data-testid="start-training"]');

    // Wait for training to start
    await this.waitForElement('text=/Training started|Training in progress/i', 5000);
  }

  /**
   * Wait for training to complete
   */
  async waitForTrainingComplete(timeout: number = 120000) {
    await this.waitForElement('text=/Training complete|Training finished|100%/i', timeout);
  }

  /**
   * Get training progress percentage
   */
  async getTrainingProgress(): Promise<number> {
    const progressElement = this.locator('[data-testid="training-progress"], [role="progressbar"]');

    if (await progressElement.isVisible({ timeout: 5000 })) {
      const ariaValue = await progressElement.getAttribute('aria-valuenow');
      if (ariaValue) {
        return parseInt(ariaValue);
      }

      // Try to extract from text
      const text = await progressElement.textContent();
      const match = text?.match(/(\d+)%/);
      if (match) {
        return parseInt(match[1]);
      }
    }

    return 0;
  }

  /**
   * Cancel training mid-process
   */
  async cancelTraining() {
    await this.click('button:has-text("Cancel"), [data-testid="cancel-training"]');

    // Wait for cancellation confirmation
    await this.waitForElement('text=/Training cancelled|Stopped/i', 5000);
  }

  /**
   * Get model metrics
   */
  async getMetrics() {
    const metrics: Record<string, number> = {};

    // Try to extract common metrics
    const metricNames = ['accuracy', 'precision', 'recall', 'f1', 'mse', 'rmse', 'r2'];

    for (const name of metricNames) {
      const metricElement = this.locator(`[data-metric="${name}"], [data-testid="metric-${name}"]`);

      if (await metricElement.isVisible({ timeout: 1000 }).catch(() => false)) {
        const text = await metricElement.textContent();
        const match = text?.match(/(\d+\.?\d*)/);
        if (match) {
          metrics[name] = parseFloat(match[1]);
        }
      }
    }

    return metrics;
  }

  /**
   * Check if confusion matrix is displayed
   */
  async hasConfusionMatrix(): Promise<boolean> {
    return await this.isVisible('[data-testid="confusion-matrix"], .confusion-matrix, text=/Confusion Matrix/i');
  }

  /**
   * Check if ROC curve is displayed
   */
  async hasROCCurve(): Promise<boolean> {
    return await this.isVisible('[data-testid="roc-curve"], .roc-curve, text=/ROC Curve|AUC/i');
  }

  /**
   * Check if feature importance is displayed
   */
  async hasFeatureImportance(): Promise<boolean> {
    return await this.isVisible('[data-testid="feature-importance"], .feature-importance, text=/Feature Importance/i');
  }

  /**
   * Save trained model
   */
  async saveModel(modelName?: string) {
    await this.click('button:has-text("Save"), [data-testid="save-model"]');

    if (modelName) {
      await this.fill('input[name="model-name"], [data-testid="model-name"]', modelName);
      await this.click('button:has-text("Confirm"), [data-testid="confirm-save"]');
    }

    // Wait for save confirmation
    await this.waitForElement('text=/Model saved|Saved successfully/i', 5000);
  }

  /**
   * Deploy model
   */
  async deployModel() {
    await this.click('button:has-text("Deploy"), [data-testid="deploy-model"]');

    // Wait for deployment confirmation
    await this.waitForElement('text=/Deployed|Deployment successful/i', 10000);
  }

  /**
   * Compare multiple models
   */
  async compareModels(modelIds: string[]) {
    await this.click('button:has-text("Compare"), [data-testid="compare-models"]');

    // Select models to compare
    for (const modelId of modelIds) {
      const checkbox = this.locator(`input[type="checkbox"][value="${modelId}"], [data-model="${modelId}"]`);
      await checkbox.check();
    }

    await this.click('button:has-text("Compare"), [data-testid="confirm-compare"]');

    // Wait for comparison view
    await this.waitForElement('text=/Comparison|Model Comparison/i', 5000);
  }

  /**
   * Get model version
   */
  async getModelVersion(): Promise<string> {
    return await this.getText('[data-testid="model-version"], .model-version');
  }

  /**
   * Check if cross-validation results are displayed
   */
  async hasCrossValidationResults(): Promise<boolean> {
    return await this.isVisible('[data-testid="cv-results"], text=/Cross.?Validation|CV Score/i');
  }

  /**
   * Get cross-validation score
   */
  async getCrossValidationScore(): Promise<number> {
    const cvElement = this.locator('[data-testid="cv-score"], [data-metric="cv_score"]');

    if (await cvElement.isVisible({ timeout: 5000 })) {
      const text = await cvElement.textContent();
      const match = text?.match(/(\d+\.?\d*)/);
      if (match) {
        return parseFloat(match[1]);
      }
    }

    return 0;
  }

  /**
   * Check for imbalanced dataset warning
   */
  async hasImbalancedDatasetWarning(): Promise<boolean> {
    return await this.isVisible('text=/imbalanced|class imbalance|unbalanced/i');
  }

  /**
   * Check for insufficient data error
   */
  async hasInsufficientDataError(): Promise<boolean> {
    return await this.isVisible('text=/insufficient data|not enough data|too few samples/i');
  }

  /**
   * Check for training failure message
   */
  async hasTrainingFailure(): Promise<boolean> {
    return await this.isVisible('text=/Training failed|Error during training|Failed to train/i');
  }

  /**
   * Get training failure message
   */
  async getFailureMessage(): Promise<string> {
    const failureElement = this.locator('[data-testid="error-message"], .error-message, [role="alert"]');

    if (await failureElement.isVisible({ timeout: 5000 })) {
      return (await failureElement.textContent()) || '';
    }

    return '';
  }

  /**
   * Set cross-validation folds
   */
  async setCrossValidationFolds(folds: number) {
    const input = this.locator('input[name="cv_folds"], [data-testid="cv-folds"]');
    await input.fill(String(folds));
  }

  /**
   * Enable/disable cross-validation
   */
  async toggleCrossValidation(enable: boolean) {
    const checkbox = this.locator('input[type="checkbox"][name="enable_cv"], [data-testid="enable-cv"]');

    if (enable) {
      await checkbox.check();
    } else {
      await checkbox.uncheck();
    }
  }

  /**
   * Validate hyperparameters
   */
  async validateHyperparameters(): Promise<boolean> {
    const validateButton = this.locator('button:has-text("Validate"), [data-testid="validate-params"]');

    if (await validateButton.isVisible({ timeout: 5000 })) {
      await validateButton.click();

      // Check for validation result
      const isValid = await this.page.locator('text=/Valid|Validation successful/i').isVisible({ timeout: 3000 }).catch(() => false);
      return isValid;
    }

    return true; // If no validate button, assume valid
  }

  /**
   * Get model ID from URL or page
   */
  async getModelId(): Promise<string> {
    const url = this.page.url();
    const match = url.match(/\/models\/([a-zA-Z0-9-]+)/);

    if (match) {
      return match[1];
    }

    // Try to get from page element
    const modelIdElement = this.locator('[data-testid="model-id"], [data-model-id]');
    if (await modelIdElement.isVisible({ timeout: 5000 })) {
      const id = await modelIdElement.getAttribute('data-model-id');
      if (id) return id;
    }

    throw new Error('Could not extract model ID from URL or page');
  }
}
