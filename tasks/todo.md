# #795 — The model report

A generated, exportable account of why this model, for the user who has to defend it.

## What already exists (verified, with sources)

The report is an **assembly** job, not a computation job. Almost everything AC1 asks
for is already persisted:

| Section | Source |
|---|---|
| Winner, metrics, features, target, timings | `MLModel` — `algorithm`, `cv_score`, `test_score`, `metrics`, `feature_importance`, `n_samples_train`, `n_features`, `training_time` |
| **Algorithms tried with CV scores** | `TrainingJob.model_comparison` → `ModelComparisonEntry(algorithm, cv_score, test_score, training_time)`, written at `model_training.py:846-863`. Joins to `MLModel` on the shared `model_id` |
| **Why the winner won** | `TrainingJob.best_model_explanation`, built by `build_best_model_explanation(result.best_model, result.all_models, …)` |
| Algorithm recommendations | `TrainingJob.algorithm_recommendations` |
| Confusion matrix / ROC / PR | Computed from the persisted held-out arrays via `MetricsService.load_evaluation_artifacts` (the #79 path) |
| SHAP drivers | `MLModel.shap_values_path`, `shap_explainer_type`, `feature_importance` |
| Tuning | `tuning_strategy`, `tuning_results`, `improvement_from_tuning` |
| **Honest caveats** | `is_calibrated` + `calibration_score_is_insample` + `evaluation_on_calibration_set` (#201), and `early_stopped` + `stop_reason` + `algorithms_evaluated` (#101) — "the run stopped early, so not every candidate was tried" is a real caveat the data supports |

## What does NOT exist

1. **No baseline row.** Nothing trains a dummy/majority-class estimator — grep finds no
   `DummyClassifier`/`DummyRegressor` in the candidate set. AC1 asks for it.
2. **No persisted seed.** `random_state=42` is an engine default (`automl_engine.py:188`),
   never written to `MLModel`, so a run with an overridden seed cannot be reported truthfully.
3. **No library versions** captured at training time.

AC2 forbids inventing any of these. Each is either computed from something real, or the
report says "not recorded" — the #536 rule: a number a customer cannot trust is worse
than no number.

## Plan

1. **`app/services/model_report.py`** — assembles a `ModelReport` from the stored
   documents above. Pure function of what is stored; no model call, no AI.
2. **`GET /api/v1/ml/{model_id}/report`** — tenant-scoped, registered *before* the
   catch-all `/{model_id}`. Follows `_partial_evaluation_response`'s degradation: a
   model with no `TrainingJob` or no artifacts yields `partial=true` and the sections
   it can support, never a 500.
3. **Provenance on every section** — each carries where its numbers came from
   (`stored` / `computed_at_report_time` / `not_recorded`), so AC2 is structural rather
   than a promise in a docstring.
4. **Markdown rendering server-side** — the canonical artifact, testable in pytest and
   reusable by the API. `GET …/report.md` downloads it.
5. **Frontend `/models/[id]/report`** — renders the sections, reachable from the model
   views so `routeReachability.test.ts` passes without an allowlist entry. "Download
   Markdown" plus print-to-PDF via `@media print` CSS.
6. **Tests** — the classifier of each section's provenance, the degradation path on a
   model with no job, and a real end-to-end assembly against seeded documents.

## Open decisions (asked before building)

- The baseline row, the PDF mechanism, and whether generated prose is in scope at all.

## Known limitation

Pre-existing models trained before `model_comparison` was populated will report the
leaderboard as `not_recorded`. That is correct, not a bug — the data was never captured.
