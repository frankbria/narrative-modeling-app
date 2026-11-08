import {
  buildVerdict,
  confusionReading,
  majorityBaseline,
  metricRows,
  modelTitle,
  prReading,
  rocReading,
  topDrivers
} from '@/components/evaluate/evaluationReading'
import type { ModelEvaluationResponse } from '@/lib/types/evaluation'

describe('evaluationReading', () => {
  it('names the class the model missed most, with the real label', () => {
    const reading = confusionReading({ labels: ['stayed', 'churned'], matrix: [[90, 10], [47, 49]] })
    expect(reading).toBe('Of 96 rows that really were "churned", the model missed 47.')
  })

  it('has no reading for an empty matrix', () => {
    expect(confusionReading({ labels: ['a'], matrix: [[0]] })).toBeNull()
    expect(majorityBaseline([[0]])).toBeNull()
  })

  it('reads the baseline off the most common class', () => {
    expect(majorityBaseline([[7, 1], [1, 1]])).toBe(0.8)
  })

  it('lists the top three drivers in words', () => {
    expect(topDrivers({ a_b: 5, c: 4, d: 3, e: 1 })).toBe('Mostly driven by a b, c and d.')
    expect(topDrivers(null)).toBeNull()
  })

  it('explains ROC and PR curves, or stays silent without the numbers', () => {
    expect(rocReading({ curves: {}, auc_per_class: {}, macro_auc: 0.9 })).toContain('90%')
    expect(rocReading({ curves: {}, auc_per_class: {}, macro_auc: null })).toBeNull()
    expect(prReading({ curves: {}, baseline_per_class: { yes: 0.42 } })).toContain('42% precision for "yes"')
    expect(prReading({ curves: {}, baseline_per_class: {} })).toBeNull()
  })

  it('has no metric rows for a legacy model with only stored metrics', () => {
    expect(metricRows({ metrics: null } as ModelEvaluationResponse)).toEqual([])
  })

  it('skips a ranking score the model could not compute', () => {
    const rows = metricRows({
      metrics: {
        accuracy: 0.8, precision_weighted: 0.8, recall_weighted: 0.8, f1_weighted: 0.8,
        roc_auc: null
      }
    } as ModelEvaluationResponse)
    expect(rows.map((r) => r.label)).not.toContain('Ranking ability')
  })

  it('says when the model does not beat the baseline, and has no verdict without metrics', () => {
    const weak = {
      metrics: { accuracy: 0.5 },
      confusion_matrix: { labels: ['a', 'b'], matrix: [[8, 0], [2, 0]] },
      feature_importance: null
    } as unknown as ModelEvaluationResponse
    expect(buildVerdict(weak)?.baseline).toContain('Does not beat')
    expect(buildVerdict({ metrics: null } as ModelEvaluationResponse)).toBeNull()
  })

  it('titles a model by name, falling back to its id', () => {
    expect(modelTitle({ model_name: 'Churn', model_id: 'm1' } as ModelEvaluationResponse)).toBe('Churn')
    expect(modelTitle({ model_name: null, model_id: 'm1' } as ModelEvaluationResponse)).toBe('m1')
  })
})
