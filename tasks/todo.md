# Issue #776: the plan-limit test reads ADR-003's table by section order

## Problem
`_adr_limits` took the `## Decision` section and kept the first row it met per tier. The
cost tables in the same section also start their rows with the tier names, so it was
right only while the decision table came first. `_adr_prices` was fixed for this in #775.

## Plan
- [x] `tests/adr_table.py::decision_rows`: the table found by its `| Tier | Price |` header,
      read to its end. Both tests use it.
- [x] A reordered-table test for the limits, like the one the prices have.
