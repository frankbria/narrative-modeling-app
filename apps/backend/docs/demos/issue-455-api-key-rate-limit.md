# Issue #455 — a tenant can no longer disable rate limiting on the paid serving surface

*2026-09-08T02:29:15Z*

API-key creation accepted a caller-supplied `rate_limit` verbatim. Both rate-limit stores read `limit <= 0` as "no enforcement", and the per-key bucket on `/production/v1/models` is the *only* limiting on that surface — so `rate_limit=0` removed the control outright on the paid serving path.

This demo drives the **real** FastAPI app (httpx over ASGITransport) against a **real** MongoDB, behind the **real** rate-limit middleware and store. Nothing is mocked: every status code below is one FastAPI produced, and every `rate_limit` value is re-read from Mongo.

Rate limiting is disabled in the test environment (`CLAUDE.md`), so the middleware is constructed with `enabled=True` — otherwise the 429s below would be vacuous.

The whole run, end to end. Each section maps to an acceptance criterion from the issue.

```bash
MONGODB_URI=mongodb://localhost:27017 PYTHONPATH=. uv run python scripts/demo_issue_455.py 2>/dev/null
```

```output

=== Plan ceilings (AC2: single source of truth in plans.py) ===
  free api_key_rate_limit                      1000
  pro api_key_rate_limit                       10000
  enterprise api_key_rate_limit                60000
  all finite (UNLIMITED would re-open the hole) True

=== AC1: rate_limit=0 is refused at the door ===
  POST api-keys rate_limit=0                   HTTP 422
  POST api-keys rate_limit=-1                  HTTP 422

=== AC1/AC2: an absurd value is clamped to the plan ceiling ===
  POST api-keys rate_limit=10,000,000          HTTP 200
  response rate_limit                          1000
  stored in MongoDB                            1000

=== A ceiling, not an override: a lower ask is honoured ===
  POST api-keys rate_limit=5 -> stored         5

=== Defence 1: a LEGACY row already at 0 is still limited ===
  legacy row rate_limit in MongoDB             0
  3 requests on the paid serving surface       [200, 429, 429]
  before the fix this would have been          [200, 200, 200] (unlimited)

=== Defence 2: a plan downgrade re-clamps existing keys ===
  key minted while on ENTERPRISE               60000
  after the cancellation webhook               1000

=== AC3: the audit script sees this database's damage ===

  $ fix_api_key_rate_limits.py read-only  (exit 1)
    api_keys scanned:              4
    rate_limit <= 0 (UNLIMITED):   1
    rate_limit missing/non-numeric: 0
    rate_limit > 60000 (ceiling):   0
    
    Out-of-range rows found. Re-run with --apply to correct them.

  $ fix_api_key_rate_limits.py --apply  (exit 0)
    api_keys scanned:              4
    rate_limit <= 0 (UNLIMITED):   1
    rate_limit missing/non-numeric: 0
    rate_limit > 60000 (ceiling):   0
    
    raised to 1000:  1
    lowered to 60000: 0
    still out of range:  0
  
  legacy row after --apply                  1000

All six acceptance criteria demonstrated against the real app.
```

The one line that carries the whole issue is `3 requests on the paid serving surface  [200, 429, 429]` — a key stored at `rate_limit=0`, the exact state #455 describes, now gets one request per window instead of unlimited throughput.

That is not merely "the test passes": mutating the fix makes it fail. Neutering the clamp and the re-clamp filter breaks three tests.

```bash
cp app/billing/api_keys.py /tmp/ak.bak
sed -i "s/    return min(requested, ceiling)/    return requested  # MUTANT/" app/billing/api_keys.py
sed -i "s|{\"user_id\": user_id, \"rate_limit\": {\"\$gt\": ceiling}},|{\"user_id\": \"no-such-user\"},  # MUTANT|" app/billing/api_keys.py
PYTHONPATH=. uv run pytest tests/test_billing/test_api_key_clamp.py tests/test_api/test_production.py -q -k "clamp or APIKeyManagement" 2>/dev/null | grep -E "^FAILED"
cp /tmp/ak.bak app/billing/api_keys.py
```

```output
FAILED tests/test_billing/test_api_key_clamp.py::TestClampUserApiKeys::test_lowers_keys_above_the_new_ceiling
FAILED tests/test_billing/test_api_key_clamp.py::TestWebhookReclampsOnDowngrade::test_subscription_downgrade_lowers_existing_keys
FAILED tests/test_api/test_production.py::TestProductionAPIKeyManagement::test_create_list_and_revoke_api_key
FAILED tests/test_api/test_production.py::TestProductionAPIKeyManagement::test_create_api_key_clamps_to_plan_ceiling
```

Four tests fail when the fix is removed, and the file is restored immediately after (the diff below is empty, confirming it).

```bash
git diff --stat app/billing/api_keys.py; echo "(empty = restored)"
```

```output
(empty = restored)
```

And the full PR gate suite is green with the change in place.

```bash
PYTHONPATH=. uv run pytest tests/ -m "not integration and not performance" -q 2>/dev/null | tail -3; echo "pytest exit: ${PIPESTATUS[0]}"
```

```output
SKIPPED [1] tests/integration/test_full_workflow.py:193: Complex PII workflow test needs refactoring
SKIPPED [1] tests/integration/test_full_workflow.py:245: Error handling test needs refactoring for new API structure
SKIPPED [1] tests/test_middleware/test_api_version.py:131: No deprecated versions exist yet
pytest exit: 0
```

The suite prints skip reasons rather than a `N passed` line — the repo conftest suppresses the summary on full runs, so the exit code is the signal (`pytest exit: 0`).

## Acceptance criteria

| AC | Evidence above |
|----|----------------|
| 1. `rate_limit` not accepted, **or** clamped to the plan ceiling — state which | **Clamped.** `POST rate_limit=10,000,000` → stored `1000` |
| 2. `0` rejected or normalized; ceiling from `plans.py` | `HTTP 422` for `0` and `-1`; ceilings read from `api_key_rate_limit_ceiling` |
| 3. Existing rows found and corrected; count recorded | Audit script: `rate_limit <= 0: 1` → `raised to 1000: 1` → `still out of range: 0` |
| 4. A test asserts `rate_limit=0` does not get unlimited throughput | `[200, 429, 429]` through the real middleware; 4 tests fail when the fix is mutated |
| 5. Test must not pass vacuously given limiting is off in test env | Middleware constructed `enabled=True`; the mutation run proves the assertions bite |

## Not demonstrated here

**AC3 against the real cluster.** The count above is from a throwaway demo database. The Atlas credentials in the local `.env` are rejected (`bad auth`) — the failure mode issue #552 describes — so the production/staging count still needs one operator run of `scripts/fix_api_key_rate_limits.py` at deploy time.

**Legacy `0` rows are bricked, not just limited.** Flooring at 1 means 1 request/hour until the repair script runs. Fail-closed is correct, but the script belongs in the same deploy.
