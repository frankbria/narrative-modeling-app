import { classLabel, nameEvaluationClasses } from '@/lib/evaluation/classLabels'
import type { ModelEvaluationResponse } from '@/lib/types/evaluation'

describe('classLabel (#1187)', () => {
  it.each([
    ['1', 'churned = 1'],
    ['0', 'churned = 0'],
    ['2.0', 'churned = 2.0'],
    ['True', 'churned = True'],
    ['false', 'churned = false'],
  ])('names the bare class %s against the target', (label, named) => {
    expect(classLabel(label, 'churned')).toBe(named)
  })

  it('keeps a class that already reads as words', () => {
    expect(classLabel('Month-to-month', 'contract')).toBe('Month-to-month')
  })

  it('keeps the bare class when the target is unknown', () => {
    expect(classLabel('1', null)).toBe('1')
  })
})

const classification: ModelEvaluationResponse = {
  model_id: 'm1',
  model_name: null,
  algorithm: 'Extra Trees',
  problem_type: 'binary_classification',
  target_column: 'churned',
  partial: false,
  evaluation_on_calibration_set: false,
  metrics: {
    accuracy: 0.8,
    precision_macro: 0.8,
    precision_weighted: 0.8,
    recall_macro: 0.8,
    recall_weighted: 0.8,
    f1_macro: 0.8,
    f1_weighted: 0.8,
    roc_auc: 0.9,
    log_loss: null,
    per_class_metrics: { '0': { precision: 0.9, recall: 0.8, f1: 0.85, support: 40 }, '1': { precision: 0.6, recall: 0.7, f1: 0.65, support: 10 } },
  },
  stored_metrics: {},
  confusion_matrix: { labels: ['0', '1'], matrix: [[32, 8], [3, 7]] },
  roc_curve: { curves: { '1': [{ x: 0, y: 0 }] }, auc_per_class: { '1': 0.9 }, macro_auc: null },
  pr_curve: { curves: { '1': [{ x: 0, y: 1 }] }, baseline_per_class: { '1': 0.2 } },
  feature_importance: null,
  ai_explanation: null,
  evaluated_at: '2026-11-08T00:00:00Z',
}

describe('nameEvaluationClasses (#1187)', () => {
  it('renames every class-keyed field together', () => {
    const named = nameEvaluationClasses(classification)
    expect(named.confusion_matrix?.labels).toEqual(['churned = 0', 'churned = 1'])
    expect(Object.keys((named.metrics as { per_class_metrics: object }).per_class_metrics)).toEqual(['churned = 0', 'churned = 1'])
    expect(named.roc_curve?.auc_per_class).toEqual({ 'churned = 1': 0.9 })
    expect(Object.keys(named.roc_curve?.curves ?? {})).toEqual(['churned = 1'])
    expect(named.pr_curve?.baseline_per_class).toEqual({ 'churned = 1': 0.2 })
    expect(Object.keys(named.pr_curve?.curves ?? {})).toEqual(['churned = 1'])
  })

  it('passes a regression or partial evaluation through unchanged', () => {
    const partial = { ...classification, metrics: null, confusion_matrix: null, roc_curve: null, pr_curve: null }
    expect(nameEvaluationClasses(partial)).toEqual(partial)
    const regression = { ...partial, problem_type: 'regression', metrics: { mae: 1, mse: 1, rmse: 1, r2: 0.5, mape: null } }
    expect(nameEvaluationClasses(regression)).toEqual(regression)
  })
})
