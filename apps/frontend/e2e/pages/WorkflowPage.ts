import { Page } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Workflow Page Object
 * Handles AI-guided workflow interactions
 */
export class WorkflowPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to workflow dashboard
   */
  async gotoDashboard() {
    await this.goto('/dashboard');
  }

  /**
   * Start a new workflow
   */
  async startWorkflow() {
    await this.click('button:has-text("New Workflow"), button:has-text("Start"), [data-testid="start-workflow"]');
  }

  /**
   * Wait for AI problem detection to complete
   */
  async waitForProblemDetection(timeout: number = 120000) {
    // Wait for AI to analyze and detect problem type
    await this.waitForElement('text=/Problem type|Detected|classification|regression/i', timeout);
  }

  /**
   * Verify detected problem type
   */
  async getDetectedProblemType(): Promise<string> {
    const element = this.page.locator('[data-testid="problem-type"], .problem-type, [data-problem]');
    const text = await element.textContent();
    return text?.toLowerCase().includes('classification') ? 'classification' : 'regression';
  }

  /**
   * Wait for AI transformation recommendations
   */
  async waitForTransformationRecommendations(timeout: number = 120000) {
    await this.waitForElement('[data-testid="ai-recommendations"], .ai-suggestions, text=/Recommended transformations/i', timeout);
  }

  /**
   * Get AI transformation recommendations
   */
  async getTransformationRecommendations(): Promise<string[]> {
    const recommendations: string[] = [];
    const elements = this.page.locator('[data-testid="recommendation-item"], .recommendation, [data-transformation]');
    const count = await elements.count();

    for (let i = 0; i < count; i++) {
      const text = await elements.nth(i).textContent();
      if (text) recommendations.push(text.trim());
    }

    return recommendations;
  }

  /**
   * Apply recommended transformation
   */
  async applyRecommendedTransformation(index: number = 0) {
    const buttons = this.page.locator('button:has-text("Apply"), [data-testid="apply-recommendation"]');
    await buttons.nth(index).click();

    // Wait for transformation to complete
    await this.waitForElement('text=/Applied|Transformation complete/i', 30000);
  }

  /**
   * Apply all recommended transformations
   */
  async applyAllRecommendations() {
    await this.click('button:has-text("Apply All"), [data-testid="apply-all-recommendations"]');

    // Wait for all transformations to complete
    await this.waitForElement('text=/All transformations applied|Complete/i', 60000);
  }

  /**
   * Wait for AI algorithm recommendations
   */
  async waitForAlgorithmRecommendations(timeout: number = 120000) {
    await this.waitForElement('[data-testid="algorithm-recommendations"], text=/Recommended algorithms/i', timeout);
  }

  /**
   * Get AI algorithm recommendations
   */
  async getAlgorithmRecommendations(): Promise<string[]> {
    const algorithms: string[] = [];
    const elements = this.page.locator('[data-testid="algorithm-item"], .algorithm-recommendation, [data-algorithm]');
    const count = await elements.count();

    for (let i = 0; i < count; i++) {
      const text = await elements.nth(i).textContent();
      if (text) algorithms.push(text.trim());
    }

    return algorithms;
  }

  /**
   * Select recommended algorithm
   */
  async selectRecommendedAlgorithm(algorithmName?: string) {
    if (algorithmName) {
      // Select specific algorithm
      await this.page.click(`[data-algorithm="${algorithmName}"], button:has-text("${algorithmName}")`);
    } else {
      // Select first recommended algorithm
      const algorithms = this.page.locator('[data-testid="algorithm-item"], .algorithm-recommendation');
      await algorithms.first().click();
    }
  }

  /**
   * Start model training
   */
  async startTraining(targetColumn: string) {
    // Select target column
    await this.page.click('select[name="target"], [data-testid="target-column-select"]');
    await this.page.click(`option:has-text("${targetColumn}"), [data-column="${targetColumn}"]`);

    // Click train button
    await this.click('button:has-text("Train"), [data-testid="start-training"]');
  }

  /**
   * Wait for training to complete
   */
  async waitForTrainingComplete(timeout: number = 180000) {
    await this.waitForElement('text=/Training complete|Model trained|Training finished/i', timeout);
  }

  /**
   * Get training status
   */
  async getTrainingStatus(): Promise<'training' | 'completed' | 'failed'> {
    if (await this.isVisible('text=/Training complete|completed/i')) {
      return 'completed';
    } else if (await this.isVisible('text=/Training failed|error/i')) {
      return 'failed';
    }
    return 'training';
  }

  /**
   * Deploy the trained model
   */
  async deployModel() {
    await this.click('button:has-text("Deploy"), [data-testid="deploy-model"]');

    // Wait for deployment confirmation
    await this.waitForElement('text=/Deployed|Deployment successful/i', 30000);
  }

  /**
   * Make a prediction
   */
  async makePrediction(inputData: Record<string, string | number>) {
    // Navigate to predict page
    await this.click('button:has-text("Predict"), a[href*="predict"], [data-testid="navigate-predict"]');

    // Fill input fields
    for (const [field, value] of Object.entries(inputData)) {
      await this.fill(`input[name="${field}"], [data-field="${field}"]`, String(value));
    }

    // Submit prediction
    await this.click('button:has-text("Predict"), [data-testid="submit-prediction"]');

    // Wait for prediction result
    await this.waitForElement('[data-testid="prediction-result"], .prediction-output', 15000);
  }

  /**
   * Get prediction result
   */
  async getPredictionResult(): Promise<string> {
    const result = await this.getText('[data-testid="prediction-result"], [data-prediction], .prediction-value');
    return result;
  }

  /**
   * Check for data quality issues
   */
  async hasDataQualityIssues(): Promise<boolean> {
    return await this.isVisible('text=/missing values|outliers|imbalanced|data quality/i');
  }

  /**
   * Get data quality warnings
   */
  async getDataQualityWarnings(): Promise<string[]> {
    const warnings: string[] = [];
    const elements = this.page.locator('[data-testid="quality-warning"], .data-quality-issue, [data-issue]');
    const count = await elements.count();

    for (let i = 0; i < count; i++) {
      const text = await elements.nth(i).textContent();
      if (text) warnings.push(text.trim());
    }

    return warnings;
  }

  /**
   * Get workflow progress
   */
  async getWorkflowProgress(): Promise<{
    currentStep: string;
    completedSteps: number;
    totalSteps: number;
  }> {
    const currentStep = await this.getText('[data-testid="current-step"], .active-step');
    const progress = await this.getText('[data-testid="workflow-progress"], .progress-indicator');

    // Parse progress (e.g., "3/7 steps completed")
    const match = progress.match(/(\d+)\/(\d+)/);
    const completedSteps = match ? parseInt(match[1]) : 0;
    const totalSteps = match ? parseInt(match[2]) : 7;

    return {
      currentStep: currentStep.trim(),
      completedSteps,
      totalSteps
    };
  }

  /**
   * Check if workflow is resumable after interruption
   */
  async canResumeWorkflow(): Promise<boolean> {
    return await this.isVisible('button:has-text("Resume"), [data-testid="resume-workflow"]');
  }

  /**
   * Resume interrupted workflow
   */
  async resumeWorkflow() {
    await this.click('button:has-text("Resume"), [data-testid="resume-workflow"]');

    // Wait for workflow to resume
    await this.waitForElement('[data-testid="workflow-active"], text=/Resuming|Resumed/i', 10000);
  }

  /**
   * Check for AI timeout error
   */
  async hasAITimeout(): Promise<boolean> {
    return await this.isVisible('text=/AI timeout|request timed out|AI service unavailable/i');
  }

  /**
   * Retry AI operation after timeout
   */
  async retryAIOperation() {
    await this.click('button:has-text("Retry"), [data-testid="retry-ai"]');

    // Wait for retry to start
    await this.page.waitForTimeout(2000);
  }

  /**
   * Navigate to specific workflow step
   */
  async goToWorkflowStep(step: 'upload' | 'transform' | 'train' | 'deploy' | 'predict') {
    const stepLinks: Record<string, string> = {
      upload: 'Upload',
      transform: 'Transform',
      train: 'Train',
      deploy: 'Deploy',
      predict: 'Predict'
    };

    await this.page.click(`a:has-text("${stepLinks[step]}"), [data-step="${step}"]`);
    await this.page.waitForLoadState('networkidle');
  }
}
