/**
 * The report page's one real guarantee (#795): a section the platform never
 * recorded renders as an explicit "Not recorded" with its reason — never as an
 * empty table, which would read as "nothing else was tried".
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ModelReportPage from '@/app/model/[id]/report/page';
import { modelService } from '@/lib/services/model';
import type { ModelReport } from '@/lib/types/modelReport';

jest.mock('next/navigation', () => ({
  useParams: () => ({ id: 'm-1' }),
}));

jest.mock('@/lib/services/model', () => ({
  modelService: { getModelReport: jest.fn(), getModelReportMarkdown: jest.fn() },
}));

const base: ModelReport = {
  model_id: 'm-1',
  model_name: 'Churn model',
  problem_type: 'classification',
  generated_at: '2026-09-21T00:00:00Z',
  trained_at: '2026-09-20T00:00:00Z',
  partial: true,
  dataset: { provenance: 'stored', target_column: 'churned', n_samples_train: 800, n_features: 2, feature_names: [] },
  leaderboard: { provenance: 'not_recorded', note: 'No training job is recorded for this model.', rows: [] },
  winner: { provenance: 'stored', algorithm: 'Random Forest', cv_score: 0.87, test_score: 0.85, explanation: 'It won on CV.', metrics: {} },
  baseline: { provenance: 'computed_at_report_time', strategy: 'majority_class', score: 0.7, metric: 'accuracy', note: 'Computed at report time.' },
  drivers: { provenance: 'not_recorded', note: 'No SHAP or native importance stored.', features: [], explainer_type: null },
  reproducibility: { provenance: 'stored', environment: { sklearn: '1.5.0' }, seed: null, dataset_version_id: null, training_config: {}, note: null },
  caveats: ['This model does not record which dataset version it trained on.'],
};

describe('ModelReportPage', () => {
  beforeEach(() => {
    (modelService.getModelReport as jest.Mock).mockResolvedValue(base);
  });

  it('shows an unrecorded leaderboard as Not recorded, with the reason', async () => {
    render(<ModelReportPage />);

    await waitFor(() => expect(screen.getAllByText('Not recorded').length).toBeGreaterThan(0));
    expect(screen.getByText(/No training job is recorded/)).toBeInTheDocument();
    // The table headers must NOT render — an empty table is the failure mode.
    expect(screen.queryByText('CV score')).not.toBeInTheDocument();
  });

  it('shows the computed baseline and says it was computed at report time', async () => {
    render(<ModelReportPage />);

    await waitFor(() => expect(screen.getByText(/majority_class/)).toBeInTheDocument());
    expect(screen.getByText(/Computed at report time/)).toBeInTheDocument();
  });

  it('renders the leaderboard when it was recorded', async () => {
    (modelService.getModelReport as jest.Mock).mockResolvedValue({
      ...base,
      leaderboard: {
        provenance: 'stored',
        note: null,
        rows: [
          { algorithm: 'Random Forest', cv_score: 0.87, test_score: 0.85, training_time: 1, is_winner: true },
          { algorithm: 'Logistic Regression', cv_score: 0.79, test_score: 0.78, training_time: 1, is_winner: false },
        ],
      },
    });

    render(<ModelReportPage />);

    await waitFor(() => expect(screen.getByText('Logistic Regression')).toBeInTheDocument());
    expect(screen.getByText('winner')).toBeInTheDocument();
  });

  it('shows an error when the Markdown download fails, instead of doing nothing', async () => {
    const user = userEvent.setup();
    (modelService.getModelReportMarkdown as jest.Mock).mockRejectedValue(
      new Error('HTTP 401')
    );

    render(<ModelReportPage />);
    await waitFor(() => expect(screen.getByText('Download Markdown')).toBeInTheDocument());
    await user.click(screen.getByText('Download Markdown'));

    expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 401');
  });

  it('does not label the winner Not recorded when only the explanation is missing', async () => {
    (modelService.getModelReport as jest.Mock).mockResolvedValue({
      ...base,
      winner: { ...base.winner, explanation: null, note: 'No stored explanation.' },
    });

    render(<ModelReportPage />);

    await waitFor(() => expect(screen.getByText('No stored explanation.')).toBeInTheDocument());
    // Exactly the two genuinely-absent sections (leaderboard, drivers) carry the
    // label. Scoped to <p> so the intro banner's own <strong>Not recorded</strong>
    // — which explains what the label means — is not counted as a section.
    expect(screen.getAllByText('Not recorded', { selector: 'p' })).toHaveLength(2);
  });

  it('shows the truncation note, which the PDF export depends on', async () => {
    (modelService.getModelReport as jest.Mock).mockResolvedValue({
      ...base,
      drivers: {
        provenance: 'stored',
        note: 'Showing the top 20 of 35 features by magnitude.',
        features: [['tenure', 0.9]],
        explainer_type: 'tree',
      },
    });

    render(<ModelReportPage />);

    await waitFor(() =>
      expect(screen.getByText(/top 20 of 35 features/)).toBeInTheDocument()
    );
  });

  it('surfaces caveats', async () => {
    render(<ModelReportPage />);

    await waitFor(() =>
      expect(screen.getByText(/does not record which dataset version/)).toBeInTheDocument()
    );
  });
});
