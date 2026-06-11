# Issue #79: [P2.3] Model evaluation dashboard with performance metrics

> Previous plan (issue #188 — claude-review safeguards) was **completed** and merged in PR #189
> (commit f8e96a3); see `git log tasks/todo.md`.

Plan source: CodeRabbit Coding Plan comment (2026-06-06), adapted after 3-agent codebase exploration.

## Adapted Plan

### Contract first (done by orchestrator before fan-out)
**C1. Define the API contract**: `apps/backend/app/schemas/evaluation.py` (Pydantic) and
`apps/frontend/lib/types/evaluation.ts` (mirrored TS) committed together so backend/frontend
tracks can proceed independently.
- `ClassificationMetrics` (accuracy, precision_macro, precision_weighted, recall, f1, roc_auc, log_loss, per_class_metrics)
- `RegressionMetrics` (mae, mse, rmse, r2, mape)
- `ConfusionMatrixData` (labels, matrix), `CurvePoint` (x, y, threshold?)
- `ROCCurveData` / `PRCurveData` (per-class curves dict + macro/baseline aux)
- `AIExplanation` (overall_assessment, metric_explanations, strengths, concerns, recommendations, generated_by: "openai"|"fallback")
- `ModelEvaluationResponse` (model_id, problem_type, metrics union, confusion_matrix?, roc_curve?, pr_curve?, feature_importance?, ai_explanation?, evaluated_at, partial: bool)
- `ModelComparisonRequest` (model_ids: 2–5) / `ModelEvaluationSummary` / `ModelComparisonResponse`

### Backend track (B1–B4, sequential within track)
**B1. Persist evaluation artifacts during training**
- `automl_engine.py`: `AutoMLResult` gains `y_test`, `y_pred`, `y_proba` (classifiers), `class_labels` — captured for the BEST model after final fit (arrays currently computed then discarded at automl_engine.py:249-254)
- `train_model_task` (model_training.py) + `model_storage.py save_model()`: serialize arrays to S3 `models/{user_id}/{model_id}/evaluation_data.json`
- `ml_model.py`: add `evaluation_data_path: Optional[str]`
- Tests: engine unit test (arrays present, lengths match); storage integration test (LocalStack-gated)

**B2. MetricsService** (`app/services/metrics_service.py`)
- Classification: accuracy, precision (macro+weighted), recall, F1, AUC-ROC (multiclass OvR), log loss, per-class breakdown
- Regression: MAE, MSE, RMSE, R², MAPE
- Confusion matrix; ROC + PR curve data per class (downsample to ≤200 points per curve to bound payload)
- Loader for evaluation artifacts from S3
- Tests: pure-function unit tests vs sklearn ground truth (binary, multiclass, regression, edge: single-class y_test, missing y_proba)

**B3. EvaluationExplanationService** (`app/services/evaluation_explanation_service.py`)
- DatasetSummarizationService pattern: instance OpenAI client, JSON mode, `@with_circuit_breaker`, deterministic fallback (built on comparison.py's rule-based style)
- Tests: mocked-client success path, fallback path (no key, API error)

**B4. Endpoints — in `model_training.py` router (`/api/v1/ml`), NOT models.py** ⚠️ deviation
- `GET /{model_id}/evaluation`: ownership check, load artifacts, compute via MetricsService, AI explanation (graceful degradation), `partial: true` fallback from MLModel scalars when artifacts missing (pre-#79 models)
- `POST /compare`: 2–5 model_ids, same user + dataset + problem_type (400 otherwise); reuses MLModel scalar metrics
- Route registration order: `/compare` before `/{model_id}` (existing /jobs precedent)
- Tests: route tests via `async_authorized_client` (404, partial, full, compare validation)

### Frontend track (F1–F5)
**F1. Service layer**: `ModelService.getEvaluation()` + `compareModels()` + `ModelServiceClient` wrappers (lib/services/model.ts), pointing at `/ml/{model_id}/evaluation` and `/ml/compare`
**F2. Chart components**: `ConfusionMatrixChart.tsx` (SVG heatmap à la CorrelationHeatmap; click selects a cell → detail panel with count/row-% = the drill-down), `ROCCurveChart.tsx`, `PRCurveChart.tsx` (Recharts LineChart, per-class lines, diagonal/baseline reference, AUC in legend, threshold in tooltip)
**F3. Evaluate page rewrite** (`app/evaluate/page.tsx`): typed state, Tabs (Overview | Confusion Matrix | Curves | Compare), Model Report Card section, classification/regression conditional rendering, FeatureImportanceChart reuse, PRESERVE stage guards + completeStage payload
**F4. Comparison UI**: `ModelComparisonTable.tsx` (models as columns, best-per-row highlighted) + model selector fed by `listModels(datasetId)`
**F5. Export**: `lib/utils/export.ts` — CSV via existing Blob pattern; PDF via NEW deps `jspdf` + `jspdf-autotable`; buttons in page header
- Tests per component: jest with established recharts/fetch/next-auth mocks

### Integration (orchestrator)
**I1.** Merge tracks, full backend + frontend suites, type-check, lint
**I2.** E2E: `e2e/pages/EvaluatePage.ts` + `e2e/workflows/evaluate.spec.ts` (follow train.spec.ts pattern); run locally via Playwright
**I3.** Demo with real trained model (local stack: MongoDB + backend + frontend, SKIP_AUTH dev flow per local-demo-environment memory)

## Acceptance Criteria (from issue)
- [ ] Classification metrics: Accuracy, Precision, Recall, F1, AUC-ROC, Log Loss
- [ ] Regression metrics: MAE, MSE, RMSE, R², MAPE
- [ ] Confusion matrix with interactive drill-down (cell click → detail panel)
- [ ] ROC curve and Precision-Recall curves
- [ ] Comparison across models trained in the same AutoML run
- [ ] AI-generated plain-language explanations (Model Report Card)
- [ ] Export capabilities (PDF, CSV)
- [ ] evaluate page wired to real endpoints; E2E evaluate workflow test passes

## Deviations from Original Plan
1. **Endpoints live at `/api/v1/ml/...` (model_training.py), not models.py**: models.py is the legacy ModelConfig router; real trained `MLModel` docs + ownership patterns + the modelId the workflow state carries all live in the ml router. The frontend fetch is being rewritten anyway, so "matches existing frontend URL" no longer favors models.py.
2. **Evaluation artifacts persisted for the BEST model only** (plan ambiguous): per-candidate arrays would multiply S3 writes for little value — comparison uses scalar metrics already persisted in TrainingJob.model_comparison / MLModel.
3. **Comparison constrained to same dataset + problem_type** (per plan) and implemented from MLModel scalars, not full artifact recomputation.
4. **Confusion-matrix drill-down = cell-click detail panel** (count, % of actual class). Row-level sample drill-through deferred (no sample IDs in artifacts).
5. **Curve payloads downsampled** (≤200 points/curve) — not in original plan; raw thresholds can be tens of thousands of points.
6. **Old models degrade gracefully**: `partial: true` response from MLModel scalars when `evaluation_data_path` is absent.

## Orchestration
Contract commit by orchestrator → two parallel implementation agents (backend track, frontend track — disjoint directories, worktree isolation) → orchestrator integrates, runs suites, E2E, demo.
