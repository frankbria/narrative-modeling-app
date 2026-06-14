# Issue #82 — Prediction Interfaces (single + batch)

**Source plan**: Traycer comment (heavily adapted — it misdescribes current state).
**Branch**: `feature/82-prediction-interfaces`

## Verified current state (Phase 2)
- `POST /api/v1/ml/{model_id}/predict` (`model_training.py:969`) — **already real inference**; loads model + persisted `FeatureEngineer`, `await transform()`, predicts, returns probabilities. AC2 (pipeline reuse) already satisfied here.
- `BatchPredictionService` (`services/batch_prediction.py`) — **broken**: `load_model(model.model_path)` wrong (sig is `load_model(model_id, user_id)` → tuple), `feature_engineer.transform()` not awaited (it's async), calls non-existent S3 methods (`upload_file`/`upload_file_content`/`download_file_content`), no summary stats.
- `production.py` predict — same `load_model` bug.
- Frontend `app/predict/page.tsx` — calls non-existent `/models/{id}/features` & `/models/{id}/predict/batch`, wrong base path (`/models/` vs `/ml/` + `/batch/`), shape mismatch.
- Form must use **raw** input columns (from `FeatureEngineer.numeric_features`/`categorical_features`), not engineered `MLModel.feature_names`.

## Backend
- [ ] **B1** `GET /api/v1/ml/{model_id}/features` → `{features:[{name,type,options?}], class_labels, problem_type, target_column}`. Derive from persisted FeatureEngineer (raw numeric→number, categorical→categorical w/ encoder categories as options); fallback to `MLModel.feature_names` when no FE. (AC1)
- [ ] **B2** Enhance `POST /ml/{model_id}/predict`: missing-feature validation → clear 422 (AC3); add backward-compatible `class_labels` + per-record `confidence` (max proba) to `PredictResponse`. (AC1/AC3)
- [ ] **B3** Fix `BatchPredictionService`: correct `load_model(model_id,user_id)` + tuple unpack; `await transform()`; real S3 via `upload_file_obj`/`download_file_obj`; compute `prediction_distribution` + `confidence_stats` into `job.results`; download returns predictions CSV. Surface stats in `BatchJobResponse.results`. (AC4)
- [ ] **B4** Fix identical `load_model` bug in `production.py` predict (bug ownership).
- [ ] **B5** Tests (TDD): features endpoint; predict validation + class_labels/confidence; batch service unit tests (mock S3/model); integration round-trip train→predict-single→predict-batch (enable skipped `integration/test_ml_workflow_e2e.py`). (AC6)

## Frontend
- [ ] **F1** `lib/services/model.ts` + `lib/types`: add `getModelFeatures`, batch methods (`createBatchJob`,`getBatchJobStatus`,`getBatchJobProgress`,`downloadBatchResults`,`cancelBatchJob`); fix paths to `/ml/` & `/batch/`; mirror backend schemas.
- [ ] **F2** Rewire `app/predict/page.tsx`: features→form w/ real-time validation; single predict via `/ml/{id}/predict` showing prediction + confidence + class probs; batch via `/batch/jobs` create→poll progress→summary stats→download CSV; add `data-testid`s; keep workflow stage completion. (AC1/AC3/AC4/AC5)
- [ ] **F3** Add `app/predict/[datasetId]/page.tsx` re-export (workflow nav pushes `/predict/{datasetId}`). (AC5)
- [ ] **F4** Jest: model.ts new methods; predict page.
- [ ] **F5** E2E: repair/enable `e2e/workflows/predict.spec.ts` @smoke (single + batch) with real backend seed. (AC5)

## Acceptance Criteria (gate)
- [ ] Single prediction: auto-generated form from feature schema, real-time validation, prediction value shown
- [ ] Input preprocessing reuses training-time pipeline (single + batch)
- [ ] Missing-feature handling with clear errors
- [ ] Batch: CSV upload → BatchPredictionService → progress → downloadable results CSV w/ summary stats
- [ ] `app/predict/page.tsx` wired to real endpoints; E2E predict workflow passes
- [ ] Integration test: train → predict single → predict batch round-trip
