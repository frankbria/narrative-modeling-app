# Issue #80 — Model interpretability: SHAP values & feature importance

**Plan source:** Adapted from the Traycer plan, which was **largely discarded as stale + over-scoped** (it
referenced files that don't exist here — `models.py`/`model.py`/`ModelConfig`/`model_service.py` — and
proposed LIME, matplotlib/plotly image generation, dependence plots, KernelExplainer, cross-model comparison,
a separate `/models/[id]/interpretability` page, and a Redis cache layer, all of which the issue's own Beta
Scope defers post-beta). This plan is driven by the issue's **Acceptance Criteria** + the real codebase
(verified 2026-06-14), building on the #79 evaluation pipeline and #83 explainer infrastructure.

## Scope decisions / deviations
- **Endpoints live under `/api/v1/ml/`**, not `/api/v1/models/`. Every real model endpoint (predict, features,
  evaluation, compare) and the frontend `ModelService` already point at `/ml/`. `/api/v1/models/` is a legacy
  `ModelConfig` surface with no prediction endpoints. The AC's `/api/v1/models/...` path was from the stale plan.
- **SHAP via TreeExplainer (tree models) + LinearExplainer (linear models) only.** Verified installable &
  functional on Python 3.13 / numpy 2.3 / sklearn 1.7 (shap 0.52). Models with neither (KNN, SVM-rbf) fall back
  to model-native / stored importance — exactly the roadmap's "fall back to native if blocked." **No LIME, no
  KernelExplainer, no PDP/ICE/dependence plots** (post-beta per roadmap).
- **Frontend renders from JSON with Recharts** (same as #79 ROC/PR/feature-importance charts). **No backend
  image generation** (no matplotlib/plotly).
- **SHAP computed at training time** on the held-out test set (sampled <=200 rows) from the **raw** estimator
  (before #83 calibration wrapping), persisted to S3 like #79's `evaluation_data.json`. Keeps the <30s budget
  off the request path; endpoints serve stored data instantly. All best-effort — never fails training.
- **Per-prediction SHAP extends #83's `PredictionExplainerService`/`PredictionEnricher`** (prefer SHAP, fall
  back to existing linear/tree/stored logic) — not a parallel system. Single-predict path only.

## Steps (TDD: RED -> GREEN -> REFACTOR)
1. **Deps** — add `shap>=0.46` to `apps/backend/pyproject.toml`; `uv lock`/`uv sync`; confirm import.
2. **InterpretabilityService** (`app/services/interpretability_service.py`) — `select_explainer_type` (unwrap
   calibrated/frozen/pipeline), `compute_global_shap` (mean |SHAP| per feature + sampled beeswarm points +
   explainer_type; multiclass -> mean-abs across classes), `compute_instance_shap` (base + signed per-feature
   contributions, class slice for multiclass), `top_drivers_text` (plain language), sampling helper. Never raises.
   Tests: tree/linear/regression/multiclass/unsupported->None/sampling cap/JSON-safe serialization.
3. **Training integration** — `AutoMLEngine`: compute global SHAP on `X_test_transformed` (sampled) from the
   raw estimator before calibration; store on `AutoMLResult`. `model_storage.save_model`: `build_shap_payload`
   -> S3 `models/{user_id}/{model_id}/shap_data.json`; set new `MLModel` fields. Best-effort + warning on failure.
4. **MLModel fields** — `shap_values_path: Optional[str] = None`, `shap_explainer_type: Optional[str] = None`
   (optional -> pre-#80 models degrade).
5. **Schemas** — `schemas/evaluation.py`: `ShapSummaryResponse`, `FeatureImportanceResponse` (+ mirror to
   `lib/types/evaluation.ts`). Add `"shap_tree"`/`"shap_linear"` to #83 `PredictionExplanation.method`.
6. **Endpoints** in `model_training.py` (registered before `/{model_id}` catch-all):
   `GET /{model_id}/feature-importance` (native + SHAP importance, ranked; partial when none; 404 foreign),
   `GET /{model_id}/shap` (load shap_data.json; partial + message when absent/unsupported; never 500; 404 foreign).
   Tests: `tests/test_api/test_interpretability.py`.
7. **Per-prediction SHAP** — extend `PredictionExplainerService`/`PredictionEnricher` to prefer instance SHAP,
   fall back to linear/tree/stored. Gated behind existing `include_explanations`, single-predict path.
   Tests: extend `test_prediction_explainer_service.py`.
8. **Frontend service/types** — `lib/types/evaluation.ts` mirror; `lib/services/model.ts` add `getShapSummary`,
   `getFeatureImportance` (call `/ml/{id}/shap`, `/ml/{id}/feature-importance`).
9. **Frontend viz** — `components/ShapSummaryChart.tsx` (Recharts bar of mean |SHAP|, FeatureImportanceChart
   pattern); integrate SHAP global importance + plain-language drivers into the evaluate page Overview (native
   fallback when partial). Predict page's "What drove this prediction" panel now SHAP-powered (minimal change).
   Tests: `__tests__/components/ShapSummaryChart.test.tsx` + extend evaluate page test.
10. **Docs** — update CLAUDE.md issue-history (#80 bullet); API docs if needed (Phase 12b).

## Acceptance Criteria -> coverage
- [ ] Global feature importance for all beta algorithms -> Steps 6, 9 (native + SHAP; native fallback always available)
- [ ] SHAP summary plot data (Tree/Linear explainers) -> Steps 2, 3, 6, 9
- [ ] Individual prediction explanations (waterfall-style contributions) -> Step 7 + existing predict panel
- [ ] Plain-language explanation of top drivers -> Step 2 `top_drivers_text` (+ #83 text)
- [ ] Sampling strategy, SHAP stays fast (<30s) -> Step 2 sampling + Step 3 train-time precompute (off request path)
- [ ] Endpoints `feature-importance` + `shap` -> Step 6 (under `/api/v1/ml/` — deviation noted above)
- [ ] Frontend visualizations on evaluate page, same chart library (Recharts) -> Step 9
