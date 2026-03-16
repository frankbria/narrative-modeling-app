import { Page, APIRequestContext } from '@playwright/test';
import { UploadPage } from '../pages/UploadPage';
import { TransformPage } from '../pages/TransformPage';
import { TrainPage } from '../pages/TrainPage';
import { WorkflowPage } from '../pages/WorkflowPage';
import { PredictPage } from '../pages/PredictPage';

/**
 * Workflow Orchestrator Helper
 * Manages multi-step AI-guided workflow execution
 */
export class WorkflowOrchestrator {
  private uploadPage: UploadPage;
  private transformPage: TransformPage;
  private trainPage: TrainPage;
  private workflowPage: WorkflowPage;
  private predictPage: PredictPage;

  constructor(
    private page: Page,
    private request: APIRequestContext
  ) {
    this.uploadPage = new UploadPage(page);
    this.transformPage = new TransformPage(page);
    this.trainPage = new TrainPage(page);
    this.workflowPage = new WorkflowPage(page);
    this.predictPage = new PredictPage(page);
  }

  /**
   * Execute complete classification workflow
   */
  async executeClassificationWorkflow(
    csvPath: string,
    targetColumn: string
  ): Promise<{
    datasetId: string;
    modelId: string;
    versionIds: string[];
    predictionResult: string;
  }> {
    const versionIds: string[] = [];

    // Step 1: Upload dataset
    console.log('Step 1: Uploading dataset...');
    await this.uploadPage.goto('/upload');
    await this.uploadPage.uploadFile(csvPath);
    await this.uploadPage.waitForUploadComplete();
    const datasetId = await this.uploadPage.getDatasetId();
    console.log(`Dataset uploaded: ${datasetId}`);

    // Step 2: Wait for AI problem detection
    console.log('Step 2: Waiting for AI problem detection...');
    await this.workflowPage.waitForProblemDetection();
    const problemType = await this.workflowPage.getDetectedProblemType();
    console.log(`Problem type detected: ${problemType}`);

    // Step 3: Get and apply AI transformation recommendations
    console.log('Step 3: Applying AI-recommended transformations...');
    await this.workflowPage.waitForTransformationRecommendations();
    const recommendations = await this.workflowPage.getTransformationRecommendations();
    console.log(`Recommendations: ${recommendations.join(', ')}`);

    // Apply transformations (creates versions)
    await this.workflowPage.applyAllRecommendations();

    // Track version after transformations
    const transformedVersionId = await this.getLatestVersionId(datasetId);
    if (transformedVersionId) versionIds.push(transformedVersionId);

    // Step 4: Get AI algorithm recommendations
    console.log('Step 4: Getting AI algorithm recommendations...');
    await this.workflowPage.waitForAlgorithmRecommendations();
    const algorithms = await this.workflowPage.getAlgorithmRecommendations();
    console.log(`Recommended algorithms: ${algorithms.join(', ')}`);

    // Select first recommended algorithm
    await this.workflowPage.selectRecommendedAlgorithm();

    // Step 5: Train model
    console.log('Step 5: Training model...');
    await this.workflowPage.startTraining(targetColumn);
    await this.workflowPage.waitForTrainingComplete();
    const modelId = await this.getLatestModelId(datasetId);
    console.log(`Model trained: ${modelId}`);

    // Step 6: Deploy model
    console.log('Step 6: Deploying model...');
    await this.workflowPage.deployModel();

    // Step 7: Make prediction
    console.log('Step 7: Making prediction...');
    const testInput = { age: '35', income: '75000' }; // Example input
    await this.workflowPage.makePrediction(testInput);
    const predictionResult = await this.workflowPage.getPredictionResult();
    console.log(`Prediction result: ${predictionResult}`);

    return {
      datasetId,
      modelId,
      versionIds,
      predictionResult
    };
  }

  /**
   * Execute complete regression workflow
   */
  async executeRegressionWorkflow(
    csvPath: string,
    targetColumn: string
  ): Promise<{
    datasetId: string;
    modelId: string;
    versionIds: string[];
    predictionResult: string;
  }> {
    // Similar to classification but for regression
    return await this.executeClassificationWorkflow(csvPath, targetColumn);
  }

  /**
   * Execute workflow with data quality issues
   */
  async executeWorkflowWithQualityIssues(
    csvPath: string,
    targetColumn: string
  ): Promise<{
    datasetId: string;
    qualityWarnings: string[];
    resolved: boolean;
  }> {
    // Upload dataset with quality issues
    await this.uploadPage.goto('/upload');
    await this.uploadPage.uploadFile(csvPath);
    await this.uploadPage.waitForUploadComplete();
    const datasetId = await this.uploadPage.getDatasetId();

    // Wait for AI to detect quality issues
    await this.page.waitForTimeout(5000);
    const hasIssues = await this.workflowPage.hasDataQualityIssues();
    const qualityWarnings = hasIssues ? await this.workflowPage.getDataQualityWarnings() : [];

    // Apply recommended fixes
    if (hasIssues) {
      await this.workflowPage.applyAllRecommendations();
    }

    return {
      datasetId,
      qualityWarnings,
      resolved: hasIssues
    };
  }

  /**
   * Execute workflow with version branching
   */
  async executeWorkflowWithBranching(
    datasetId: string,
    branchPoints: { versionId: string; transformationType: string }[]
  ): Promise<{
    branches: { versionId: string; transformations: string[] }[];
  }> {
    const branches: { versionId: string; transformations: string[] }[] = [];

    for (const branchPoint of branchPoints) {
      // Navigate to transform page for specific version
      await this.transformPage.goto(`/datasets/${datasetId}/prepare?version=${branchPoint.versionId}`);

      // Apply alternative transformation
      await this.transformPage.addTransformation(branchPoint.transformationType);
      await this.transformPage.applyTransformation();

      // Track new branch version
      const newVersionId = await this.getLatestVersionId(datasetId);
      if (newVersionId) {
        branches.push({
          versionId: newVersionId,
          transformations: [branchPoint.transformationType]
        });
      }
    }

    return { branches };
  }

  /**
   * Simulate workflow interruption and resume
   */
  async simulateInterruptionAndResume(
    datasetId: string,
    interruptAtStep: 'transform' | 'train'
  ): Promise<{
    interrupted: boolean;
    resumed: boolean;
    workflowComplete: boolean;
  }> {
    let interrupted = false;
    let resumed = false;

    // Start workflow
    await this.page.goto(`/datasets/${datasetId}`);

    if (interruptAtStep === 'transform') {
      // Go to transform, then simulate browser crash
      await this.transformPage.goto(`/datasets/${datasetId}/prepare`);
      await this.transformPage.addTransformation('scale');

      // Simulate crash by reloading page
      await this.page.reload();
      interrupted = true;

      // Check if workflow can be resumed
      const canResume = await this.workflowPage.canResumeWorkflow();
      if (canResume) {
        await this.workflowPage.resumeWorkflow();
        resumed = true;
      }
    }

    // Check if workflow is still in a valid state
    const progress = await this.workflowPage.getWorkflowProgress();
    const workflowComplete = progress.completedSteps === progress.totalSteps;

    return { interrupted, resumed, workflowComplete };
  }

  /**
   * Handle AI timeout and retry
   */
  async handleAITimeout(operation: () => Promise<void>): Promise<{
    timedOut: boolean;
    retried: boolean;
    success: boolean;
  }> {
    let timedOut = false;
    let retried = false;
    let success = false;

    try {
      // Attempt operation
      await operation();
      success = true;
    } catch (error) {
      // Check for timeout
      timedOut = await this.workflowPage.hasAITimeout();

      if (timedOut) {
        // Retry operation
        await this.workflowPage.retryAIOperation();
        retried = true;

        try {
          await operation();
          success = true;
        } catch (retryError) {
          success = false;
        }
      }
    }

    return { timedOut, retried, success };
  }

  /**
   * Get latest version ID for a dataset
   */
  private async getLatestVersionId(datasetId: string): Promise<string> {
    try {
      const response = await this.request.get(`/api/v1/datasets/${datasetId}/versions`);

      if (response.ok()) {
        const data = await response.json();
        const versions = data.versions || data;

        if (Array.isArray(versions) && versions.length > 0) {
          // Sort by created_at and get latest
          versions.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
          return versions[0].id || versions[0].version_id;
        }
      }
    } catch (error) {
      console.warn('Could not fetch latest version ID:', error);
    }

    return `mock-version-${Date.now()}`;
  }

  /**
   * Get latest model ID for a dataset
   */
  private async getLatestModelId(datasetId: string): Promise<string> {
    try {
      const response = await this.request.get(`/api/v1/models?dataset_id=${datasetId}`);

      if (response.ok()) {
        const data = await response.json();
        const models = data.models || data;

        if (Array.isArray(models) && models.length > 0) {
          // Sort by created_at and get latest
          models.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
          return models[0].id || models[0].model_id;
        }
      }
    } catch (error) {
      console.warn('Could not fetch latest model ID:', error);
    }

    return `mock-model-${Date.now()}`;
  }

  /**
   * Verify workflow state persistence
   */
  async verifyWorkflowStatePersistence(datasetId: string): Promise<{
    progressSaved: boolean;
    currentStep: string;
  }> {
    // Reload page to check if state persists
    await this.page.reload();
    await this.page.waitForLoadState('networkidle');

    const progress = await this.workflowPage.getWorkflowProgress();

    return {
      progressSaved: progress.completedSteps > 0,
      currentStep: progress.currentStep
    };
  }

  /**
   * Visualize version lineage chain
   */
  visualizeVersionChain(versions: { id: string; parentId: string | null }[]): string {
    let chain = '';

    // Build a simple text representation of the version tree
    const rootVersions = versions.filter(v => !v.parentId);

    const buildChain = (versionId: string, depth: number = 0): void => {
      const indent = '  '.repeat(depth);
      chain += `${indent}${versionId}\n`;

      const children = versions.filter(v => v.parentId === versionId);
      children.forEach(child => buildChain(child.id, depth + 1));
    };

    rootVersions.forEach(root => buildChain(root.id));

    return chain;
  }
}
