# Issue #683: audit the remaining consumers of the mocked dataset

## What the audit found
| consumer | what it did | outcome |
|---|---|---|
| `test_ai_analysis.py`, summarize (3 tests) | `MagicMock` dataset, `save = AsyncMock()`, stubbed summarizer returning an invented shape | hid #981 (the summary failed for a real dataset and the failure was saved). Replaced there. |
| `test_ai_summary.py`, success path | `UserData.save` patched out | hid #983 (the stale save that undid processing). Replaced there. |
| `test_ai_analysis.py`, analyze (5 tests) | `MagicMock` dataset behind a patched lookup, under an id no lookup could match | the route works, but a rule-based fallback was charged as an AI call. Fixed and replaced here. |
| `test_model_training.py`, `POST /ml/train` (2 tests) | `MagicMock` behind a patched lookup | no bug. Converted to a real document here, plus the foreign-dataset case. |
| `test_transformations_integration.py` (3 tests) | its own mock behind a patched lookup | kept: they test the response shape; the lookups have real-document tests in `test_object_id_lookups.py`. |
| `test_ai_summary.py`, the other paths | patched `UserData.get` | kept: unit tests of "already summarised", "not found" and "model failed", none of which writes. |
| `test_secure_upload.py`, `test_chunked_upload_flow.py`, `integration/test_upload_workflow.py` | mention the fixture in comments only | not consumers. |

## Plan
- [x] RED: `/ai/analyze` with nothing stubbed leaves `ai_calls` at 0.
- [x] The route releases its unit when the answer is the rule-based fallback.
      `analyze_with_ai` was at cc 10: `_processed_upload` (shared with summarize), `_analysis`.
- [x] Real-document tests for analyze replace the five mocked ones.
- [x] The two mocked `/ml/train` route tests use a real document.
- [x] `conftest.mock_user_data` has no consumer left and is removed.
