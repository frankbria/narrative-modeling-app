# Issue #81 — Error Analysis Tools (adapted plan)

**Phase 5.3 post-beta V2.** Build error-analysis tools: misclassification patterns, error
clustering/segments, confusion pairs, AI suggestions, error-case browser with drill-down.

## Scope decisions (vs. stale Traycer plan)
The Traycer/CodeRabbit plans target the **dead legacy `ModelConfig` / `/models/` surface**.
Real surface is **`MLModel` / `/api/v1/ml/`** (memory: two-model-surfaces). Cuts:

- **Reuse #79's `evaluation_data.json`** — persist the held-out **transformed feature matrix
  `X_test` + `feature_names` into the SAME payload**. No new MLModel field, no new S3 file,
  no new loader (reuse `load_evaluation_artifacts`). Pre-#81 models lack `X_test` → `partial`.
- **One endpoint** `GET /api/v1/ml/{model_id}/errors`. Drop `POST /error-patterns` — drill-down
  is **client-side filtering** of returned cases. Never 500 for owned models; 404 foreign.
- **AI suggestions** via the OpenAI circuit breaker + deterministic rule-based fallback,
  mirroring `EvaluationExplanationService` (NOT MCP — that's not the real AI path).
- **Frontend: one `ErrorAnalysisDashboard`** in a new **"Errors" tab** on `app/model/[id]/page.tsx`.
  Reuse `ConfusionMatrixChart` + `BarChart` + tables. **Drop** the 4 bespoke viz components
  (PatternTree/ClusterScatter/SegmentChart/ConfusionMatrixHeatmap) and the dedicated route.

## Backend
1. `automl_engine.py`: add `X_test: np.ndarray | None` to `AutoMLResult`; set it from
   `X_test_transformed.to_numpy()` (already in memory at line ~255). `feature_names` already exists.
2. `model_storage.py::build_evaluation_payload`: add optional `X_test`/`feature_names` args →
   JSON-safe rows under `payload["X_test"]` + `payload["feature_names"]`.
3. `model_training.py` (~509): pass `X_test=result.X_test, feature_names=result.feature_names`.
4. `app/schemas/error_analysis.py`: `ErrorDistribution`, `ConfusionPair`, `ErrorSegment`,
   `ErrorCluster`, `ErrorPattern`, `ErrorCase`, `ErrorAnalysisResponse` (with `partial`).
5. `app/services/error_analysis_service.py` — stateless, **never raises**:
   - distribution: overall + per-class error rate (y arrays)
   - confusion pairs: off-diagonal counts, reuse `MetricsService.compute_confusion_matrix`
   - segments: per-feature quantile binning, error rate per bin (needs X_test)
   - clusters: KMeans on scaled error rows, label by top distinguishing features (needs X_test)
   - patterns: shallow `DecisionTreeClassifier` surrogate on error indicator → readable rules (X_test)
   - cases: index/actual/predicted/confidence (+ top feature values); regression = residual-based
   - `generate_suggestions`: rule-based + optional OpenAI (circuit breaker)
6. `model_training.py`: `GET /{model_id}/errors` registered **before** catch-all `/{model_id}`.

## Frontend
7. `lib/types/evaluation.ts`: mirror error-analysis schemas.
8. `lib/services/model.ts`: `getErrorAnalysis(modelId)`.
9. `components/ErrorAnalysisDashboard.tsx`: overview cards + sections (distribution, confusion
   pairs, patterns, segments, clusters, cases w/ confusion-pair filter, AI suggestions).
10. `app/model/[id]/page.tsx`: add "Errors" tab → `<ErrorAnalysisDashboard modelId={modelId} />`.

## Tests (TDD)
- `tests/test_services/test_error_analysis_service.py` (distribution/pairs/segments/clusters/
  patterns/cases/suggestions + empty-errors + regression + never-raises)
- `tests/test_api/test_error_analysis.py` (full / partial / 404 / regression)
- extend `test_model_storage.py` (X_test in payload)
- `__tests__/components/ErrorAnalysisDashboard.test.tsx`, extend `model.test.ts`

## Known limitations
- Error analysis uses **engineered** features (same as SHAP #80); no original-space reconstruction.
- Clustering = KMeans (k by simple heuristic), not DBSCAN/t-SNE. Segments = quantile bins.
- Drill-down is client-side; no server-side `POST /error-patterns`.
- Pre-#81 models (no `X_test`) → distribution/pairs/cases only, segments/clusters/patterns empty.
