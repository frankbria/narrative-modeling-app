# Issue #83 — Confidence scoring + per-prediction explainability

**Branch:** `feat/83-prediction-confidence-explainability`
**Source:** Traycer plan (adapted) — see deviations below.

## Acceptance Criteria (from issue)
- [ ] AC1 — Confidence scores (0-1) for all classification predictions via `predict_proba` + probability calibration
- [ ] AC2 — Uncertainty indication for regression (prediction intervals)
- [ ] AC3 — Per-prediction feature-contribution breakdown (model-native importance; SHAP from #80 not yet available → fall back)
- [ ] AC4 — Low-confidence warning flags in both single and batch results
- [ ] AC5 — Confidence column included in batch prediction output CSV *(already shipped in #82 — verify + extend with low-confidence column)*
- [ ] AC6 — Plain-language explanation of what drives each prediction

## Adapted Plan (lean — no SHAP, no separate calibrated-model files)

### 1. `ConfidenceService` (new: `app/services/confidence_service.py`)
- `confidence_from_proba(proba_row, problem_type)` → max class proba (0-1)
- `is_low_confidence(score, threshold=0.7)` → bool flag
- `calibrate_classifier(estimator, X_cal, y_cal, method)` → `CalibratedClassifierCV(cv="prefit")`; pick sigmoid (small data) vs isotonic; returns wrapper + Brier score
- `regression_interval(pred, residual_std)` → `[pred-1.96σ, pred+1.96σ]`
- Tests: `tests/test_services/test_confidence_service.py`

### 2. `PredictionExplainerService` (new: `app/services/prediction_explainer_service.py`)
- Model-native, NO SHAP. Linear (`coef_`): per-row contribution = coef·x (genuinely per-prediction). Tree (`feature_importances_`): global importance as documented fallback.
- `explain(estimator, X_row, feature_names, top_n=5)` → top-N `FeatureContribution`
- `explanation_text(top_features, prediction, problem_type)` → deterministic plain-language string (rule-based, no LLM cost/latency per prediction)
- Tests: `tests/test_services/test_prediction_explainer_service.py`

### 3. Schemas (`app/schemas/model.py`)
- `PredictionConfidence`, `FeatureContribution`, `PredictionExplanation` — all optional/backward-compatible

### 4. MLModel fields (`app/models/ml_model.py`)
- `is_calibrated: bool=False`, `calibration_method: Optional[str]`, `calibration_score: Optional[float]`, `residual_std: Optional[float]` — all default None/False (old models degrade gracefully). `feature_importance` already exists.

### 5. Training integration (`automl_engine.py` + `model_storage.py`)
- After best model chosen + #79 held-out arrays captured: calibrate best estimator via `cv="prefit"` on the held-out test split, swap the persisted estimator for the calibrated one (no new S3 path), record `is_calibrated`/`calibration_method`/`calibration_score`.
- Regression: compute `residual_std` from existing y_test/y_pred arrays.

### 6. Endpoints
- Training predict (`model_training.py`): add per-record `low_confidence` flags, `explanations` (gated by `include_explanations: bool=False`), regression `prediction_interval`.
- Production predict (`production.py`): add the same confidence fields (currently missing entirely).
- Batch (`batch_prediction.py`): add per-record `low_confidence`, summary `low_confidence_count`, `low_confidence` CSV column; optional explanations.

### 7. Frontend (`apps/frontend`)
- `app/predict/page.tsx`: low-confidence warning badge, feature-contribution section, explanation text (single); low-confidence count + interval (batch). Update `lib/services/model.ts` types. Update jest + `e2e/workflows/predict.spec.ts` minimally.

### 8. Docs: docstrings + CLAUDE.md issue-#83 entry. No API version bump.

## Deviations from Traycer plan
- **DROP SHAP entirely** (Traycer steps 1-3 SHAP parts). #80 (P3.3) is OPEN; AC says "fall back to model-native importance". SHAP belongs to #80.
- **DROP 3 new viz endpoints** (Traycer step 11: calibration-curve / confidence-distribution / explanation-summary) — not in AC, YAGNI.
- **Simplify calibration storage** — swap persisted estimator in place + 4 metadata fields instead of separate `_calibrated.pkl` / `_shap_background.pkl` S3 artifacts.
- **Regression intervals** via stored `residual_std` (uniform, model-agnostic, reuses #79 arrays) instead of quantile regression / per-tree variance.
- **Rule-based explanation text** (deterministic) instead of per-prediction LLM calls.
