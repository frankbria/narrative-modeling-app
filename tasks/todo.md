# Issue #472 — [P0.29] [bug] POST /api/v1/ (store.py) returns 500 unconditionally

Plan source: self-authored; the issue offers remove-or-fix and recommends removal → remove. Approved autonomously.

## Design
- Delete `app/api/routes/store.py`, its import and mount in `main.py`.
- Evidence for removal: no frontend caller (grep for a bare `${API_URL}/` POST finds nothing), no tests, and the
  handler cannot succeed (constructs `UserData` with fields the model does not have).
- Update the metering registry (`_STORE_ROUTE`, the `/api/v1/` entry) and anything in `api_documentation.py`.
- Guard: the mounted-routers test and the registry keep the route table honest; a test asserts `POST /api/v1/` is 404/405.

## Steps
1. [x] RED: a test that POST /api/v1/ is no longer a route
2. [x] GREEN: delete module + mount + registry entries
3. [x] Docs: CLAUDE.md registry note mentions store.py — update

## Acceptance criteria
- [x] Removal chosen and stated; no caller found (frontend + api_documentation grep)
- [x] Route gone; registry/tests updated
