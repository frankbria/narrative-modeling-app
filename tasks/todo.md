# Issue #77 — Hyperparameter Tuning (post-beta V2)

Add optional automated hyperparameter optimization (grid / random / Bayesian) to the
existing AutoML pipeline. Default-off; when on, the best params are applied to the
final model. Backend-only (the Traycer plan is backend-only too).

## Adapted plan (lean — collapses Traycer's 14 steps to 6)

### 1. Dependency: optuna (optional group)
- `apps/backend/pyproject.toml`: add `optuna>=4.1.0` to a new `[dependency-groups] tuning`
  group, included in `[tool.uv] default-groups` (mirrors the `interpretability`/shap
  lever from #204). Grid/random use sklearn (always present); Bayesian lazy-imports
  optuna so a slim image without it degrades to grid/random.

### 2. HyperparameterTuner service — ONE new file
- `app/services/model_training/hyperparameter_tuner.py`:
  - `TuningConfig` (strategy, time_budget, n_trials, cv_folds, scoring, n_jobs, random_state)
  - `TrialResult`, `TuningResult` dataclasses. `TuningResult` carries the **visualization
    data inline** (parameter_importance dict, optimization_history list of
    {trial, score, best_so_far}, improvement_over_default) — no separate viz module.
  - `tune(algorithm, X, y, base_estimator, config)` → routes to grid / random / bayesian.
  - Search spaces per algorithm (LogReg, RandomForest, XGBoost, LightGBM, GradientBoosting,
    SVM, KNN + regressors), **data-driven ranges** via the existing
    `build_data_profile` (comparison.py) — shrink n_estimators on large data, etc.
  - Parallel trials via `n_jobs`; early stopping via optuna `MedianPruner` + `timeout`
    (Bayesian). Grid/random honor n_trials/n_jobs; time_budget best-effort there.
  - Never raises into the pipeline — on failure returns `None` (keep training resilient,
    same contract as SHAP/calibration).

### 3. Integrate into AutoMLEngine
- `app/services/model_training/automl_engine.py`:
  - `__init__` gains `enable_tuning=False`, `tuning_config: TuningConfig | None`.
  - In `run()`, after feature engineering / before the training loop: when enabled, tune
    each candidate, apply best params to its estimator, emit a `TrainingEvent` per
    candidate, honor `cancel_check`.
  - `AutoMLResult` gains `tuning_results: dict[str, TuningResult] | None` and
    `tuning_strategy`/`improvement_from_tuning` summary fields.
  - Reuse existing `_get_scoring_metric`, thread-pool (`asyncio.to_thread`) pattern.

### 4. Persist on MLModel + wire API
- `app/models/ml_model.py`: add optional `tuning_strategy: str | None`,
  `tuning_time: float | None`, `improvement_from_tuning: float | None`,
  `tuning_results: dict | None` (the inline viz payload). All optional → pre-#77 degrade.
- `app/api/routes/model_training.py`: **no request-schema change** — read
  `enable_tuning` / `tuning_strategy` / `tuning_config` from the existing
  `training_config` dict. Build the engine with tuning, persist tuning fields in
  `model_metadata`. Add ONE route `GET /{model_id}/tuning-results` (registered before
  `/{model_id}`) returning the stored viz payload (partial/empty for untuned models,
  never 500). Skip the standalone `POST /models/tune` (YAGNI — not in the AC).

### 5. Module exports
- `app/services/model_training/__init__.py`: export `HyperparameterTuner`, `TuningConfig`,
  `TuningResult`.

### 6. Tests (2 files, not 4)
- `tests/test_model_training/test_hyperparameter_tuner.py`: search spaces + data-driven
  adaptation, all three strategies on a tiny dataset, improvement calc, early-stopping/
  pruner path, invalid algorithm/strategy, resilient-failure → None.
- `tests/test_api/test_hyperparameter_tuning.py` (+ extend `test_model_training.py`):
  train-with-tuning task path, tuning fields persisted, `GET /tuning-results` shape +
  untuned-model degradation.

## Acceptance criteria → coverage
- [ ] Three strategies (grid/random/bayesian-optuna) → step 2, unit tests
- [ ] Smart algorithm-specific, data-driven search spaces → step 2 (build_data_profile)
- [ ] Tuning config: time budget, n_trials, metric, CV folds → `TuningConfig`
- [ ] Parallel trials + early stopping for poor trials → n_jobs + optuna MedianPruner/timeout
- [ ] Results visualization: param importance, optimization history, improvement vs default
      → inline in `TuningResult`, exposed via `GET /{model_id}/tuning-results`
- [ ] Best params automatically applied to final model → step 3 (AutoMLEngine integration)

## Deviations from Traycer plan (with reasons)
- **Dropped** separate `DataProfile`/`DataProfiler` (Traycer #3) — reuse existing
  `build_data_profile` + `StatisticsEngine`. No duplicate.
- **Dropped** `tuning_visualization.py` models (#6) + `tuning_plots.py` utils (#7) +
  their test file (#13) — viz data folded into `TuningResult` (it's data, not plots;
  no frontend in scope). Optuna gives param importance natively.
- **Dropped** standalone `POST /models/tune` (#8) — not required by any AC; the AC is
  "applied to the final model" (integrated path).
- **Dropped** request-schema fields — reuse the existing `training_config: dict`.
- **Dropped** standalone `claudedocs/HYPERPARAMETER_TUNING.md` (#14) — document in
  CLAUDE.md per repo convention (Phase 12b docs-sync).
- optuna goes in an **optional** dependency group (not core) — matches the #204 shap
  Docker-lever pattern; grid/random work without it.

## Known beta limitations
- Tuning is opt-in and runs **before** calibration/SHAP (those still run on the tuned
  best model — consistent with current pipeline).
- time_budget is hard-enforced only for Bayesian (optuna `timeout`); grid/random honor
  n_trials + n_jobs, time_budget is best-effort.
- Per-instance frontend charts deferred — endpoint returns the data for a future UI.
