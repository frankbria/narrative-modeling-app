/**
 * The model report (#795) — mirrors `app/schemas`-level shapes in
 * `apps/backend/app/services/model_report.py`. Change both together.
 *
 * `provenance` is the load-bearing field: it is what lets the UI distinguish
 * "measured and here is the number" from "never recorded", instead of rendering an
 * empty table that reads like a result.
 */
export type Provenance = 'stored' | 'computed_at_report_time' | 'not_recorded';

export interface ReportSection {
  provenance: Provenance;
  note?: string | null;
}

export interface LeaderboardRow {
  algorithm: string;
  cv_score: number | null;
  test_score: number | null;
  training_time: number | null;
  is_winner: boolean;
}

export interface ModelReport {
  model_id: string;
  model_name: string;
  problem_type: string;
  generated_at: string;
  trained_at: string | null;
  partial: boolean;
  dataset: ReportSection & {
    target_column: string;
    n_samples_train: number | null;
    n_features: number | null;
    feature_names: string[];
  };
  leaderboard: ReportSection & { rows: LeaderboardRow[] };
  winner: ReportSection & {
    algorithm: string;
    cv_score: number | null;
    test_score: number | null;
    explanation: string | null;
    metrics: Record<string, unknown>;
  };
  baseline: ReportSection & {
    strategy: string | null;
    score: number | null;
    metric: string | null;
  };
  drivers: ReportSection & {
    features: [string, number][];
    explainer_type: string | null;
  };
  reproducibility: ReportSection & {
    environment: Record<string, string>;
    seed: number | null;
    dataset_version_id: string | null;
    training_config: Record<string, unknown>;
  };
  caveats: string[];
}
