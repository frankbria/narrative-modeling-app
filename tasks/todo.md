# Issue #450 — [P0.7] Two A/B-testing endpoints have no authentication

Branch: `fix/450-ab-testing-unauthenticated`

## Problem
`assign_variant` and `track_prediction` in `app/api/routes/ab_testing.py` omit the
`get_current_user_id` dependency the other eight endpoints all carry, and the router is
mounted without `dependencies=[...]`. Both are reachable unauthenticated by anyone.
`track_prediction` lets an anonymous caller inject prediction outcomes into any tenant's
experiment metrics — the numbers used to pick a production model. `assign_variant`
discloses `model_id` for arbitrary experiment ids.

## Correction to the issue
The issue gives the paths as `/api/v1/track-prediction` and
`/api/v1/experiments/{id}/assign-variant`. Those are wrong: it read the `include_router`
prefix in `main.py` but missed that the router itself declares
`APIRouter(prefix="/ab-testing")`. The real paths are `/api/v1/ab-testing/...`.
The vulnerability is real; only the paths were misstated.

## Plan
1. **RED** — tests in `tests/test_api/test_ab_testing.py`:
   - unauthenticated `GET .../assign-variant` → 401 (AC3, via `async_test_client`)
   - unauthenticated `POST .../track-prediction` → 401 (AC3)
   - authenticated non-owner on both → 404 (AC2)
   - owner path still works on both (regression)
2. **GREEN** — add `current_user_id: str = Depends(get_current_user_id)` to both, and
   load the experiment with an owner predicate, matching `get_experiment_metrics`
   two functions away. `track_prediction` currently passes `experiment_id` straight to
   the service, which fetches unscoped — the route must establish ownership first.
3. Docs: record both in `SECURITY_OWNERSHIP_CHECKS.md`.

## AC4 — answered, not built
"Consider whether `track-prediction` needs to be callable by the serving path rather
than a browser session; if so it belongs on the X-API-Key production surface."

Answer: not today. Per #502 no serving path assigns or tracks a variant, so there is no
serving caller to accommodate — building an API-key surface for a caller that does not
exist would be speculative, and it is #502 that decides whether this feature ships at
all. Session auth is the correct scoping now and is strictly safer than the status quo.
Recorded on #502 so the decision is made with this in view.

## Acceptance criteria
- [ ] AC1 both endpoints require authentication
- [ ] AC2 both tenant-scoped; non-owner gets 404
- [ ] AC3 route tests assert 401 unauthenticated on each
- [ ] AC4 serving-path question answered in writing
