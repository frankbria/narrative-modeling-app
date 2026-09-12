# Issue #563 — [P3.9] [security] GET /api/v1/ai/health is unauthenticated and does outbound work per request

Plan source: self-authored. Approved autonomously — AC1 offers "require auth" or "keep public + cache"; every sibling route in the router is authenticated and the MCP server is deployed nowhere (#508), so require auth. No fork.

## Findings
- `ai_analysis.py::check_mcp_health` is the only handler in its router without `Depends(get_current_user_id)`; the router is mounted under `/api/v1/ai` without router-level dependencies.
- Each anonymous call runs `mcp_service.check_health()` — an outbound request to an internal component.
- Liveness/readiness probes live in `health.py` (`/health`, `/health/ready`, #503 owns the readiness outbound-work question). MCP is not a readiness dependency of this app, so the check does not belong beside them.

## Design
1. Add `current_user_id: str = Depends(get_current_user_id)` to `check_mcp_health` (unused id is fine — it is the gate). Docstring says why it is authenticated.
2. Test (AC3): unauthenticated → 401; authenticated → 200 with `mcp_available` bool (MCP health stubbed). Plus keep the #450 auth-sweep test green.

## Steps
- [ ] RED tests
- [ ] dependency on the route
- [ ] gate → PR → demo → CI → merge
