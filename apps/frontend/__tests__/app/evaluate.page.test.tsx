import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import EvaluatePage from '@/app/evaluate/page'
import { WorkflowStage } from '@/lib/types/workflow'
import type { ModelEvaluationResponse } from '@/lib/types/evaluation'

// Router. The object must be stable across renders (like the real Next.js
// router): the page's load effect depends on `router`, so a fresh object per
// render would re-trigger the fetch in an infinite loop.
const mockPush = jest.fn()
const mockRouter = { push: mockPush, replace: jest.fn(), prefetch: jest.fn() }
jest.mock('next/navigation', () => ({
  useRouter: () => mockRouter,
}))

// Authenticated session
jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'u1' } }, status: 'authenticated' }),
}))

jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('mock-token'),
}))

// Real recharts, with only ResponsiveContainer sized so jsdom's 0x0 layout
// doesn't blank the charts (#346). The old passthrough mock ignored props
// entirely, so this page could render charts the library can't.
jest.mock('recharts', () =>
  jest.requireActual('@/__tests__/utils/sizedRecharts').sizedRecharts()
)

// Export utils touch URL.createObjectURL / jspdf, which jsdom lacks.
const mockExportCSV = jest.fn()
const mockExportPDF = jest.fn()
jest.mock('@/lib/utils/export', () => ({
  exportEvaluationCSV: (...args: unknown[]) => mockExportCSV(...args),
  exportEvaluationPDF: (...args: unknown[]) => mockExportPDF(...args),
}))

// Workflow context: evaluation stage accessible, model trained.
const mockCompleteStage = jest.fn()
const mockCanAccessStage = jest.fn(() => true)
const mockGoToNextStage = jest.fn()
const mockGoToPreviousStage = jest.fn()
const mockRequestStageRedirect = jest.fn()
const mockWorkflowContext = {
  state: {
    currentStage: WorkflowStage.MODEL_EVALUATION,
    completedStages: new Set<WorkflowStage>([WorkflowStage.MODEL_TRAINING]),
    stageData: {} as Record<WorkflowStage, unknown>,
    datasetId: 'ds-1',
    modelId: 'm1',
  },
  isHydrated: true,
  guardMessage: null,
  canAccessStage: mockCanAccessStage,
  completeStage: mockCompleteStage,
  setCurrentStage: jest.fn(),
  setDatasetId: jest.fn(),
  resetWorkflow: jest.fn(),
  loadWorkflow: jest.fn(),
  saveWorkflow: jest.fn(),
  goToNextStage: mockGoToNextStage,
  goToPreviousStage: mockGoToPreviousStage,
  requestStageRedirect: mockRequestStageRedirect,
  clearGuardMessage: jest.fn(),
}
jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => mockWorkflowContext,
}))

// Model service
const mockGetEvaluation = jest.fn()
const mockListModels = jest.fn()
const mockCompareModels = jest.fn()
jest.mock('@/lib/services/model', () => ({
  modelService: {
    getEvaluation: (...args: unknown[]) => mockGetEvaluation(...args),
    listModels: (...args: unknown[]) => mockListModels(...args),
    compareModels: (...args: unknown[]) => mockCompareModels(...args),
    // SHAP summary is best-effort enrichment (issue #80); default to a partial
    // response so the page renders without the SHAP chart in these tests.
    getShapSummary: () =>
      Promise.resolve({
        model_id: 'm1',
        partial: true,
        explainer_type: null,
        problem_type: 'binary_classification',
        feature_importance: [],
        base_value: null,
        plain_language: '',
        message: 'unavailable',
        evaluated_at: '2026-06-14T00:00:00Z',
      }),
  },
}))

const classificationEvaluation: ModelEvaluationResponse = {
  model_id: 'm1',
  model_name: 'Churn Model',
  algorithm: 'random_forest',
  problem_type: 'binary_classification',
  partial: false,
  evaluation_on_calibration_set: false,
  metrics: {
    accuracy: 0.91,
    precision_macro: 0.9,
    precision_weighted: 0.905,
    recall_macro: 0.89,
    recall_weighted: 0.912,
    f1_macro: 0.9,
    f1_weighted: 0.9075,
    roc_auc: 0.95,
    log_loss: 0.31,
    per_class_metrics: {
      yes: { precision: 0.9, recall: 0.88, f1: 0.89, support: 50 },
      no: { precision: 0.92, recall: 0.93, f1: 0.92, support: 70 },
    },
  },
  stored_metrics: { cv_score: 0.9, test_score: 0.91 },
  confusion_matrix: { labels: ['yes', 'no'], matrix: [[44, 6], [5, 65]] },
  roc_curve: {
    curves: { yes: [{ x: 0, y: 0 }, { x: 1, y: 1 }] },
    auc_per_class: { yes: 0.95 },
    macro_auc: 0.95,
  },
  pr_curve: {
    curves: { yes: [{ x: 0, y: 1 }, { x: 1, y: 0.42 }] },
    baseline_per_class: { yes: 0.42 },
  },
  feature_importance: { age: 0.6, income: 0.4 },
  ai_explanation: {
    overall_assessment: 'This model performs strongly on held-out data.',
    metric_explanations: { accuracy: '91% of predictions correct.' },
    strengths: ['High accuracy'],
    concerns: ['Mild class imbalance'],
    recommendations: ['Collect more minority-class data'],
    generated_by: 'openai',
  },
  evaluated_at: '2026-06-11T00:00:00Z',
}

const regressionEvaluation: ModelEvaluationResponse = {
  model_id: 'm2',
  model_name: 'Price Model',
  algorithm: 'linear_regression',
  problem_type: 'regression',
  partial: false,
  evaluation_on_calibration_set: false,
  metrics: { mae: 3.2, mse: 16.81, rmse: 4.1, r2: 0.84, mape: 12.5 },
  stored_metrics: { cv_score: 0.83 },
  confusion_matrix: null,
  roc_curve: null,
  pr_curve: null,
  feature_importance: null,
  ai_explanation: {
    overall_assessment: 'Solid regression fit.',
    metric_explanations: {},
    strengths: ['Low error'],
    concerns: [],
    recommendations: [],
    generated_by: 'fallback',
  },
  evaluated_at: '2026-06-11T00:00:00Z',
}

describe('EvaluatePage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockCanAccessStage.mockReturnValue(true)
    mockWorkflowContext.state.modelId = 'm1'
  })

  it('redirects with a guard message when the evaluation stage is not accessible', () => {
    mockCanAccessStage.mockReturnValue(false)
    mockGetEvaluation.mockResolvedValue(classificationEvaluation)

    render(<EvaluatePage />)

    expect(mockRequestStageRedirect).toHaveBeenCalledTimes(1)
    expect(mockGetEvaluation).not.toHaveBeenCalled()
  })

  it('redirects to model training when no model id is in the workflow state', () => {
    mockWorkflowContext.state.modelId = ''
    mockGetEvaluation.mockResolvedValue(classificationEvaluation)

    render(<EvaluatePage />)

    expect(mockRequestStageRedirect).toHaveBeenCalledWith(
      WorkflowStage.MODEL_TRAINING,
      expect.stringMatching(/train a model/i)
    )
    expect(mockGetEvaluation).not.toHaveBeenCalled()
  })

  it('renders classification metrics, the report card and the model badge', async () => {
    mockGetEvaluation.mockResolvedValue(classificationEvaluation)

    render(<EvaluatePage />)

    expect(await screen.findByText('Churn Model')).toBeInTheDocument()
    expect(screen.getByText('random_forest')).toBeInTheDocument()
    expect(mockGetEvaluation).toHaveBeenCalledWith('m1')

    // Classification metric cards
    expect(screen.getByText('Accuracy')).toBeInTheDocument()
    expect(screen.getByText('0.9100')).toBeInTheDocument()
    expect(screen.getByText('ROC AUC')).toBeInTheDocument()

    // Model report card driven by the AI explanation
    expect(
      screen.getByText('This model performs strongly on held-out data.')
    ).toBeInTheDocument()
    expect(screen.getByText('High accuracy')).toBeInTheDocument()
    expect(screen.getByText('Mild class imbalance')).toBeInTheDocument()
    expect(screen.getByText('Collect more minority-class data')).toBeInTheDocument()
    expect(screen.getByText('AI-generated')).toBeInTheDocument()

    // Classification-only tabs are offered
    expect(screen.getByRole('tab', { name: /confusion matrix/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /curves/i })).toBeInTheDocument()
  })

  it('renders regression metric cards without classification tabs', async () => {
    mockGetEvaluation.mockResolvedValue(regressionEvaluation)

    render(<EvaluatePage />)

    expect(await screen.findByText('Price Model')).toBeInTheDocument()
    expect(screen.getByText('MAE')).toBeInTheDocument()
    expect(screen.getByText('3.2000')).toBeInTheDocument()
    expect(screen.getByText('R²')).toBeInTheDocument()
    expect(screen.getByText('Rule-based')).toBeInTheDocument()

    expect(
      screen.queryByRole('tab', { name: /confusion matrix/i })
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: /curves/i })).not.toBeInTheDocument()
  })

  it('shows the partial banner with stored metrics for legacy models', async () => {
    mockGetEvaluation.mockResolvedValue({
      ...classificationEvaluation,
      partial: true,
      metrics: null,
      confusion_matrix: null,
      roc_curve: null,
      pr_curve: null,
      feature_importance: null,
      ai_explanation: null,
      stored_metrics: { cv_score: 0.88, test_score: 0.86 },
    })

    render(<EvaluatePage />)

    expect(
      await screen.findByText(/trained before evaluation persistence/i)
    ).toBeInTheDocument()
    expect(screen.getByText('Cv Score')).toBeInTheDocument()
    expect(screen.getByText('0.8800')).toBeInTheDocument()
    expect(screen.getByText('Test Score')).toBeInTheDocument()
  })

  it('shows the error state when the evaluation fetch fails', async () => {
    mockGetEvaluation.mockRejectedValue(new Error('Model not found'))

    render(<EvaluatePage />)

    expect(await screen.findByText(/failed to load evaluation/i)).toBeInTheDocument()
    expect(screen.getByText('Model not found')).toBeInTheDocument()
  })

  it('shows the no-data state when no evaluation is returned', async () => {
    mockGetEvaluation.mockResolvedValue(null)

    render(<EvaluatePage />)

    expect(await screen.findByText(/no evaluation data/i)).toBeInTheDocument()
  })

  it('completes the evaluation stage and advances when continuing to prediction', async () => {
    mockGetEvaluation.mockResolvedValue(classificationEvaluation)

    render(<EvaluatePage />)
    await screen.findByText('Churn Model')

    fireEvent.click(screen.getByRole('button', { name: /continue to prediction/i }))

    expect(mockCompleteStage).toHaveBeenCalledTimes(1)
    const [stage, payload] = mockCompleteStage.mock.calls[0]
    expect(stage).toBe(WorkflowStage.MODEL_EVALUATION)
    expect(payload).toMatchObject({
      evaluationComplete: true,
      metrics: classificationEvaluation.metrics,
    })
    // After recording completion, StageNavigation advances to the next stage.
    await waitFor(() => expect(mockGoToNextStage).toHaveBeenCalledTimes(1))
  })

  it('navigates back to the previous stage', async () => {
    mockGetEvaluation.mockResolvedValue(classificationEvaluation)

    render(<EvaluatePage />)
    await screen.findByText('Churn Model')

    fireEvent.click(screen.getByRole('button', { name: /back/i }))

    expect(mockGoToPreviousStage).toHaveBeenCalledTimes(1)
  })

  it('exports CSV and PDF from the header buttons', async () => {
    mockGetEvaluation.mockResolvedValue(classificationEvaluation)

    render(<EvaluatePage />)
    await screen.findByText('Churn Model')

    fireEvent.click(screen.getByRole('button', { name: /export csv/i }))
    fireEvent.click(screen.getByRole('button', { name: /export pdf/i }))

    expect(mockExportCSV).toHaveBeenCalledWith(classificationEvaluation)
    expect(mockExportPDF).toHaveBeenCalledWith(classificationEvaluation)
  })

  it('shows the confusion matrix when its tab is selected', async () => {
    mockGetEvaluation.mockResolvedValue(classificationEvaluation)

    render(<EvaluatePage />)
    await screen.findByText('Churn Model')

    // Radix tab triggers activate on mousedown (StatisticsDashboard.test.tsx pattern)
    fireEvent.mouseDown(screen.getByRole('tab', { name: /confusion matrix/i }))

    expect(
      await screen.findByRole('button', { name: /actual yes, predicted yes: 44/i })
    ).toBeInTheDocument()
  })

  it('compares selected models in the Compare tab', async () => {
    mockGetEvaluation.mockResolvedValue(classificationEvaluation)
    mockListModels.mockResolvedValue([
      { model_id: 'm1', name: 'Churn Model', algorithm: 'random_forest' },
      { model_id: 'm9', name: 'Challenger', algorithm: 'logistic_regression' },
    ])
    mockCompareModels.mockResolvedValue({
      problem_type: 'binary_classification',
      dataset_id: 'ds-1',
      models: [
        {
          model_id: 'm1',
          name: 'Churn Model',
          algorithm: 'random_forest',
          problem_type: 'binary_classification',
          cv_score: 0.9,
          test_score: 0.91,
          metrics: { accuracy: 0.91 },
          created_at: null,
        },
        {
          model_id: 'm9',
          name: 'Challenger',
          algorithm: 'logistic_regression',
          problem_type: 'binary_classification',
          cv_score: 0.86,
          test_score: 0.85,
          metrics: { accuracy: 0.85 },
          created_at: null,
        },
      ],
    })

    render(<EvaluatePage />)
    await screen.findByText('Churn Model')

    fireEvent.mouseDown(screen.getByRole('tab', { name: /compare/i }))

    await waitFor(() => expect(mockListModels).toHaveBeenCalledWith('ds-1'))

    fireEvent.click(await screen.findByRole('checkbox', { name: /churn model/i }))
    fireEvent.click(screen.getByRole('checkbox', { name: /challenger/i }))

    const compareButton = screen.getByRole('button', { name: /^compare$/i })
    expect(compareButton).toBeEnabled()
    fireEvent.click(compareButton)

    await waitFor(() =>
      expect(mockCompareModels).toHaveBeenCalledWith(['m1', 'm9'])
    )
    expect(await screen.findByTestId('cell-accuracy-m1')).toHaveAttribute(
      'data-best',
      'true'
    )
  })

  it('requires at least two models before comparing', async () => {
    mockGetEvaluation.mockResolvedValue(classificationEvaluation)
    mockListModels.mockResolvedValue([
      { model_id: 'm1', name: 'Churn Model', algorithm: 'random_forest' },
      { model_id: 'm9', name: 'Challenger', algorithm: 'logistic_regression' },
    ])

    render(<EvaluatePage />)
    await screen.findByText('Churn Model')

    fireEvent.mouseDown(screen.getByRole('tab', { name: /compare/i }))
    fireEvent.click(await screen.findByRole('checkbox', { name: /churn model/i }))

    expect(screen.getByRole('button', { name: /^compare$/i })).toBeDisabled()
  })
})
