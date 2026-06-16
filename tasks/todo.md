# Issue #168 — Frontend deploy page contract mismatch (POST vs PUT + response fields)

**Branch:** `fix/168-deploy-page-contract-mismatch`
**Scope (confirmed):** Full fix — 3 AC + the broken `checkDeploymentStatus`.

## Acceptance Criteria
- [ ] Deploy page request method/URL matches the backend route (`PUT /models/{id}/deploy`)
- [ ] Response fields read by the UI exist in `ModelDeployResponse`
- [ ] `DeployResponse` in `lib/types/api.ts` matches the backend schema

## Backend contract (source of truth)
- `PUT /api/v1/models/{model_id}/deploy` → `ModelDeployResponse { model_id, status, deployed_at, deployment_endpoint?: str|null, message }`
- Request body: `ModelDeployRequest { endpoint?: str }` (extra fields ignored)
- No `GET /models/{id}/deployment` route exists. Status lives in `GET /models/{id}` → `deployment_config { is_deployed, deployment_endpoint?, deployed_at? }`

## Plan (TDD)
1. **RED** — `__tests__/app/deploy/page.test.tsx`: assert PUT method, endpoint read from `deployment_endpoint`, no `api_key` UI, `completeStage` gets `model_id`+`deployment_endpoint`, and mount status check hits `GET /models/{id}` (not `/deployment`).
2. `lib/types/api.ts`:
   - `DeployResponse` → `{ model_id, status, deployed_at, deployment_endpoint: string|null, message }` (+ JSDoc → backend schema).
   - Replace `DeploymentStatusResponse` with a narrow `ModelDeploymentView` (`deployment_config?: { is_deployed, deployment_endpoint, deployed_at }`).
3. `app/deploy/page.tsx`:
   - `handleDeploy`: POST→PUT; clean body (`{}` — endpoint optional); read `data.deployment_endpoint`/`data.model_id`; `completeStage` uses `model_id`+`deployment_endpoint`.
   - `checkDeploymentStatus`: `GET /models/{id}`; if `deployment_config.is_deployed`, build a `DeployResponse` from it.
   - Success UI: drop the API Key section; render `deployment_endpoint` (with null fallback); fix the example `curl` (remove `api_key` Authorization header).
4. **GREEN** — `npm test` (deploy), `npm run type-check`, eslint.
5. deslop → quality gate (cross-family review) → PR → demo → CI → docs → merge.

## Out of scope (Known Limitations)
- `lib/services/visualization.ts` `getBoxPlot`/`getCorrelationMatrix` camelCase drift — has **no callers** (`useVisualizations` unused). Note in PR; defer (YAGNI). Not in AC.
- Backend issuing real API keys on deploy (intentionally not done).
