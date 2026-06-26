# Issue #84 — Model deployment as production REST API (adapted plan)

## Reality check (Phase 2 exploration)
- **Production serving ALREADY works**: `POST /api/v1/production/v1/models/{model_id}/predict` does real
  inference on `MLModel` by id, authed by `X-API-Key` (`verify_api_key`), rate-limited per-key (#151).
  `GET .../info` too.
- **AC2 (API key auth + rate limiting): DONE** — `APIKey` model, `/settings/api` page, `RateLimitMiddleware`.
- **AC3 (OpenAPI docs): mostly done** — FastAPI `/docs` + `app/services/api_documentation.py`
  (openapi.json/yaml, client libs, Postman). Gap: per-model example + a link from the deploy page.
- **AC5 (multiple versions): satisfied by architecture** — each version (#78) is a separate
  `MLModel.model_id` → its own live production endpoint. `promote`/`versions` endpoints exist.
- **BUG / AC1 BROKEN**: the deploy button (`PUT /api/v1/models/{id}/deploy`) and status read
  (`GET /api/v1/models/{id}`) target the **dead `ModelConfig`** surface. Real trained models are
  **`MLModel`** (training creates only `MLModel`, `model_storage.py:245`). So deploy 404s against every
  real model — still broken after #168 (which only fixed the request/response *shape*, not the surface).
  `MLModel` has no deployment fields yet and no `status` enum (existing+`is_active` = trained).

## Plan

### Backend
1. **MLModel**: add 3 optional fields — `is_deployed: bool=False`, `deployment_endpoint: str|None`,
   `deployed_at: datetime|None` (optional → pre-existing models degrade). Update the `sample_ml_model`
   mock fixture(s) (recurring `response_model=MLModel` MagicMock gotcha).
2. **Real deploy on `/api/v1/ml/`** (in `model_training.py`, registered *before* catch-all `/{model_id}`):
   `PUT /api/v1/ml/{model_id}/deploy` (reuse existing `ModelDeployRequest`/`ModelDeployResponse`) →
   look up MLModel (404 unknown/foreign), set the 3 fields, **synthesize the production serving URL
   server-side when `endpoint` is omitted** (guarantees a live endpoint → AC1), return `ModelDeployResponse`.
   Status is readable via the existing `GET /api/v1/ml/{model_id}` (returns full MLModel).
3. **Backend test** `tests/test_api/test_ml_deploy.py` — deploy real MLModel (200 + fields set +
   endpoint synthesized), status reflected on GET, 404 foreign/unknown.

### Frontend
4. **Repoint deploy page** `app/deploy/page.tsx`: PUT/GET `${API_URL}/ml/{id}...`; read
   `is_deployed`/`deployment_endpoint`/`deployed_at` from top-level MLModel (not `deployment_config`).
   Update `DeployResponse`/`ModelDeploymentView` in `lib/types/api.ts`.
5. **AC4 — Endpoint testing panel** on the success view: new `components/EndpointTester.tsx`. Fetches
   `getModelFeatures(modelId)`, renders the predict-style auto form + an API-key input, POSTs to
   `${API_URL}/production/v1/models/{id}/predict` with `X-API-Key`, renders predictions/confidence.
6. **AC3 — real example + docs link**: build the curl example from real feature names
   (`getModelFeatures`) instead of `feature1/feature2`; add a "View interactive API docs" link to
   `${API_URL}/docs`.
7. **Frontend tests**: update `__tests__/app/deploy/page.test.tsx` (ml route + status fields);
   new `EndpointTester` test.

## Dropped from Traycer's 14-step plan (over-scoped / already built / wrong surface)
- No new `Deployment` Beanie document, no `DeploymentService`, no dynamic FastAPI route registration
  (production serving already routes by `model_id`).
- No new rate-limit middleware (#151 exists), no per-deployment API keys (account keys + `model_ids`
  scoping exist).
- No monitoring routes (`/monitor` page + production metrics exist).
- No version-routing/canary/alias engine — each MLModel version is already its own live endpoint.
- Targets the **real `MLModel`/`/api/v1/ml/`** surface, not the dead `ModelConfig`/`/api/v1/models/` one.

## Acceptance criteria
- [ ] AC1 one-click deploy → live, authenticated prediction endpoint per model
- [ ] AC2 API key auth + rate limiting (already done — verified, not rebuilt)
- [ ] AC3 auto-generated OpenAPI docs with request/response examples
- [ ] AC4 endpoint testing interface in the deploy page
- [ ] AC5 deploy multiple model versions simultaneously / API versioning

## Beta limitations (deliberate)
- Serving is **not gated** on `is_deployed` — any trained model is callable with a valid scoped API
  key (matches existing #82/#83 predict behavior). Deploy *marks* the model and *surfaces* its endpoint.
- No undeploy endpoint, no canary/traffic-splitting, no separate provisioned infra.
