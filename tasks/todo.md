# Issue #202 — Vectorize batch `_predict_chunk` inference

Pure performance. `_predict_chunk` currently runs transform/predict/predict_proba
once **per row** (~3000 sklearn calls per 1000-row chunk). Vectorize to ~3 calls/chunk.

## Plan (adapted from CodeRabbit comment)

1. Extract the current row-by-row loop verbatim → `_predict_chunk_sequential`
   (the fallback that preserves per-row error isolation).
2. New `_predict_chunk_vectorized`: one `transform`, one `predict`, one
   `predict_proba` over the whole chunk; assemble per-row dicts by indexing into
   the arrays. **Keep the existing batched `_attach_explanations` flow (#80)** —
   do NOT revert explanations to per-row `explain()` (CodeRabbit Task 6 is stale).
3. `_predict_chunk` = try vectorized; on any chunk-level exception, fall back to
   `_predict_chunk_sequential` (preserves the `test_predict_chunk_records_per_row_errors`
   semantics where one bad row doesn't fail the chunk).

## Tests (TDD)
- predict/predict_proba called **once** per chunk (not per row).
- vectorized failure falls back to sequential (per-row error record preserved).
- existing 6 `_predict_chunk` tests stay green (confidence, low-conf, interval, explanation).

## Out of scope
- No new schema/fields, no API change, no behavioral change to outputs.
