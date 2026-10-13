# Issue #981: the AI summary fails for a dataset with fewer than two numeric columns

## Problem
`POST /ai/summarize/{id}` on a really processed dataset whose statistics hold
`correlation_matrix: null` answers 200 with "Failed to generate dataset summary", the
exception's text in `issues`, and saves that as the dataset's `aiSummary`. Found while
auditing the mocked tests for #683: the route's tests used a `MagicMock` dataset.

## Plan
- [x] RED: a real document carrying the captured `/data/process` result; each nullable key
      as null; a forced failure; a write landing while the summary is made.
- [x] `_stored(source, key, default)`: a stored null reads like a missing key. Every read
      of schema, statistics and quality report uses it. `_extract_statistical_highlights`
      (cc 9) and `_prepare_context` (cc 8) are split on the way.
- [x] The request takes each part as a dict or nothing; the model-instance branches had
      no caller.
- [x] A failed summary: `internal_error_message`, exception to the log.
- [x] The route (cc 8): `_summary_request`, `_settle`. A failed summary is returned, not
      stored; the write sets only `aiSummary`.
- [x] The three mocked summarize tests go; the lookup test asserts 200, not "not 404".
