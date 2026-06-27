import {
  buildEvaluationCSV,
  buildEvaluationPDFDoc,
  exportEvaluationPDF,
} from '@/lib/utils/export'
import type { ModelEvaluationResponse } from '@/lib/types/evaluation'
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'

const mockDoc = {
  text: jest.fn(),
  setFontSize: jest.fn(),
  setFont: jest.fn(),
  splitTextToSize: jest.fn((text: string) => [text]),
  addPage: jest.fn(),
  save: jest.fn(),
  internal: { pageSize: { getWidth: () => 210, getHeight: () => 297 } },
}

jest.mock('jspdf', () => ({
  jsPDF: jest.fn(() => mockDoc),
}))

jest.mock('jspdf-autotable', () => ({
  __esModule: true,
  default: jest.fn(),
}))

const classificationEvaluation: ModelEvaluationResponse = {
  model_id: 'm1',
  model_name: 'Churn, "v2"',
  algorithm: 'random_forest',
  problem_type: 'binary_classification',
  partial: false,
  evaluation_on_calibration_set: false,
  metrics: {
    accuracy: 0.91,
    precision_macro: 0.9,
    precision_weighted: 0.91,
    recall_macro: 0.89,
    recall_weighted: 0.91,
    f1_macro: 0.9,
    f1_weighted: 0.91,
    roc_auc: 0.95,
    log_loss: null,
    per_class_metrics: {
      yes: { precision: 0.9, recall: 0.88, f1: 0.89, support: 50 },
    },
  },
  stored_metrics: { cv_score: 0.9 },
  confusion_matrix: { labels: ['yes', 'no'], matrix: [[44, 6], [5, 65]] },
  roc_curve: null,
  pr_curve: null,
  feature_importance: { income: 0.4, age: 0.6 },
  ai_explanation: {
    overall_assessment: 'Strong model.',
    metric_explanations: {},
    strengths: ['High accuracy'],
    concerns: [],
    recommendations: ['Collect more data'],
    generated_by: 'openai',
  },
  evaluated_at: '2026-06-11T00:00:00Z',
}

const regressionEvaluation: ModelEvaluationResponse = {
  model_id: 'm2',
  model_name: null,
  algorithm: 'linear_regression',
  problem_type: 'regression',
  partial: false,
  evaluation_on_calibration_set: false,
  metrics: { mae: 3.2, mse: 16.8, rmse: 4.1, r2: 0.84, mape: null },
  stored_metrics: {},
  confusion_matrix: null,
  roc_curve: null,
  pr_curve: null,
  feature_importance: null,
  ai_explanation: null,
  evaluated_at: '2026-06-11T00:00:00Z',
}

describe('buildEvaluationCSV', () => {
  it('builds the classification CSV with all sections and RFC4180 escaping', () => {
    const csv = buildEvaluationCSV(classificationEvaluation)

    expect(csv).toBe(
      [
        'Model Info',
        'Field,Value',
        'Model ID,m1',
        'Name,"Churn, ""v2"""',
        'Algorithm,random_forest',
        'Problem Type,binary_classification',
        'Evaluated At,2026-06-11T00:00:00Z',
        '',
        'Metrics',
        'Metric,Value',
        'accuracy,0.91',
        'precision_macro,0.9',
        'precision_weighted,0.91',
        'recall_macro,0.89',
        'recall_weighted,0.91',
        'f1_macro,0.9',
        'f1_weighted,0.91',
        'roc_auc,0.95',
        '',
        'Per-Class Metrics',
        'Class,Precision,Recall,F1,Support',
        'yes,0.9,0.88,0.89,50',
        '',
        'Confusion Matrix',
        'Actual \\ Predicted,yes,no',
        'yes,44,6',
        'no,5,65',
        '',
        'Feature Importance',
        'Feature,Importance',
        'age,0.6',
        'income,0.4',
      ].join('\n')
    )
  })

  it('quotes fields containing carriage returns (RFC 4180)', () => {
    const evaluation = {
      ...classificationEvaluation,
      model_name: 'line one\rline two',
    }
    const csv = buildEvaluationCSV(evaluation)
    expect(csv).toContain('Name,"line one\rline two"')
  })

  it('builds the regression CSV without classification-only sections', () => {
    const csv = buildEvaluationCSV(regressionEvaluation)

    expect(csv).toBe(
      [
        'Model Info',
        'Field,Value',
        'Model ID,m2',
        'Name,',
        'Algorithm,linear_regression',
        'Problem Type,regression',
        'Evaluated At,2026-06-11T00:00:00Z',
        '',
        'Metrics',
        'Metric,Value',
        'mae,3.2',
        'mse,16.8',
        'rmse,4.1',
        'r2,0.84',
      ].join('\n')
    )
  })

  it('falls back to stored metrics for partial evaluations', () => {
    const partial: ModelEvaluationResponse = {
      ...regressionEvaluation,
      partial: true,
      metrics: null,
      stored_metrics: { cv_score: 0.88, test_score: 0.86 },
    }

    const csv = buildEvaluationCSV(partial)

    expect(csv).toContain('cv_score,0.88')
    expect(csv).toContain('test_score,0.86')
  })
})

describe('buildEvaluationPDFDoc', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('creates a doc with title, metadata, metrics table and confusion matrix', () => {
    const doc = buildEvaluationPDFDoc(classificationEvaluation)

    expect(doc).toBe(mockDoc)
    expect(jsPDF).toHaveBeenCalledTimes(1)

    const textCalls = mockDoc.text.mock.calls.flat()
    expect(textCalls).toEqual(
      expect.arrayContaining([expect.stringMatching(/Model Evaluation Report/)])
    )

    // Metrics table + per-class table + confusion matrix table.
    const tableCalls = (autoTable as jest.Mock).mock.calls
    expect(tableCalls.length).toBe(3)
    const metricsBody = tableCalls[0][1].body as string[][]
    expect(metricsBody).toEqual(
      expect.arrayContaining([['accuracy', '0.91'], ['roc_auc', '0.95']])
    )
    const confusionHead = tableCalls[2][1].head as string[][]
    expect(confusionHead[0]).toEqual(['Actual \\ Predicted', 'yes', 'no'])

    // AI explanation is wrapped into the doc.
    expect(mockDoc.splitTextToSize).toHaveBeenCalledWith(
      'Strong model.',
      expect.any(Number)
    )
    expect(mockDoc.save).not.toHaveBeenCalled()
  })

  it('omits the confusion matrix table for regression models', () => {
    buildEvaluationPDFDoc(regressionEvaluation)

    expect((autoTable as jest.Mock).mock.calls.length).toBe(1)
    const metricsBody = (autoTable as jest.Mock).mock.calls[0][1].body as string[][]
    expect(metricsBody).toEqual(expect.arrayContaining([['mae', '3.2'], ['r2', '0.84']]))
  })
})

describe('exportEvaluationPDF', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('saves the document as evaluation-{model_id}.pdf', () => {
    exportEvaluationPDF(classificationEvaluation)

    expect(mockDoc.save).toHaveBeenCalledWith('evaluation-m1.pdf')
  })
})
