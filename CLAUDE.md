# CLAUDE.md - Project Conventions and Guidelines

## Project Overview
This is a Narrative Modeling App - an AI-guided platform that democratizes machine learning by helping non-expert analysts build, explore, and deploy models without writing code.

## Key Architecture Components

### Frontend (Next.js)
- Located in `apps/frontend/`
- Uses App Router pattern
- TypeScript with strict typing
- Tailwind CSS for styling
- NextAuth v5 for authentication (Google, GitHub providers)

### Backend (FastAPI)
- Located in `apps/backend/`
- FastAPI with async/await patterns
- MongoDB with Beanie ODM
- AWS S3 for file storage
- Background tasks for AI processing

#### AutoML training (issue #75)
- `POST /api/v1/ml/train` runs real AutoML training in a FastAPI `BackgroundTasks` job and creates a `TrainingJob` (`app/models/training_job.py`, registered in `app/models/registry.py`).
- `GET /api/v1/ml/{model_id}/status` returns live progress, the ranked model comparison, rule-based algorithm recommendations, and a plain-language best-model explanation; failures are recorded on the job (status `failed` + `error`) instead of being silently re-raised.
- The engine (`app/services/model_training/automl_engine.py`) applies basic class-imbalance handling (`class_weight="balanced"` when the majority/minority ratio exceeds 2:1) and accepts a `progress_callback`. Result summaries live in `app/services/model_training/comparison.py`.
- **Issue #76 (polling-based progress monitoring):** `GET /api/v1/ml/jobs` (list jobs, status filter + pagination), `GET /api/v1/ml/{model_id}/logs` (level filter + pagination), `POST /api/v1/ml/{model_id}/cancel` (409 on terminal state); `GET /api/v1/ml/{model_id}/status` extended with `current_stage`, `elapsed_seconds`, `estimated_remaining_seconds`, `cancellation_requested`; `TrainingJob` gains `logs` (structured `TrainingLogEntry`), `cancellation_requested`, and stage/timing fields; `AutoMLEngine` supports cooperative cancellation via `cancel_check` callback and optional `event_callback`; frontend has `TrainingProgress`, `TrainingLogs`, `CancelTrainingButton` components and a `/training` dashboard page. WebSocket/SSE and Redis progress caching deliberately not implemented (polling chosen for beta).
- **Out of scope / deferred:** time-series (ARIMA/Prophet), SMOTE resampling, Quick/Comprehensive training modes (#101), hyperparameter tuning (#77).
- **Issue #79 (model evaluation dashboard — backend):** the API contract lives in `app/schemas/evaluation.py` (mirrored by `apps/frontend/lib/types/evaluation.ts` — change both together). Training persists the best model's held-out arrays (`y_test`/`y_pred`/`y_proba`/original-space `class_labels`, captured on `AutoMLResult`) as JSON to S3 at `models/{user_id}/{model_id}/evaluation_data.json` (`build_evaluation_payload` in `app/services/model_storage.py`; upload is best-effort and never fails training; `MLModel.evaluation_data_path` records it, `None` for pre-#79 models). `GET /api/v1/ml/{model_id}/evaluation` computes detailed metrics, confusion matrix, and ROC/PR curves (≤200 points/curve) via `app/services/metrics_service.py`, plus a plain-language AI report card from `app/services/evaluation_explanation_service.py` (OpenAI JSON mode behind the shared circuit breaker, deterministic rule-based fallback when no API key — endpoint works fully without one); models without artifacts degrade to `partial=true` with stored scalar metrics (never 500). `POST /api/v1/ml/compare` compares 2–5 owned models (404 unknown/foreign, 400 mixed dataset or problem type), registered before the `/{model_id}` routes like `GET /jobs`.
- **Issue #79 (frontend):** `app/evaluate/page.tsx` is a full dashboard (Tabs: Overview with metric cards + AI "Model Report Card", Confusion Matrix with cell-click drill-down, ROC/PR Curves, Compare with 2–5 model selector) backed by `ModelService.getEvaluation`/`compareModels`; components `ConfusionMatrixChart` (SVG heatmap, keyboard-accessible), `ROCCurveChart`/`PRCurveChart` (Recharts), `ModelComparisonTable` (direction-aware best-per-metric highlighting via `isLowerBetter`). CSV/PDF export in `lib/utils/export.ts` (jspdf@4 + jspdf-autotable@5, pure `build*` functions for testability). `app/evaluate/[datasetId]/page.tsx` re-exports the page because workflow navigation pushes `/evaluate/{datasetId}`. Demo-found fixes: legacy `/api/v1/upload/` now sets `UserData.file_type` (training requires it). E2E spec `e2e/workflows/evaluate.spec.ts` passes once the e2e storage prerequisites are met (#191, fixed).
- **Issue #191 (e2e upload fixture / test storage):** the "drifted fixture" was actually missing S3-compatible storage — `test-e2e.sh` now auto-detects LocalStack on :4566 (start it via `docker compose -f apps/backend/docker-compose.test.yml up -d localstack`; the LocalStack volume must mount at `/var/lib/localstack`, not the legacy `/tmp/localstack`, which crashes 3.x), and `seed_e2e_data.py` creates `test-bucket` on the configured endpoint (never real AWS). The `uploadTestDataset` fixture fails with step-level diagnostics (step name, URL, visible `upload-error` text); `upload-fixture-smoke.spec.ts` (@smoke) validates the fixture in isolation — run it first when upload UI changes. Upload error states carry `data-testid="upload-error"` / `upload-error-message`. See `apps/frontend/e2e/README.md` → Prerequisites.
- **Issue #87 (backend workflow persistence):** workflow stage/progress state persists to MongoDB per `(user_id, dataset_id)` — `WorkflowState` in `app/models/workflow.py` (unique compound index; embedded `state_history` append log of full snapshots, capped at the latest 50; `stage_data` deep-copied into snapshots), `WorkflowService` (`create/get_by_dataset/update_workflow/get_history`; concurrent-create race → `ConflictError`, note Beanie's `save()` surfaces the unique-index violation as `RevisionIdWasChanged`), routes `POST/GET/PUT /api/v1/workflows/{dataset_id}` + `GET .../history` (wrong user → 404 by user-scoped lookup, duplicate POST → 409, `stage_data` serialized size capped at 256KB → 422). Frontend `WorkflowContext` loads backend state during hydration **before** `isHydrated` flips (dataset id from prop, localStorage cache, or the stage-page URL — direct `/explore/{id}` loads recover after a cleared cache), auto-saves at stage boundaries (completion *and* `currentStage` change), POST→PUT with 409 retry, skips identical-state saves (`lastSavedRef`), and falls back to localStorage when the backend is unreachable. Concurrent PUTs are last-writer-wins (accepted beta limitation; multi-device sync deferred with #91).
- **Issue #82 (prediction interfaces — single + batch):** `POST /api/v1/ml/{model_id}/predict` already did real inference (not a stub — the Traycer plan was stale); it now validates required raw features (clear **422** listing the missing ones), returns backward-compatible per-record `confidence` (max class proba) + `class_labels`, caps `data` at `MAX_PREDICT_RECORDS` (1000), and maps a sklearn `ValueError`/`KeyError` (e.g. unknown category) to a 422 instead of a 500. New `GET /api/v1/ml/{model_id}/features` returns the **raw input schema** for the auto-generated form (numeric vs categorical-with-options, class labels, problem type) derived from the persisted `FeatureEngineer.numeric_features`/`categorical_features` (NOT the engineered `feature_names`), with a `feature_names` fallback when artifacts can't load. The previously-broken `BatchPredictionService` is fixed: correct `load_model(model_id, user_id)` tuple call, **awaited** async `feature_engineer.transform`, real S3 (`upload_file_obj`/`download_file_obj`), cumulative counts, summary stats (`prediction_distribution` + `confidence_stats` in `job.results`/`BatchJobResponse.results`), clean tabular results CSV, and background tasks retained in `self._background_tasks` + observed via `add_done_callback` (`_spawn_processing`); tests use `create_batch_prediction_job(auto_start=False)` for determinism. Same `load_model` bug fixed in `production.py`. **Boolean-column fix:** pandas parses `true`/`false` to `bool` dtype, which fell through both FE feature lists — `FeatureEngineer._coerce_booleans` now casts bool→str at fit *and* transform so such columns are encoded as categoricals (`"True"`/`"False"`) and surfaced in the form. Frontend: `model.ts` adds `getModelFeatures` + batch methods (`createBatchJob`/`getBatchJob`/`getBatchJobProgress`/`downloadBatchResults`/`cancelBatchJob`); `app/predict/page.tsx` is wired to these (auto-generated form + real-time validation; single result shows value/confidence/per-class probs; batch = create→poll progress→summary→download CSV) and **gates its redirect on `isHydrated`** (mirrors evaluate) to avoid a premature bounce to `/upload`; `app/predict/[datasetId]/page.tsx` re-exports the page. AC6 round-trip lives in `tests/integration/test_prediction_roundtrip.py` (real Mongo + LocalStack); E2E `e2e/workflows/predict.spec.ts` drives single + batch through the wired UI (note the shared `PredictPage.predict()` selector matches "Single **Predict**ion" — click `data-testid="make-prediction"` directly).
- **Issue #83 (confidence scoring + per-prediction explainability):** builds on #82. **No SHAP** — P3.3 (#80) is still open, and the AC says "fall back to model-native importance," so SHAP is deferred to #80. Two new stateless services: `ConfidenceService` (`app/services/confidence_service.py` — `confidence_from_proba`, `is_low_confidence` at `DEFAULT_LOW_CONFIDENCE_THRESHOLD=0.7`, `calibrate_classifier` via `CalibratedClassifierCV(FrozenEstimator(...))` (replaces deprecated `cv="prefit"`; sigmoid <1000 cal samples else isotonic; Brier/log-loss score), `residual_std`/`regression_interval` for ±1.96σ intervals) and `PredictionExplainerService` (`app/services/prediction_explainer_service.py` — per-row `coef·x` for linear (`linear_coefficients`), global `feature_importances_` fallback for trees (`tree_importance`), stored `MLModel.feature_importance` fallback (`stored_importance`); unwraps Calibrated/Frozen/Pipeline wrappers; **never raises** — returns `None` when unexplainable). `PredictionEnricher` (`app/services/prediction_enrichment.py`) composes both for the endpoints. **Training-time calibration** (`AutoMLEngine._calibrate_best_model`): the best classifier is calibrated on the held-out split and **swapped in place** so the deployed model yields calibrated probabilities — done **before** `_capture_evaluation_arrays` so the #79 dashboard describes the deployed model (calibration is fit on that same held-out split — documented beta limitation); `feature_importance` is extracted from the **raw** estimator first (the calibrated wrapper hides `coef_`/`feature_importances_`); regression stores `residual_std`. New optional `MLModel` fields (`is_calibrated`, `calibration_method`, `calibration_score`, `residual_std`) + schemas (`PredictionConfidence`/`FeatureContribution`/`PredictionExplanation` in `app/schemas/model.py`) — all default/optional so pre-#83 models degrade (raw max-proba confidence, `is_calibrated=False`, no intervals). Endpoints: training `predict` + `production.py` predict (previously had **no** confidence) + batch all compute proba whenever `predict_proba` exists (drives confidence + `low_confidence` flags even when full vectors aren't requested), gate `explanations` behind `include_explanations` (default off), and add regression `prediction_intervals`; batch adds per-row `low_confidence`, summary `low_confidence_count`, and `low_confidence`/`prediction_interval`/`explanation` CSV columns (confidence column was already #82). Frontend `model.ts` adds the new response fields + `FeatureContribution`/`PredictionExplanation` types; `app/predict/page.tsx` sends `include_explanations: true` for single predictions and renders a low-confidence warning, regression interval, and a "What drove this prediction" feature-contribution panel, plus a batch low-confidence count. Tests: `tests/test_services/test_confidence_service.py`, `test_prediction_explainer_service.py`, extended `test_batch_prediction.py` + `test_api/test_model_training.py` + the `test_prediction_roundtrip.py` integration round-trip (note: mocks of `MLModel` must set the four new fields or FastAPI's `response_model=MLModel` validation rejects the bare MagicMock).

### MCP Server
- Located in `apps/mcp/`
- FastMCP framework
- Tools for advanced data processing and modeling

## Testing Commands
- Backend (full suite): `cd apps/backend && uv run pytest` — requires MongoDB on localhost:27017; optional test Redis (6380) and LocalStack (4566) via `docker compose -f docker-compose.test.yml up -d` (tests skip with a reason when these are absent)
- Backend (service-free tests, no services): `cd apps/backend && PYTHONPATH=. uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ tests/test_models/ tests/test_auth/ tests/test_model_training/test_problem_detector.py tests/test_model_training/test_feature_engineer.py -m "not integration and not performance" -v`
- Frontend (unit tests): `cd apps/frontend && npm test`
- Frontend (type check): `cd apps/frontend && npm run type-check`
- MCP: `cd apps/mcp && uv run pytest tests/` (scope to `tests/`; the vendored `fastmcp/tests/` is the upstream library's own suite)

## Test Suite Status
- Backend: full suite green locally (~1,460 passed, ~39 service-gated/documented skips) ✅ — fixed in issue #160
  - During pytest runs the app lifespan uses the **test** database (never production `MONGODB_URI`)
  - Canonical Beanie model registry: `app/models/registry.py` (shared by app lifespan and `setup_database` fixture)
- CI: `ci.yml` is the primary PR gate (issue #150). It runs backend (ruff **blocking**, mypy **advisory**, service-free pytest), frontend (eslint, `tsc --noEmit`, `next build`, jest), MCP pytest, and backend integration tests (MongoDB **service container** on 27017 + Redis/LocalStack from `docker-compose.test.yml`). A single aggregate `CI Success` status is the required check for branch protection on `main`. The old `unit-tests.yml` was consolidated into `ci.yml`; `integration-tests.yml`/`e2e-tests.yml` remain manual (`workflow_dispatch`). `deploy.yml` deploys `main` to staging over SSH (secret-gated; see workflow header) — service requirements documented in each workflow header. `claude-code-review.yml` posts an **advisory** Claude review on each PR — hardened after the PR #187 runaway incident with a 10-min job timeout, `--max-turns 20` via `claude_args` (the action has no `max_turns` input), a per-PR concurrency group with cancel-in-progress, and a prompt that mandates a single consolidated comment (issue #188); `claude.yml` answers `@claude` mentions (30-min timeout, `--max-turns 50`)
- Frontend: Jest tests configured; TypeScript errors eliminated (#166); `npm run type-check` (`tsc --noEmit`) enforced in CI
- MCP: Pytest suite available
- See `apps/backend/docs/TEST_INFRASTRUCTURE.md` for the testing guide and the **Service Prerequisites** table
- See `apps/backend/docs/TDD_GUIDE.md` for TDD methodology

## Environment Variables
- Frontend: `.env.local`
- Backend: `.env`
- Required: AWS credentials, MongoDB URI, OpenAI API key, NextAuth secret
- Development: Set `SKIP_AUTH=true` to bypass authentication — only honored when `ENVIRONMENT` is explicitly `development`/`test`; backend startup fails hard otherwise (#149)

## Data Flow
1. User uploads file → Backend processes → Stores in S3
2. Metadata saved to MongoDB
3. Background AI analysis triggered
4. Frontend displays results with visualizations

## Current Stage
**Sprint 11 Complete** ✅ | **Sprint 12 Ready** 🟢

See `apps/backend/docs/SPRINTS.md` for detailed sprint history.

## MCP Server Setup
This project includes a custom MCP server for advanced data processing. To use it with Claude Desktop:

```json
{
  "mcpServers": {
    "narrative-modeling": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/narrative-modeling-app/apps/mcp",
        "run",
        "mcp",
        "dev",
        "server.py"
      ]
    }
  }
}
```

Add this to `~/.config/claude/claude_desktop_config.json` and restart Claude Desktop. Replace `/path/to/narrative-modeling-app` with your actual project path.

Additional recommended MCP servers:
- **Context7** - For library documentation lookup
- **Serena** - For project memory and session management

## Documentation Requirements

**ALL implementation documentation MUST remain synchronized with the codebase**:

1. **API Documentation**:
   - Update OpenAPI specifications when endpoints change
   - Document all request/response schemas
   - Include example requests and responses
   - Document error responses and status codes

2. **Code Documentation**:
   - Python: Docstrings for all public functions, classes, and modules
   - TypeScript: JSDoc comments for complex functions and components
   - Update inline comments when implementation changes
   - Remove outdated comments immediately

3. **Implementation Documentation**:
   - Update relevant sections in this CLAUDE.md file
   - Keep architecture diagrams current
   - Update configuration examples when defaults change
   - Document breaking changes prominently

4. **README Updates**:
   - Keep feature lists current
   - Update setup instructions when dependencies change
   - Maintain accurate command examples
   - Update version compatibility information

5. **CLAUDE.md Maintenance**:
   - Add new patterns to relevant sections
   - Update "Current Stage" when workflow changes
   - Keep command examples accurate and tested
   - Document new testing patterns or quality gates

## Automated Workflow Configuration

### Traycer AI Integration

When receiving Traycer AI prompts:
1. Save prompt to: `prompts/<issue-id>.txt`
2. Run: `./scripts/traycer-workflow.sh <issue-id>`
3. Monitor: `npx claude-flow@alpha status --watch`
4. Only intervene if blocker queue triggered

### Quality Gates

Before PR creation:
- ✅ All tests must pass (100% requirement)
- ✅ Test coverage >85%
- ✅ Linting (ruff/eslint) passes
- ✅ Type checking (mypy/tsc) passes
- ✅ No TODO/FIXME/NotImplemented markers
- ✅ Security scan (OWASP patterns)

### CodeRabbit Configuration

Max iterations: 3
Auto-fix categories:
- Code style and formatting
- Type errors
- Simple logic bugs
- Documentation improvements

Blocker queue triggers:
- Iteration 3 still has failing tests
- Architecture change suggestions
- Security vulnerabilities requiring human decision
