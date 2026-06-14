# Issue #80 — Model Interpretability (SHAP) Demo

*2026-06-14T20:39:54Z*

Proves every acceptance criterion of issue #80 with live outputs from the REAL services and the REAL HTTP endpoints (httpx + ASGITransport against a local Mongo). Mapping: AC1/2/5 global SHAP + sampling/speed; AC3 per-prediction SHAP; AC4 plain language; AC6 the two endpoints + partial degradation + 404; AC7 covered separately by the frontend chart test/wiring.

```bash
PYTHONPATH=. uv run python tasks/issue_80_demo.py 2>/dev/null
```

```output

========================================================================
AC1/AC2/AC5 — Global SHAP summary (TreeExplainer) + sampling/speed
========================================================================
explainer_type = tree
rows explained (sampled, cap 200) = 200
elapsed = 0.36s  (AC: <30s for typical beta datasets)
mean |SHAP| per feature (ranked):
   income        0.2227
   tenure        0.1698
   credit_score  0.1254
   age           0.0086

========================================================================
AC2 — LinearExplainer for linear models
========================================================================
explainer_type = linear
top driver = tenure

========================================================================
AC3 — Per-prediction SHAP (waterfall-style), tree models, per-row
========================================================================
row 0: {'age': 0.0037, 'income': 0.2783, 'credit_score': 0.1213, 'tenure': 0.1059}
row 1: {'age': 0.0108, 'income': 0.1676, 'credit_score': 0.0829, 'tenure': 0.2296}
row 2: {'age': 0.0029, 'income': 0.2025, 'credit_score': 0.0479, 'tenure': 0.2375}
-> contributions differ per row (true per-prediction SHAP, not global)

========================================================================
AC4 — Plain-language explanation of top drivers
========================================================================
income, tenure and credit_score account for most of this model's decisions, ranked by their average impact on the model's output.

========================================================================
Fallback — unsupported model type returns None (native fallback)
========================================================================
KNN global SHAP        = None
KNN per-instance SHAP  = None
Loading .env file from: <repo>/apps/backend/.env
Loading .env file from config.py: <repo>/apps/backend/.env

========================================================================
AC6 — GET /api/v1/ml/{id}/feature-importance (native + SHAP)
========================================================================
HTTP 200
{'model_id': 'demo_tree', 'partial': False, 'explainer_type': 'tree', 'native_importance': [{'feature_name': 'income', 'importance': 0.41}, {'feature_name': 'credit_score', 'importance': 0.33}, {'feature_name': 'age', 'importance': 0.18}, {'feature_name': 'tenure', 'importance': 0.08}], 'shap_importance': [{'feature_name': 'income', 'importance': 0.39}, {'feature_name': 'credit_score', 'importance': 0.31}, {'feature_name': 'age', 'importance': 0.2}, {'feature_name': 'tenure', 'importance': 0.1}], 'message': None}

========================================================================
AC6 — GET /api/v1/ml/{id}/shap (summary + plain language)
========================================================================
HTTP 200
{'model_id': 'demo_tree', 'partial': False, 'explainer_type': 'tree', 'problem_type': 'binary_classification', 'feature_importance': [{'feature_name': 'income', 'importance': 0.39}, {'feature_name': 'credit_score', 'importance': 0.31}, {'feature_name': 'age', 'importance': 0.2}, {'feature_name': 'tenure', 'importance': 0.1}], 'base_value': 0.5, 'plain_language': "income, credit_score and age account for most of this model's decisions, ranked by their average impact on the model's output.", 'message': None, 'evaluated_at': '2026-06-14T20:40:00.935241Z'}

========================================================================
Degradation — pre-#80 model: partial, never 500
========================================================================
HTTP 200  partial=True
message = SHAP interpretability is unavailable for this model. Tree and linear models compute SHAP at training time; other algorithms (and models trained before this feature) fall back to model-native feature importance.

========================================================================
Auth — foreign/unknown model returns 404
========================================================================
HTTP 404

All acceptance criteria demonstrated with live outputs.
```

AC7 — Frontend SHAP visualization on the evaluate page (Recharts, same library as the #79 ROC/PR/feature-importance charts). The ShapSummaryChart renders mean |SHAP| per feature + the plain-language drivers; the evaluate page Overview tab renders it best-effort below native importance (omitted when SHAP is partial/unavailable). Evidence: the component test suite below, plus the page wiring in app/evaluate/page.tsx.

```bash
cd <repo>/apps/frontend && npx jest __tests__/components/ShapSummaryChart.test.tsx 2>&1 | grep -E 'PASS|✓|Tests:' 
```

```output
PASS __tests__/components/ShapSummaryChart.test.tsx
    ✓ renders the chart with the title and plain-language summary (22 ms)
    ✓ sorts features by descending importance (3 ms)
    ✓ caps the number of bars when maxFeatures is set (3 ms)
    ✓ shows an empty state when there are no features (1 ms)
    ✓ omits the explainer badge when none is provided (3 ms)
Tests:       5 passed, 5 total
```

Result: all 7 acceptance criteria demonstrated with live outputs — global SHAP (Tree + Linear), per-prediction SHAP that varies per row, plain-language drivers, both endpoints returning real ranked JSON, graceful partial degradation for pre-#80 models (never 500), 404 for unknown models, native fallback for unsupported model types, and the Recharts frontend chart. Note: re-running shows different 'evaluated_at' timestamps and SHAP floats vary slightly with library version, so this doc is evidence-of-behaviour rather than byte-identical.
