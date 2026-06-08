# Issue #75 — Core AutoML Training Pipeline (P2.1)

## Reality check vs. the issue's "Current State (verified 2026-06-05)"

The issue (and the Traycer plan) describe `POST /ml/train` as a stub and the engine as missing.
**That is no longer true.** As of today the following already exist and are functional:

- `automl_engine.py` — trains real models (LogReg/RF/XGBoost/LightGBM/GB/SVM/KNN; LinReg/Ridge/RF/XGBoost/…), stratified split, k-fold CV, best-model selection, feature importance.
- `problem_detector.py`, `feature_engineer.py`, `algorithm_selector.py`, `explanation_service.py` (OpenAI + fallback) — all implemented.
- `model_storage.py` — joblib → S3 + `MLModel` metadata → MongoDB; load/list/delete.
- `POST /ml/train` (real background training), `GET /ml/`, `GET /ml/{id}`, `POST /ml/{id}/predict`, `DELETE`, `PUT deactivate` — all working.
- `imbalanced-learn`, `statsmodels`, `prophet` already in `pyproject.toml`.

**Therefore this is a focused gap-fill, not a greenfield build.** We target ONLY the unmet acceptance
criteria and explicitly do NOT add the Traycer over-scope (WebSocket, ARIMA/Prophet, SMOTE, training modes).

## Genuine remaining gaps (the real work)

1. No training **job/status tracking** — `train_model_task` is fire-and-forget; failures are silently re-raised. No status endpoint (the response literally says "Check status endpoint" but none exists).
2. **Model comparison** computed (`all_models`) but discarded — only best model saved; not exposed via API; no AI best-model explanation surfaced.
3. Engine has **no basic class-imbalance handling**, and does not wire in the existing `AlgorithmSelector` recommendations or `ExplanationService`.
4. **Frontend `app/model/page.tsx` is broken**: posts to `/models/train` (wrong; should be `/ml/train`), wrong payload shape, polls non-existent `/models/{id}/status`, fake simulated progress.
5. No tests for the new status/job layer or the frontend wiring.

## Plan (TDD throughout)

> **Scope decisions (Phase 4):** Gap-fill only. **Job cancellation is OUT** (deferred — Known Limitation
> for AC4's "cancellable" clause). Explanations use `ExplanationService`'s **deterministic rule-based
> fallback** (no OpenAI runtime calls/API key required). Also post a correction comment on issue #75.

### Backend
- [ ] **B1. `TrainingJob` model** (`app/models/training_job.py`, register in `app/models/registry.py`), keyed by `model_id`: `user_id`, `dataset_id`, `target_column`, `status` (pending/running/completed/failed), `progress` (0–1 + current/total/current_algorithm), `algorithm_recommendations`, `model_comparison` (list of {algorithm, cv_score, test_score, training_time}), `best_model_id`, `best_model_explanation`, `error`, timestamps. → unit tests.
- [ ] **B2. Engine: basic class-imbalance + surface recommendations/explanation.** Add `class_weight="balanced"` for supporting classifiers when imbalance ratio > 2 (lightweight "basic" handling, no resampling). Surface `AlgorithmSelector` recommendations + `ExplanationService` best-model explanation (**rule-based fallback path**, no API key needed) and the full `all_models` comparison in the result. → engine tests.
- [ ] **B3. Refactor `train_model_task`**: create/update `TrainingJob` (status=running), update `progress` via per-model callback, persist comparison + best explanation on success (completed), set status=failed + `error` on exception (no more silent re-raise).
- [ ] **B4. Endpoint**: `GET /ml/{model_id}/status` → {status, progress, metrics, comparison, best_model_id, explanation, error}. Create the `pending` `TrainingJob` synchronously in `train_model` before returning. → API tests (running/completed/failed).
- [ ] **B5. Integration test** (service-gated): POST `/ml/train` on a sample CSV → poll status → completed with persisted model + comparison.

### Frontend
- [ ] **F1. Fix `app/model/page.tsx`**: route through `ModelService`; POST `/ml/train` with correct payload; poll `/ml/{model_id}/status`; drive real progress from `job.progress`; show comparison + best model on completion.
- [ ] **F2. `ModelService`**: add `getTrainingStatus(modelId)`, align types. → jest tests (service + page happy/failure paths, mocked fetch).

### Docs / housekeeping
- [ ] **D1.** Update `CLAUDE.md` "Current Stage" + a short AutoML status/endpoints note; OpenAPI reflects new routes automatically.
- [ ] **D2.** Post a comment on issue #75 correcting the outdated "Current State" and listing done-vs-remaining.

## Explicitly deferred (out of scope per the issue itself)
- Real-time WebSocket UI → **#76 (P2.2)**
- Time-series ARIMA/Prophet → post-beta
- SMOTE/resampling beyond `class_weight` → post-beta
- Quick/Comprehensive training modes → **#101 (P5.9)**
- Hyperparameter tuning / GridSearch → **#77 (P5.1)**

## Acceptance criteria coverage
- AC1 problem-type detection — already ✅ (engine uses `problem_detector`)
- AC2 algorithm recommendation + plain-language explanation — **B2** (wire existing selector/explanation)
- AC3 split / stratified / k-fold / basic imbalance — split+stratify+CV ✅; imbalance via **B2**
- AC4 async + progress queryable — **B1/B3/B4**; **cancellable = deferred (Known Limitation)**
- AC5 artifacts→S3, metadata→MongoDB — already ✅
- AC6 model comparison + best-model selection + explanation — **B2/B3/B4**
- AC7 `POST /ml/train` trains ✅; `GET` returns real status/results — **B4**
- AC8 frontend wired to real endpoints — **F1/F2**
- AC9 TDD >85% on new code; integration test on sample CSV; train workflow test — tests across B/F
