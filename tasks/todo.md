# Issue #78 — [P5.2] Model versioning and history tracking

## Architecture decision (verified against code)
- Real models = **`MLModel`** (`app/models/ml_model.py`, `/api/v1/ml/` routes, created at training in `model_storage.save_model`). The frontend `ModelService` + every live model page use `/ml/`.
- **`ModelConfig`** (`app/models/model.py`, `/models/` routes) already has `parent_model_id` + `deployment_config` + `mark_deployed()`, BUT it is a **dead/legacy surface** — never created by the real training flow. CodeRabbit's plan targets it (wrong). Traycer's plan creates brand-new `ModelVersion`/`ModelLineage` documents + 4 pages + React Flow (massively over-scoped).
- **Chosen: build versioning on `MLModel`.** No new documents, no new deps.

## Version family grouping (no retrain wiring needed)
- A **model family** = all `MLModel`s sharing `(user_id, dataset_id, name)`. Version number = chronological order within the family. Gives instant version history from existing data, zero migration.
- Add optional `parent_model_id` for explicit lineage; grouping-by-name is the primary mechanism.

## Backend
1. `MLModel`: add optional fields (all default → pre-#78 models degrade): `parent_model_id`, `is_production` (bool=False), `promoted_at`, `environment_metadata` (dict), `dataset_version_id`.
2. `app/services/model_versioning_service.py` (lean, mirrors `versioning_service.py`):
   - `list_versions(model_id, user_id)` → resolve family by (dataset_id,name), order by created_at, assign version_number, flag is_production.
   - `promote_to_production(model_id, user_id)` → set is_production on target, demote siblings, stamp promoted_at. **Rollback == promote an older version** (same op — documented, no separate endpoint).
   - `get_production_version(dataset_id, name, user_id)`.
3. Endpoints under `/ml/` (registered before dynamic `/{model_id}`):
   - `GET  /ml/{model_id}/versions` → version browser data (version#, status, algorithm, scores, dataset_version_id, features, env).
   - `POST /ml/{model_id}/promote` → promote to production (handles rollback).
   - **Comparison: reuse existing `POST /ml/compare` (#79).**
4. Training (`model_storage.save_model`): best-effort capture `environment_metadata` (python/sklearn/xgboost versions) + `dataset_version_id` (if available) + `parent_model_id` (current production in family) when creating `MLModel`.

## Frontend
1. `lib/services/model.ts`: add `getVersions(modelId)` + `promoteVersion(modelId)` + types.
2. `app/model/[id]/page.tsx`: add a **"Versions" tab** — table (version#, status badge, algorithm, CV/test scores, created, Promote button), per-row dataset version + feature set (= lineage), reuse `ModelComparisonTable` for side-by-side when 2+ selected. No new pages, no React Flow.

## Tests
- Backend: `tests/test_services/test_model_versioning_service.py`, `tests/test_api/test_model_versions.py` (list/promote/rollback/ownership/degradation).
- Frontend: extend model detail page test for the Versions tab + service mocks.

## Acceptance Criteria
- [ ] AC1 Automatic version creation per run with metadata (dataset version, feature set, algorithm, params, metrics, timestamps, environment)
- [ ] AC2 Version browser UI + side-by-side comparison
- [ ] AC3 Promote to production / rollback
- [ ] AC4 Model lineage visualization (which data/features produced which models)

## Skipped vs Traycer (add when needed)
Separate ModelVersion/ModelLineage documents, 4 new pages, React Flow dep, archive/retention policy, audit log, delete endpoint.
