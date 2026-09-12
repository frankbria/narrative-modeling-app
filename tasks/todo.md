# Issue #500 — [P1.10] [security] Caller-supplied training and tuning config is passed through unbounded

Plan source: self-authored (no plan on the issue). Approved autonomously — no architectural fork.

## Findings
- `TrainModelRequest.training_config` / `feature_config` are `dict[str, Any]`; the task feeds them to `AutoMLEngine`, `TuningConfig(**raw)` and `FeatureEngineeringConfig(**raw)` unvalidated.
- Caller-reachable cost knobs: `max_models`, `cv_folds`, `time_limit`, `test_size`, `early_stop_score`, `enable_tuning`, `tuning_strategy`, `tuning_config.{n_trials,time_budget,cv_folds,n_jobs,strategy,scoring,random_state}`, `feature_config.max_features` (+ bools/strings).
- Estimator hyperparameters (`n_estimators`, `max_depth`) are NOT caller-reachable: the search space is server-defined in `hyperparameter_tuner.py` (ParamSpec ceilings 400 / 30, tightened further by dataset size).
- The engine's `time_limit` is soft (checked between candidates, after the tuning phase). Nothing kills a run.
- Frontend sends `training_mode`, `cv_folds` (3–10), `max_models` (1–10), `test_size` (0.1–0.4) — all must stay valid on FREE.

## Design
1. `app/billing/plans.py`: `TrainingCeilings` (frozen dataclass) + `TRAINING_CEILINGS[tier]` + `training_ceilings_for(tier)` — max_models, cv_folds, time_limit_seconds, wall_clock_seconds (hard kill), tuning_trials, tuning_time_budget_seconds, max_features. FREE ceilings ≥ the `comprehensive` preset so modes stay usable on every tier.
2. `app/api/routes/model_training.py`: typed `TrainingConfigRequest` / `TuningConfigRequest` / `FeatureConfigRequest` (`extra="forbid"`, static lower bounds, strategy Literal) replace the dicts → unknown or malformed knobs 422 at parse time. Route resolves the tier (`metering.effective_tier_for`) and rejects anything over the tier ceiling with 422 whose detail names the knob, the value and the limit. No clamping.
3. Task: `asyncio.wait_for(engine.run(...), timeout=wall_clock_seconds)`; on `TimeoutError` the job is marked FAILED with "exceeded the Ns wall-clock limit for your plan". Route passes the tier's wall clock; default (no arg) falls back to FREE's — fail closed, no DB lookup in the task.
4. Tests: 422 for over-ceiling / unknown key / malformed; 200 within bounds; timeout marks FAILED; ceilings monotonic and presets fit FREE.
5. Docs: CLAUDE.md training-config bullet; lessons post-merge.

## Steps
- [ ] RED tests
- [ ] plans.py ceilings
- [ ] request models + route ceiling check + wall clock in task
- [ ] gate (pytest/diff-cover/ruff/mypy/codex) → PR → demo → CI → merge
