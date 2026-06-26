# Issue #86 — [P5.6] Client SDKs and integration tools (Python/JS SDKs, Postman)

**Post-beta V2.** Traycer plan is badly over-scoped (3-4 wks: new Webhook + WebhookDelivery
Beanie docs, WebhookService, async-predict endpoint + job TTL store, SDK test-runner that
shells out to python/tsc, Redis SDK cache, SDK download analytics, monitoring endpoints, a
`/deployments/{id}/` router on the dead surface). Most of that is speculative and targets the
wrong surface. Adapting to the **real `MLModel` / `/api/v1/ml/`** surface (per
two-model-surfaces note) and the real production serving contract.

## What already exists (verified)
- `APIDocumentationService` (`app/services/api_documentation.py`) generates **generic**
  python/javascript/curl clients + jupyter/colab/streamlit/flask samples + a Postman collection,
  served at `GET /api/v1/docs/clients/{language}`, `/docs/integrations/{framework}`,
  `/docs/postman`. **Problems:** hardcoded fake `api.narrativeml.com`, wrong predict route
  (`/api/v1/predictions/predict`), Bearer auth — NOT the real serving contract, NOT per-deployment,
  no TypeScript.
- Real serving: `POST /api/v1/production/v1/models/{model_id}/predict`, header
  `X-API-Key: sk_live_...`, body `{"data":[{<feature>:...}], "include_probabilities":true}`.
- Real model surface: `GET /api/v1/ml/{model_id}`, `GET /ml/{model_id}/features` (input schema),
  `PUT /ml/{model_id}/deploy`. `MLModel` has `model_id/name/problem_type/feature_names`.
- Existing **async prediction** mechanism = batch jobs (#82): `BatchPredictionService`
  create→poll→download via FastAPI BackgroundTasks. `httpx>=0.28.1` already a dep.
- Frontend deploy page (`app/deploy/page.tsx`) already renders `EndpointTester` (#84) + a curl
  example + "View interactive API docs" link — natural home for an SDK panel.

## Acceptance criteria → plan
- AC1 Python + JS/**TS** SDKs + cURL **per deployment**  (groundwork exists, generic only)
- AC2 Postman collection (make it per-deployment)         (groundwork exists, generic only)
- AC3 framework code samples                              (groundwork exists)
- AC4 webhook support for async predictions — **lean** (see Step 3 / decision)
- AC5 SDK documentation (README per SDK)

## Adapted steps

### 1. `SDKGenerator` service — `app/services/sdk_generator.py` (new, pure/stateless)
Deployment-aware generators parameterized by `(model_id, model_name, feature_names,
problem_type, serving_base_url)`. All hit the **real** production endpoint with `X-API-Key`
and a real `{"data":[{feature: 0}...]}` body built from actual `feature_names`:
- `python_sdk()` — `requests`-based `<Model>Client.predict(records)`; install + usage docstring.
- `typescript_sdk()` — typed `fetch` client with request/response interfaces + JSDoc (the AC's
  missing piece).
- `javascript_sdk()` — plain-JS fetch client.
- `curl_examples()` — real predict + `/info` calls.
- `postman_collection()` — per-deployment collection (predict + info; webhook example if Step 3).
- `framework_samples()` — flask / fastapi / express / nextjs snippets that call the SDK.
- `readme(language)` — install + quickstart + auth + troubleshooting (AC5).
- `sdk_info()` — languages list, model metadata, install instructions, sample record.
Reuse feature schema from `feature_names` (numeric default 0). Never raises.

### 2. SDK routes — add to `app/api/routes/model_training.py`, registered BEFORE catch-all `/{model_id}`
User-auth (`get_current_user_id`), scoped to owned models (404 unknown/foreign):
- `GET /api/v1/ml/{model_id}/sdk` → `sdk_info()` JSON.
- `GET /api/v1/ml/{model_id}/sdk/{language}` → SDK source as `text/plain`
  (`python|typescript|javascript|curl`; 404 unknown language). Serving base URL synthesized from
  `request.base_url` (mirrors #84 deploy endpoint synthesis), `deployment_endpoint` if set.
- `GET /api/v1/ml/{model_id}/sdk/postman` → Postman collection JSON.

### 3. AC4 webhooks — LEAN (decision pending in Phase 4)
**Recommended:** optional `webhook_url` + `webhook_secret` on the existing **batch** prediction
job. On batch completion, best-effort HMAC-SHA256-signed `httpx` POST of the job summary to
`webhook_url` (never blocks/raises; one retry). Reuses BatchPredictionService + background tasks —
**no** new Beanie docs, **no** async-predict endpoint, **no** webhook CRUD routes, **no** TTL store.
Generated SDK gets a webhook-receiver + signature-verify sample. ~50 LOC + tests.
*(Alt: defer webhooks entirely, document in Known Limitations.)*

### 4. Frontend SDK panel
- `ModelService.getSdkInfo / getSdk(modelId, language) / getPostman(modelId)`.
- `components/SdkPanel.tsx` on the deploy page beside `EndpointTester`: language tabs
  (Python/TypeScript/JavaScript/cURL), code block with copy + download buttons, "Download Postman
  collection" button.

### 5. Stale generic `/docs/*` surface — leave as-is (YAGNI; no real callers). Defer.

## Tests
- `tests/test_services/test_sdk_generator.py` — each language contains real endpoint, `X-API-Key`,
  real feature names, valid Postman JSON; python/curl smoke-parse.
- `tests/test_api/test_sdk_routes.py` — 200 per language, 404 bad language, 404 foreign model,
  base-URL synthesis.
- (if Step 3) extend `tests/test_services/test_batch_prediction.py` — webhook fired on completion,
  HMAC signature, never raises on bad URL.
- Frontend `__tests__/components/SdkPanel.test.tsx`, extended `model.test.ts`.

## Deviations from Traycer (this plan is heavily adapted)
- DROP: `/deployments/{id}/` router (dead surface), Webhook/WebhookDelivery Beanie docs +
  WebhookService + 5 CRUD routes, async-predict endpoint + job TTL store, `SDKTestRunner` that
  executes generated code, Redis SDK caching, SDK version tracking, download analytics, monitoring
  sdk-usage endpoint, zip-package downloads, jinja2 template dir.
- KEEP minimal/real: per-deployment generators on `/ml/`, TS SDK (the genuine gap), per-deployment
  Postman, framework samples, SDK README (AC5), and a lean batch-completion webhook for AC4.

## Known limitations (for PR)
- SDKs are single-file source (copy/paste or download), not pip/npm-published packages.
- Webhooks fire only on **batch** completion (no per-request sync-predict callback, no webhook
  management UI, no delivery-log persistence) — beta-appropriate; full webhook infra deferred.
- Generic `/docs/*` surface left untouched.
