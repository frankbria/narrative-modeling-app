# Issue #471 — [P0.28] [bug] The entire data-issues feature 404s — its router is only mounted on a dead aggregator

Plan source: self-authored; approved autonomously (no architectural fork).

## Design
- Mount `data_issues.router` in `main.py` at `{API_V1_STR}/data-issues` like its neighbours (the aggregator stays for P3.1).
- Review as new code (AC3): every handler already scopes `UserData`/`DataIssueRecord` on `user_id`; route tests prove
  404 for another tenant's dataset on all six endpoints.
- `/detect` reaches OpenAI when `options.include_ai_analysis` (default true) → `quota("ai_calls")` (#461 rule), released
  when the service reports the analyzer did not run (`summary.ai_analysis_used`). The registry now follows one hop
  (route → service → model module) and the service imports the analyzer at module level, so the router is in scope.
- AC2: route tests with `async_authorized_client` + real UserData/DataIssueRecord documents, S3 stubbed at
  `get_dataframe_from_s3`: detect (issues found on a frame with missing values/duplicates), issues, preview-fix,
  apply-fix, batch-fix, history; 404 matrix.
- AC5: `test_every_router_is_mounted.py` — every module under `app/api/routes/` appears in the live route table,
  with an explicit allow-list for the dead ones (`trained_model`, if confirmed dead; the aggregator).
- AC4: the frontend's `lib/services/data-issues.ts` paths are pinned in `apiUrlConstruction.test.ts`; UI reachability
  depends on where the components are mounted (checked).

## Steps
1. [x] RED: mounted-routers test; route tests; registry hop
2. [x] GREEN: mount, quota, ai_analysis_used
3. [x] Frontend path pins (+ e2e if a page hosts the UI)
4. [x] Docs: CLAUDE.md

## Acceptance criteria
- [x] AC1 mounted in main.py, route order fine
- [x] AC2 route tests, real documents
- [x] AC3 tenant scoping reviewed + tested
- [x] AC4 frontend calls verified
- [x] AC5 every router mounted test
