import React from 'react';
import { render, screen, within, fireEvent } from '@testing-library/react';
import { TrainingScoreTable, verdictFor } from '@/components/training/TrainingScoreTable';
import { TrainingRunView } from '@/components/model-training/TrainingRunView';
import type { TrainingStatus } from '@/lib/services/model';

jest.mock('@/components/training/TrainingProgress', () => ({ TrainingProgress: () => null }));
jest.mock('@/components/training/TrainingLogs', () => ({ TrainingLogs: () => null }));
jest.mock('@/components/training/CancelTrainingButton', () => ({ CancelTrainingButton: () => null }));
jest.mock('@/components/model-training/ExcludedColumnsPanel', () => ({ ExcludedColumnsPanel: () => null }));

const rec = (algorithm_name: string, interpretability_score: number) => ({
  algorithm_name,
  priority: 10,
  expected_performance: '',
  training_time_estimate: '',
  interpretability_score,
  explanation: `${algorithm_name} explanation`,
  pros: [],
  cons: [],
});

const status = {
  model_id: 'm1',
  status: 'completed',
  progress: 1,
  completed_algorithms: 3,
  total_algorithms: 3,
  metrics: {},
  best_algorithm: 'Random Forest',
  model_comparison: [
    { algorithm: 'Random Forest', cv_score: 0.9, test_score: 0.85 },
    { algorithm: 'XGBoost', cv_score: 0.88, test_score: 0.9 },
    { algorithm: 'Logistic Regression', cv_score: 0.7, test_score: 0.7 },
  ],
  algorithm_recommendations: [
    rec('Random Forest', 5),
    rec('XGBoost', 8),
    rec('LightGBM', 2),
    rec('SVM', 2),
  ],
} as unknown as TrainingStatus;

describe('TrainingScoreTable (#1173)', () => {
  it('gives each model a one-line verdict that explains CV vs test', () => {
    const [best, testWinner, trailing] = status.model_comparison;
    expect(verdictFor(best, status)).toMatch(/Chosen for the steadiest cross-validation/);
    expect(verdictFor(testWinner, status)).toMatch(/highest on the test rows.*not chosen/);
    expect(verdictFor(trailing, status)).toBe('Trailed the chosen model.');
  });

  it('says so when the chosen model also tops the test rows', () => {
    const both = { ...status, best_algorithm: 'XGBoost' } as TrainingStatus;
    expect(verdictFor(both.model_comparison[1], both)).toBe('Chosen: best on both checks.');
  });

  it('explains the CV and test scores in tooltips', async () => {
    render(<TrainingScoreTable status={status} />);
    fireEvent.focus(screen.getByRole('button', { name: 'What is the CV score?' }));
    expect((await screen.findAllByText(/scored on each held-back part/)).length).toBeGreaterThan(0);
    fireEvent.focus(screen.getByRole('button', { name: 'What is the Test score?' }));
    expect((await screen.findAllByText(/kept aside before training/)).length).toBeGreaterThan(0);
  });
});

describe('TrainingRunView recommendations (#1173)', () => {
  it('lists only the algorithms that ran, in plain words', () => {
    render(<TrainingRunView modelId="m1" run={{ completed: status, keepColumns: [] } as never} />);
    const section = screen.getByText('Why these algorithms?').parentElement as HTMLElement;

    expect(within(section).getByText('Random Forest')).toBeInTheDocument();
    expect(within(section).getByText('XGBoost')).toBeInTheDocument();
    expect(within(section).queryByText('LightGBM')).not.toBeInTheDocument();
    expect(within(section).queryByText('SVM')).not.toBeInTheDocument();
    expect(within(section).getByText('Easy to explain')).toBeInTheDocument();
    expect(within(section).getByText('Somewhat easy to explain')).toBeInTheDocument();
    expect(section.textContent).not.toMatch(/Priority|\/10/);
  });
});
