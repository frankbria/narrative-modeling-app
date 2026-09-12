# Issue #559 — [P3.8] [security] create_transformation_version trusts its callers to have checked ownership

Plan source: self-authored. No architectural fork; approved autonomously.

## Design
- Resolve the parent through `self.get_version(parent_version_id, mark_accessed=False, user_id=user_id)` — the existing opt-out primitive — so a parent owned by another user is refused exactly like a missing one (`NotFoundError`, no existence oracle) and the refusal is WARNING-logged the same way.
- Opt-out for genuine internal operations: `verify_parent_ownership: bool = True`; `False` passes `user_id=None` into `get_version`, which audit-logs the bypass. Both callers keep the default (redundant-by-design on the route, which pre-verifies).
- `mark_accessed=False`: deriving a child must not count as a read of the parent.

## Steps
1. [ ] Tests first (service-level, existing mock shape): foreign parent → `NotFoundError`, nothing uploaded/inserted, warning logged; own parent → proceeds; bypass → proceeds and logs the bypass.
2. [ ] Implement; run versioning/transformation/history/route suites.
3. [ ] Docs: `docs/SECURITY_OWNERSHIP_CHECKS.md` lists the method; CLAUDE.md version-ownership bullet gains one clause.

## Acceptance criteria
- [ ] AC1 parent ownership asserted, opt-out shape with audit log on bypass
- [ ] AC2 service test: foreign parent refused
- [ ] AC3 both callers unchanged and green
- [ ] AC4 doc lists the method
