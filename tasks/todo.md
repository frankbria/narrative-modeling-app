# Issue #87 — Backend workflow persistence (replace localStorage-only state)

> Previous plan (issue #191 — e2e upload fixture) was **completed** and merged in PR #192
> (commit f4d77b9); see `git log tasks/todo.md`.

**Plan source**: CodeRabbit plan comment (2026-06-06), adapted to current codebase.
**Branch**: `feature/87-workflow-persistence`

## Adapted Plan

### Step 1 — Backend data layer (TDD: tests first)
- [x] Create `apps/backend/tests/test_services/test_workflow_service.py` (RED)
  - create_workflow: generates workflow_id, initial history entry (version=1)
  - update_workflow: appends history entry with incremented version, updates `updated_at`
  - get_by_dataset: returns workflow; raises NotFoundError when absent
  - duplicate create raises ConflictError
  - history accumulation over multiple updates; history cap (keep latest 50)
- [x] Create `apps/backend/app/models/workflow.py`
  - `StateHistoryEntry(BaseModel)`: version, current_stage, completed_stages, stage_data, model_id, deployment_id, timestamp
  - `WorkflowState(Document)`: workflow_id (str UUID), user_id `Indexed(str)`, dataset_id `Indexed(str)`, current_stage, completed_stages (List[str]), stage_data (Dict[str, Any]), model_id, deployment_id, state_history, created_at/updated_at via `get_current_time()`
  - `Settings`: collection `workflow_states`; indexes incl. compound unique `[("user_id",1),("dataset_id",1)]`
  - Follow `dataset.py` patterns (Field descriptions, model_config json_encoders)
- [x] Create `apps/backend/app/services/workflow_service.py`
  - `WorkflowService(BaseService[WorkflowState])`, `_get_id_field() -> "workflow_id"`
  - `get_by_dataset`, `create_workflow` (app-level duplicate check → ConflictError), `update_workflow` (append history, cap 50), `get_history`
  - Exceptions from `app.services.exceptions`
- [x] Register model in `apps/backend/app/models/registry.py` (NOT main.py — registry is canonical)

### Step 2 — Backend API layer (TDD: tests first)
- [x] Create `apps/backend/tests/test_api/test_workflows.py` (RED) — `@pytest.mark.integration`, `async_authorized_client` + `setup_database`, user `test_user_123`
  - POST → 201; duplicate POST → 409
  - GET → 200 with state; missing → 404; other user's workflow → 404 (user-scoped lookup; deviation from plan's 403, see below)
  - PUT → 200, appends history; missing → 404
  - GET /history → entries + total_versions
  - Recovery: create at stage N → new client session → GET returns stage N; history checkpoints reconstructable
- [x] Create `apps/backend/app/schemas/workflow.py`
  - `WorkflowCreateRequest`, `WorkflowUpdateRequest` (all-optional), `WorkflowResponse`, `StateHistoryEntryResponse`, `WorkflowHistoryResponse`
- [x] Create `apps/backend/app/api/routes/workflows.py`
  - `GET/POST/PUT /workflows/{dataset_id}`, `GET /workflows/{dataset_id}/history`
  - Auth via `Depends(get_current_user_id)` (`app.auth.nextauth_auth`); HTTPException mapping; logging per `datasets.py`
- [x] Register router in `apps/backend/app/main.py`: `app.include_router(workflows.router, prefix=f"{settings.API_V1_STR}", tags=["workflows"])`

### Step 3 — Frontend integration (TDD: tests first)
- [x] Create `apps/frontend/lib/contexts/__tests__/WorkflowContext.persistence.test.tsx` (RED) — mock fetch + getAuthToken
  - loadWorkflow: backend 200 → state hydrated + localStorage cache refreshed; 404 → localStorage fallback; network error → localStorage fallback
  - saveWorkflow: POST first time, PUT after exists (and PUT after POST→409)
  - completeStage triggers saveWorkflow
- [x] Modify `apps/frontend/lib/contexts/WorkflowContext.tsx`
  - Remove stub early-return in `loadWorkflow()` (~line 158); URL `${API_URL}/workflows/${datasetId}` (API_URL already includes /api/v1)
  - Auth via existing `getAuthToken()` helper, conditional Bearer header (ModelService pattern)
  - `saveWorkflow()`: POST when not yet created, PUT thereafter; 409 → PUT; failure → localStorage fallback (existing useEffect stays as cache layer)
  - `completeStage()` fires saveWorkflow after state update (stage boundaries are infrequent — no debounce; YAGNI)
  - Page-load recovery: backend state wins; 404/network error → keep localStorage state
  - Set ↔ Array serialization preserved (completedStages)

### Step 4 — Quality gates & docs
- [x] Backend: `cd apps/backend && uv run pytest tests/test_services/test_workflow_service.py tests/test_api/test_workflows.py -v` then full relevant suite; ruff
- [x] Frontend: `npm test`, `npm run type-check`
- [x] Update CLAUDE.md (issue #87 section), e2e README if seeding behavior affected
- [x] Demo (Phase 11), PR, CI, merge

## Acceptance Criteria (from issue)
- [x] Workflow state stored in MongoDB per user/dataset: current stage, completion flags, key selections (stage_data)
- [x] State saved at each stage boundary; restored on login/page load
- [x] Automatic recovery after browser crash/refresh mid-stage
- [x] Version history of workflow state changes (append log)
- [x] Endpoints: POST/GET/PUT `/api/v1/workflows/{id}` (+ `/history`)
- [x] Frontend WorkflowContext reads/writes backend state with localStorage offline fallback
- [x] Integration tests for save/restore/recovery paths

## Deviations from the CodeRabbit plan
1. **Model registration via `app/models/registry.py`**, not `init_beanie()` in `main.py` — registry became canonical in issue #160; main.py already consumes `DOCUMENT_MODELS`.
2. **Wrong-user GET returns 404, not 403** — lookups are scoped by `(user_id, dataset_id)`, so another user's workflow is simply not found; avoids leaking existence. Plan's 403 test becomes a 404 test.
3. **App-level duplicate check (ConflictError → 409) in addition to the unique index** — unit tests run on mongomock with `skip_indexes=True`, so the index alone can't be relied on in tests.
4. **History capped at 50 entries** (keep latest) — full-snapshot entries with unbounded growth risk the 16MB Mongo doc limit; cap is one line and satisfies "simple append log".
5. **`StateHistoryEntry` also snapshots `model_id`/`deployment_id`** so a history entry can fully reconstruct state (plan's recovery test demands full reconstruction but omitted these fields).
6. **No debounce on auto-save** — stage boundaries are infrequent user actions; plan said "if needed". YAGNI.
7. **Frontend URL is `${API_URL}/workflows/…`** — `API_URL` constant already contains `/api/v1`.
