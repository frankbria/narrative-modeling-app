# Issue #221 — Broaden integration test coverage in CI gate

**Goal:** S3/upload/OpenAI integration coverage runs reliably in the required CI
gate, with **no silent skips for missing services**.

## Root cause
- LocalStack is provisioned *best-effort* in `backend-integration` → S3 tests skip silently if it fails.
- `test_openai_fixtures.py` lacks the `integration` marker → excluded from the gate.
- `s3_client` / `redis_client` / roundtrip skip-on-missing-service → silently green even when a service is down.

## Changes (minimal)
1. `tests/conftest.py` — add `require_service(reason)`: skips normally, but
   `pytest.fail`s when `CI_REQUIRE_SERVICES` is truthy. Route `redis_client` +
   `s3_client` "not available" skips through it.
2. `tests/integration/test_prediction_roundtrip.py` — route its
   `pytest.skip("LocalStack S3 not available")` through `require_service`.
3. `tests/integration/test_openai_fixtures.py` + `test_upload_workflow.py` — add
   module-level `pytestmark = pytest.mark.integration` (OpenAI suite is fully
   mocked/deterministic; upload suite's 3 runnable tests cover real
   POST /datasets/upload + listing + auth). The upload module's `@pytest.mark.skip`
   tests are fixture/endpoint debt and stay skipped (not service skips).
4. `.github/workflows/ci.yml` (`backend-integration`):
   - Make LocalStack a **hard requirement** (fail if not healthy; drop best-effort warning).
   - Add `CI_REQUIRE_SERVICES: true` to the test env.
5. Docs — `ci.yml` header + `TEST_INFRASTRUCTURE.md` (LocalStack now required in
   gate; mocked-OpenAI path in gate; `CI_REQUIRE_SERVICES` semantics).

## Out of scope (ponytail — AC says "for missing services")
- Hardcoded `@pytest.mark.skip` tests in `test_upload_workflow.py` /
  `test_full_workflow.py` / `test_ml_workflow_e2e.py` — skip for missing
  fixtures / unimplemented endpoints (refactoring debt), not missing services.
  (The *runnable* upload tests ARE promoted; only the fixture-debt ones stay skipped.)
- Pulling `tests/test_integration/` into the gate.

## Verification
- With LocalStack + Mongo up and `CI_REQUIRE_SERVICES=true`: S3 + OpenAI +
  roundtrip suites **pass** (not skip).
- With S3 endpoint unreachable + `CI_REQUIRE_SERVICES=true`: S3 tests **fail**
  (not skip) — proves the no-silent-skip guard works.
