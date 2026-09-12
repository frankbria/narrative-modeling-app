# Issue #637 — [P2.45] [security] data-issues handlers return raw exception text in 200 {success: false} bodies

Plan source: self-authored. Approved autonomously — no architectural fork (AC1 offers raise-or-generic; generic keeps #471's ai_calls accounting intact, so generic it is).

## Findings
- `data_issues.py`: `error=str(e)` in the `except Exception` of detect, preview-fix, apply-fix (two excepts: domain `ValidationError|OperationError` with a user-facing `.message`, then generic), batch-fix. `get_dataset_issues` / `get_issue_history` raise `HTTPException(500, detail=str(e))` — already sanitised by #269's handler (5xx detail is replaced), so they only need the redundant text dropped.
- `fix_suggestion_engine.preview_fix` returns `{"success": False, "error": str(e)}` and the route copies it into the 200 body — same leak one layer down.
- `transformations.py`: same shape in preview, apply, pipeline/apply, validate (`errors=[str(e)]`), auto-clean. `OperationError.message` branches are domain errors and stay.
- Raising instead would turn a detect failure into a 5xx the refund middleware refunds wholesale — including an AI call the analyzer actually sent — so the 200 `{success:false}` contract stays and the *message* changes (AC2).
- Frontend consumers render `result.error` verbatim (`BatchFixPanel`) or only branch on `success`; a fixed sentence with a reference id reads fine (AC3). `test_transformations_integration.py:768` asserts the raw S3 text and must move to the new contract.

## Design
1. `app/middleware/error_handlers.py`: `internal_error_message(what: str) -> str` → `"<what> failed because of an internal error (reference <request id>)"`, reading `request_id_ctx`; the caller logs the exception with `logger.exception`.
2. Replace every `error=str(e)` / `errors=[str(e)]` in a generic `except Exception` in `data_issues.py` and `transformations.py`; `fix_suggestion_engine.preview_fix` returns a fixed message too (it has no request; the route wraps it).
3. Tests: force `RuntimeError("s3://secret-bucket/key: boom")` in each handler's service call; assert 200, `success is False`, no "secret-bucket"/"boom" in the body, the reference id equals the `X-Request-ID` response header; keep `test_a_sent_request_stays_charged_when_the_service_fails_after_it` green (AC2).

## Steps
- [x] RED tests
- [x] helper + route/engine changes (+ engine, fix-engine and bulk-service catch-alls after review)
- [x] gate → PR #643 → demo → CI → merge
