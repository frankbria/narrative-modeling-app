# Feature Execution Security Model

**Status**: Implemented (GH-132)
**Scope**: Feature Store (`apps/backend/app/services/feature_store_service.py`, `apps/backend/app/services/model_training/feature_engineer.py`) and Visual Feature Builder (`apps/backend/app/services/expression_evaluator.py`)

## Summary

User-provided feature definitions are **never executed as code**. A feature's
`definition_code` must be a JSON-serialized expression tree (`ExpressionNode`),
which is parsed, validated, and evaluated by the whitelist-based
`ExpressionEvaluator`. There is no `eval()`, `exec()`, or `compile()` anywhere
in the feature execution path — arbitrary code execution is impossible by
construction, not by filtering.

## History

Before GH-132, `FeatureEngineer.apply_stored_feature()` executed
`feature.definition_code` with `exec()` guarded only by pattern-based keyword
blocking. Pattern blocking is bypassable (string concatenation, `getattr`
chains, encodings), so the `exec()` call was removed entirely. In-process
sandboxes such as RestrictedPython were rejected because the execution scope
necessarily includes pandas: `pd.read_csv('/etc/passwd')` grants file access
and `pd.read_html(url)` grants network access regardless of how well the
Python language layer is restricted.

## Architecture

```
POST /features                    POST /features/{id}/apply
      │                                   │
      ▼                                   ▼
FeatureStoreService.save_feature   FeatureStoreService.apply_feature
      │                                   │
      ▼                                   ▼
parse_feature_definition()         FeatureEngineer.apply_stored_feature()
  - json.loads                            │
  - ExpressionNode.model_validate         ├─ parse_feature_definition()
  - reject anything else (422)            ├─ ExpressionEvaluator.evaluate()
                                          │    (whitelisted pandas/numpy ops only)
                                          └─ df[output_column] = result
```

Validation happens at **every boundary**:

| Boundary | Mechanism | Failure mode |
|---|---|---|
| Create (`POST /features`) | `parse_feature_definition` in `save_feature` | 422, nothing persisted |
| Update (`PUT /features/{id}`) | `parse_feature_definition` in `update_feature` | 422, nothing persisted |
| Import (`import_feature`) | Delegates to `save_feature` | 422, nothing persisted |
| Apply (`POST /features/{id}/apply`) | `parse_feature_definition` + `ExpressionEvaluator` | 422, nothing executed |

Application-time validation is retained so that legacy documents stored
before GH-132 (raw Python strings) are rejected rather than executed.

## Threat model

| Threat | Mitigation |
|---|---|
| Arbitrary code execution | No code path interprets `definition_code` as Python. It is data (JSON), parsed with `json.loads` and validated as an `ExpressionNode`. |
| File system access | No file operations in the evaluator whitelist; `open`/`pd.read_csv` are unreachable. |
| Network access | No network operations in the whitelist; `pd.read_html`/`urllib` are unreachable. |
| Module imports | No import mechanism exists in expression trees. |
| System commands | No process/OS operations in the whitelist. |
| Dunder/introspection escapes (`__class__.__bases__…`) | Expression trees have no attribute access; node values are column names, constants, or whitelisted operation/function names. |
| Keyword-filter bypasses (string assembly, encodings, `getattr` chains) | Nothing to bypass — raw strings are rejected at parse time, not scanned for keywords. |

## What the evaluator allows

`ExpressionEvaluator` (see `app/services/expression_evaluator.py`) maps
expression-tree nodes to explicit pandas/numpy calls:

- **Operations**: add, subtract, multiply, divide, modulo, power; comparisons; and/or/not
- **Math functions**: abs, log, log10, sqrt, exp, sin, cos, tan, ceil, floor
- **Statistics**: mean, median, std, min, max, sum
- **Strings**: upper, lower, trim, length
- **Dates**: year, month, day, hour, minute, weekday
- **Type/null handling**: to_numeric, to_string, fill_null, is_null
- **Conditionals**: if/then/else trees

Adding a new operation requires adding an explicit mapping in the evaluator —
there is no fallback to dynamic dispatch.

## Breaking change (legacy features)

`StoredFeature` documents created before GH-132 whose `definition_code` is raw
Python no longer execute. Applying one returns **422** with guidance to
recreate the feature using the Visual Feature Builder. This is intentional:
those documents are untrusted input and executing them is the vulnerability
this change removes.

This applies to **every** `definition_type` (`transformation`, `aggregation`,
`encoding`, `custom`). Before GH-132 all types flowed through the same
`exec()` call — there was never a separate safe path per type — so all types
now require a serialized expression tree. Group-by style aggregations are not
yet representable as expression trees; supporting them safely means adding
whitelisted, parameterized operations to the evaluator (follow-up work), not
reintroducing code execution.

Expression trees referencing operations or functions outside the whitelist
(`OperationType`/`FunctionType` enums) are rejected at save time, so a
feature that can never be applied is never persisted.

## Performance

Acceptance criterion: <10% overhead versus the previous (unsandboxed)
implementation, measured at the feature-application operation boundary
(dataset load + transformation, mirroring `apply_feature`). Enforced by
`tests/test_security/test_feature_store_execution.py::TestPerformanceOverhead`.

Notes from benchmarking (300k-row dataset, trivial multiply feature):

- End-to-end apply overhead vs the legacy exec path: within 10% (test-enforced).
- As part of this work, `ExpressionEvaluator._to_series` scalar broadcasting
  was fixed to use C-level fills instead of materializing a Python list per
  row (~30x faster on 1M rows), which benefits the Visual Feature Builder too.

## Security testing

`tests/test_security/test_feature_store_execution.py` covers:

- File system, import, system-command, and network attack vectors
- Dunder traversal and `getattr`-chain escapes
- String-assembly and encoding bypasses of keyword filters
- Side-effect assertions (sentinel file not created, module not imported)
- Malformed/legacy definitions rejected with `UnsafeFeatureDefinitionError`
- Valid expression trees applied correctly
- The <10% overhead benchmark

Run with:

```bash
cd apps/backend && uv run pytest tests/test_security/test_feature_store_execution.py -v
```

## References

- OWASP Code Injection: https://owasp.org/www-community/attacks/Code_Injection
- GH-132: Security: sandboxed execution environment for Feature Store code
- `docs/FEATURE_BUILDER.md` — Visual Feature Builder architecture
