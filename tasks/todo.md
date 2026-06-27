# Issue #101 — Quick / Comprehensive Training Modes

## What already exists (Traycer plan is stale — do NOT rebuild)
- Per-algorithm progress, current_stage, elapsed/estimated-remaining time, polling UI, logs, cancel — all shipped in #76.
- Hyperparameter tuning (`enable_tuning`/`tuning_config`, bayesian + budgets, optuna early-stop pruner) — shipped in #77.
- `progress_callback`/`event_callback`/`cancel_check`, `max_models`, candidate model catalog — exist in `AutoMLEngine`.
- `training_config` dict passthrough on `TrainModelRequest` (no schema change needed — modes ride in it, like #77 did with tuning).

## Real gaps (AC ↔ work)
1. AC1/AC2: mode → engine config mapping (quick: 3 algos, no tuning, 300s; comprehensive: 10+ algos, tuning, 1800s).
2. AC2 "10+ algorithms": catalog tops out at ~7. Add ~4 always-on sklearn algos (ExtraTrees, AdaBoost, DecisionTree, GaussianNB / Lasso+ElasticNet) → comprehensive lists 10+.
3. AC4: `time_limit` is accepted by the engine but **never enforced**, and the route never passes it. Add wall-clock enforcement + early-stop-on-good-score in the candidate loop.
4. AC3: dataset-based recommendation (small endpoint + heuristic) + frontend mode selector with trade-off copy.
5. AC5: time-remaining progress — already done (#76). No work.

## Plan (lean)

### Backend
- **New** `app/services/model_training/training_mode.py` (pure): `TrainingMode` enum; `resolve_mode_config(mode, overrides)` -> engine kwargs (max_models, time_limit, enable_tuning, tuning_strategy, early_stop_score) with explicit overrides winning; `recommend_mode(n_rows, n_features)` -> {mode, reason}.
- **Edit** `automl_engine.py`:
  - `__init__`: add `early_stop_score: float | None = None`.
  - Candidate loop: enforce `time_limit` (break after >=1 model when elapsed >= budget) and early-stop when `cv_score >= early_stop_score`. Record `early_stopped`/`stop_reason`/`algorithms_evaluated`.
  - `_get_candidate_models`: append ~4 always-on algos so full catalog >=10. Quick (first 3) unaffected.
  - `AutoMLResult`: add `training_mode`, `early_stopped=False`, `stop_reason=None`, `algorithms_evaluated=None`.
- **Edit** `model_training.py` train route: resolve `training_config["training_mode"]` via `resolve_mode_config` (absent -> today's behaviour unchanged), pass `time_limit` + `early_stop_score` to engine, stash mode/stop_reason in `training_config` (persisted on MLModel — **no new MLModel field**, avoids mock-fixture gotcha). New `GET /ml/datasets/{dataset_id}/mode-recommendation` (owner-scoped, 404 foreign).

### Frontend
- **Edit** `lib/services/model.ts`: add `training_mode?` to `training_config` type; add `getModeRecommendation`.
- **New** `components/TrainingModeSelector.tsx`: two cards (Quick/Comprehensive) + trade-off copy + recommendation banner.
- **Edit** `app/model/page.tsx`: render selector, fetch recommendation on load, send `training_config.training_mode`.

### Tests (TDD)
- BE: `test_training_mode.py`; extend automl engine test (time-budget break, early-stop, new algos count >=10); route test (mode wiring + recommendation endpoint 200/404-foreign).
- FE: `TrainingModeSelector.test.tsx`; extend `model.test.ts` (getModeRecommendation); model page mode wiring.

## Explicitly NOT doing (vs Traycer)
- No `dataset_profiler.py`, no `training_constants.py`, no new MLModel DB fields, no new MLModel migration.
- No new `GET /ml/train/{id}/progress` endpoint, no Redis progress cache (status endpoint + polling already exist).
- No `RecommendationBanner.tsx`/`TrainingProgressDialog.tsx`/rework of `ModelTrainingButton.tsx` (unused).
- No top-level `TrainModelRequest.training_mode` schema field (rides in training_config).
