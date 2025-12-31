# Swarm Coordination System - User Guide

## Overview

This guide explains how to use the hook-based swarm coordination system for the Narrative Modeling App. This system complements the existing agent specifications by providing a communication protocol that prevents context contamination.

**Related Documents**:
- **Strategy**: [`../swarm-coordination-plan.md`](../swarm-coordination-plan.md) - Complete coordination strategy
- **Existing Agents**: [`../README.md`](../README.md) - Original 3-agent swarm documentation

## What's New

The hook-based coordination system adds:

1. **Communication Protocol**: Agents communicate via JSON hooks instead of TaskOutput
2. **Memory System**: Shared knowledge base (`memory/*.json`) prevents duplicate work
3. **Quality Gates**: Automated verification before PR creation
4. **Blocker Escalation**: Clear escalation path when agents get stuck

## Quick Start for SwarmLead

### 1. Receive Task from Traycer

```bash
# Task saved by user
cat prompts/sprint-12-feature-x.txt
# "Implement dataset export to CSV functionality"

# Invoke SwarmLead
./scripts/traycer-workflow.sh sprint-12-feature-x
```

### 2. Analyze Task Type

Read the coordination plan pattern matching:

| Task Description | Pattern | Action |
|-----------------|---------|--------|
| "Add UI component..." | Single-Layer (Frontend) | Spawn Frontend Specialist |
| "Create API endpoint..." | Single-Layer (Backend) | Spawn Backend Specialist |
| "Implement feature with frontend + backend" | Cross-Layer | Spawn Integration Coordinator |
| "Fix: Bug affecting multiple layers" | Bug Investigation | Spawn Integration Coordinator (debug mode) |
| "Add Redis caching" | Infrastructure | Spawn DevOps + Backend Specialists |

### 3. Check Memory for Context

```bash
# Read relevant memory files
cat .claude-flow/memory/architecture.json      # System design
cat .claude-flow/memory/api-contracts.json     # Existing endpoints
cat .claude-flow/memory/sprint-history.json    # Sprint context
```

### 4. Spawn Appropriate Agents

**Example: Cross-Layer Feature**

```bash
# Spawn Integration Coordinator
# Integration Coordinator will then spawn Frontend + Backend specialists
# and coordinate via artifact hooks
```

### 5. Monitor Progress

```bash
# Poll progress hooks (every 5 minutes)
ls -l .claude-flow/hooks/progress/

# Check for blockers
ls -l .claude-flow/hooks/blockers/

# Monitor artifacts
ls -l .claude-flow/hooks/artifacts/
```

### 6. Enforce Quality Gates

Before signaling PR ready:

```bash
# Verify all agents completed
grep -r "\"status\": \"completed\"" .claude-flow/hooks/progress/

# Verify no active blockers
[ -z "$(ls .claude-flow/hooks/blockers/)" ] && echo "No blockers"

# Verify tests passed
cat .claude-flow/hooks/progress/*testing.json | grep "100%"

# Verify coverage
grep "coverage_percentage.*[8-9][5-9]" .claude-flow/hooks/artifacts/*.json
```

## Quick Start for Agents

### Frontend Specialist

**Before Starting**:
```bash
# Read memory
cat .claude-flow/memory/architecture.json
cat .claude-flow/memory/api-contracts.json

# Copy progress template
cp .claude-flow/templates/progress-hook-template.json \
   .claude-flow/hooks/progress/task-123-frontend.json
```

**During Work**:
```bash
# Update progress every 15 minutes
# Edit .claude-flow/hooks/progress/task-123-frontend.json
{
  "task_id": "task-123",
  "agent_type": "frontend-specialist",
  "status": "in_progress",
  "progress_percentage": 45,
  "current_step": "Implementing CSV export button",
  "completed_steps": ["Created export component", "Added to dataset list page"],
  "next_steps": ["Add download logic", "Write tests"]
}
```

**On Completion**:
```bash
# Write artifact hook
cp .claude-flow/templates/artifact-hook-template.json \
   .claude-flow/hooks/artifacts/task-123-frontend.json

# List all completed work
{
  "task_id": "task-123",
  "agent_type": "frontend-specialist",
  "artifacts": [
    {
      "type": "ui_component",
      "name": "ExportButton",
      "location": "apps/frontend/components/ExportButton.tsx",
      "tests_passing": true,
      "coverage_percentage": 92
    }
  ],
  "ready_for_integration": true
}
```

**If Stuck (after 3 attempts)**:
```bash
# Write blocker hook
cp .claude-flow/templates/blocker-hook-template.json \
   .claude-flow/hooks/blockers/task-123-download-failed.json

{
  "task_id": "task-123",
  "agent_type": "frontend-specialist",
  "blocker_type": "api_integration_issue",
  "severity": "high",
  "description": "CSV download triggers CORS error from backend",
  "attempted_fixes": [
    "Verified API endpoint exists",
    "Checked CORS configuration in backend",
    "Tried alternative download method"
  ],
  "requires_agent": "backend-specialist"
}
```

### Backend Specialist

**Before Starting**:
```bash
# Read memory
cat .claude-flow/memory/architecture.json
cat .claude-flow/memory/api-contracts.json
cat .claude-flow/memory/configuration.json

# Copy progress template
cp .claude-flow/templates/progress-hook-template.json \
   .claude-flow/hooks/progress/task-123-backend.json
```

**During Work**:
- Implement `/api/datasets/{id}/export` endpoint
- Write unit tests (pytest)
- Update `memory/api-contracts.json` with new endpoint

**On Completion**:
```bash
# Write artifact hook
{
  "task_id": "task-123",
  "agent_type": "backend-specialist",
  "artifacts": [
    {
      "type": "api_endpoint",
      "path": "/api/v1/datasets/{id}/export",
      "method": "GET",
      "tests_passing": true,
      "coverage_percentage": 89,
      "location": "apps/backend/app/api/routes/datasets.py"
    }
  ],
  "ready_for_integration": true
}

# Update memory
# Edit .claude-flow/memory/api-contracts.json
# Add new endpoint specification
```

### Integration Coordinator

**Role**: Orchestrate cross-layer features

**Workflow**:
1. Read `memory/architecture.json` and `memory/api-contracts.json`
2. Design API contract for new feature
3. Update `memory/api-contracts.json` with contract
4. Spawn Frontend Specialist (provide contract)
5. Spawn Backend Specialist (provide contract)
6. Monitor `hooks/artifacts/` for both agents' completion
7. Verify contract alignment
8. Signal SwarmLead: Feature ready for testing

### Test Engineer

**Trigger**: After specialists complete work

**Workflow**:
```bash
# Read artifact hooks to know what to test
cat .claude-flow/hooks/artifacts/task-123-frontend.json
cat .claude-flow/hooks/artifacts/task-123-backend.json

# Read testing patterns
cat .claude-flow/memory/testing-patterns.json

# Run all tests
cd apps/backend && uv run pytest                    # Backend
cd apps/frontend && npm test                        # Frontend unit
cd apps/frontend && npm run test:e2e               # E2E

# Verify coverage
uv run pytest --cov=app --cov-report=term          # >85%

# Write progress hook
{
  "task_id": "task-123",
  "agent_type": "test-engineer",
  "status": "completed",
  "tests": {
    "backend": "214/214 passing",
    "frontend_unit": "87/87 passing",
    "frontend_e2e": "12/12 passing",
    "coverage": 89
  }
}
```

**If Tests Fail**:
```bash
# Try 3 times to fix
# If still failing after attempt 3:

# Write blocker hook
{
  "blocker_type": "integration_test_failure",
  "severity": "high",
  "description": "E2E test: CSV download returns 404",
  "attempted_fixes": [
    "Verified endpoint exists in backend",
    "Checked API URL in frontend",
    "Reviewed CORS configuration"
  ],
  "requires_agent": "integration-coordinator"
}
```

## Memory Management

### Who Owns What

| Memory File | Owner | Writers | Readers |
|-------------|-------|---------|---------|
| `architecture.json` | Integration Coordinator | Integration Coordinator | All agents |
| `api-contracts.json` | Backend Specialist | Backend Specialist, Integration Coordinator | Frontend Specialist, Integration Coordinator |
| `testing-patterns.json` | Test Engineer | Test Engineer | All specialists |
| `configuration.json` | DevOps Specialist | DevOps Specialist | Backend Specialist, MCP Specialist |
| `sprint-history.json` | Integration Coordinator | Integration Coordinator | All agents |
| `dependencies.json` | DevOps Specialist | DevOps Specialist | All agents |
| `mcp-tools.json` | MCP Specialist | MCP Specialist | All agents |

### When to Update Memory

**`api-contracts.json`**:
- ✅ ALWAYS update when adding/modifying API endpoints
- ✅ Include request/response schemas
- ✅ Document authentication requirements

**`architecture.json`**:
- ✅ Update when changing system design
- ✅ Update when adding new data flows
- ✅ Update when modifying component boundaries

**`testing-patterns.json`**:
- ✅ Update when discovering new test patterns
- ✅ Update when quality gates change
- ✅ Update when common issues are resolved

## Common Workflows

### Workflow 1: Simple Frontend Task

```
User: "Add loading spinner to dataset list"

SwarmLead:
  1. Analyzes: Single-layer frontend task
  2. Reads: memory/architecture.json
  3. Spawns: Frontend Specialist

Frontend Specialist:
  1. Writes: hooks/progress/task-123-frontend.json (in_progress)
  2. Implements loading spinner
  3. Writes tests (Jest)
  4. Writes: hooks/artifacts/task-123-frontend.json
  5. Updates: hooks/progress/task-123-frontend.json (completed)

SwarmLead:
  1. Reads: hooks/artifacts/task-123-frontend.json
  2. Spawns: Test Engineer

Test Engineer:
  1. Reads: hooks/artifacts/task-123-frontend.json
  2. Runs: npm test
  3. Verifies: Coverage >85%
  4. Writes: hooks/progress/task-123-testing.json (completed)

SwarmLead:
  1. Verifies all quality gates
  2. Signals: PR ready
```

### Workflow 2: Cross-Layer Feature

```
User: "Implement dataset export to CSV"

SwarmLead:
  1. Analyzes: Cross-layer (frontend + backend)
  2. Reads: memory/architecture.json, memory/api-contracts.json
  3. Spawns: Integration Coordinator

Integration Coordinator:
  1. Designs API contract: GET /api/v1/datasets/{id}/export
  2. Updates: memory/api-contracts.json
  3. Spawns: Backend Specialist (provide contract)
  4. Spawns: Frontend Specialist (provide contract)

Backend Specialist (parallel):
  1. Reads: memory/api-contracts.json
  2. Implements endpoint
  3. Writes tests
  4. Updates: memory/api-contracts.json (with implementation details)
  5. Writes: hooks/artifacts/task-124-backend.json

Frontend Specialist (parallel):
  1. Reads: memory/api-contracts.json
  2. Implements export button
  3. Writes tests
  4. Writes: hooks/artifacts/task-124-frontend.json

Integration Coordinator:
  1. Reads: hooks/artifacts/task-124-backend.json
  2. Reads: hooks/artifacts/task-124-frontend.json
  3. Verifies: API contract alignment
  4. Writes: hooks/progress/task-124-integration.json (completed)

SwarmLead:
  1. Spawns: Test Engineer (E2E tests)

Test Engineer:
  1. Runs E2E test: Click export → Download CSV → Verify content
  2. Writes: hooks/progress/task-124-testing.json (completed)

SwarmLead:
  1. Verifies all quality gates
  2. Signals: PR ready
```

### Workflow 3: Bug Investigation

```
User: "Fix: Authentication redirect loop in production"

SwarmLead:
  1. Analyzes: Cross-layer debugging
  2. Reads: memory/architecture.json (auth flow)
  3. Spawns: Integration Coordinator (debug mode)

Integration Coordinator:
  1. Uses: morph-mcp.warpgrep_codebase_search "redirect authentication"
  2. Hypothesizes: NEXTAUTH_URL mismatch
  3. Spawns: Frontend Specialist (check NextAuth config)
  4. Spawns: DevOps Specialist (check production env vars)

Frontend Specialist:
  1. Checks: apps/frontend/app/api/auth/[...nextauth]/route.ts
  2. Verifies: NEXTAUTH_URL usage
  3. Writes: hooks/artifacts/task-125-frontend.json (findings)

DevOps Specialist:
  1. Checks: Production .env
  2. Finds: NEXTAUTH_URL=http://localhost:3000 (WRONG)
  3. Fixes: NEXTAUTH_URL=https://app.narrativemodeling.com
  4. Writes: hooks/artifacts/task-125-devops.json (fix applied)

Integration Coordinator:
  1. Reads both artifact hooks
  2. Confirms: Fix resolves issue
  3. Writes: hooks/progress/task-125-integration.json (completed)

SwarmLead:
  1. Spawns: Test Engineer (verify in production)
```

## Troubleshooting

### Agent Not Writing Hooks

**Symptom**: No hooks in `hooks/progress/` or `hooks/artifacts/`

**Fix**:
1. Verify agent has hook template access
2. Check agent understands hook format
3. Provide explicit instructions: "Write progress hook to `.claude-flow/hooks/progress/<task-id>-<agent-type>.json`"

### Blocker Hook Ignored

**Symptom**: Agent wrote blocker hook but no response from SwarmLead

**Fix**:
1. Check SwarmLead is polling `hooks/blockers/`
2. Verify blocker hook naming: `<task-id>-<blocker-type>.json`
3. Manually invoke SwarmLead to read blocker

### Memory Files Outdated

**Symptom**: Agents using stale API contracts or config

**Fix**:
1. Verify agent ownership (see memory management table)
2. Add memory update to agent's artifact hook checklist
3. Implement quality gate: Verify memory updated

### Too Many Parallel Agents

**Symptom**: Context limits exceeded, agents slow

**Fix**:
1. Implement agent pooling (max 5 concurrent)
2. Sequence tasks instead of parallel
3. Use Integration Coordinator to batch work

## Best Practices

### For SwarmLead

1. **Always check memory first** before spawning agents
2. **Poll hooks regularly** (every 5 minutes for progress, immediately for blockers)
3. **Enforce quality gates strictly** - 100% pass rate required
4. **Update beads** after task completion
5. **Archive hooks** after sprint completion

### For Agents

1. **Read relevant memory before starting** work
2. **Write progress hooks every 15 minutes** or after significant steps
3. **Update memory when ownership applies** (see table)
4. **Write blocker hooks after 3 failed attempts** only
5. **Document all artifacts** in artifact hooks

### For Integration Coordinator

1. **Design API contracts first** before spawning specialists
2. **Write contracts to memory** before spawning
3. **Monitor artifact hooks** from spawned agents
4. **Verify alignment** before signaling completion
5. **Update architecture memory** when system design changes

## Advanced Topics

### Custom Hook Types

You can create custom hook types for project-specific needs:

```bash
# Example: Performance profiling hook
.claude-flow/hooks/performance/<task-id>-profile.json
{
  "task_id": "task-126",
  "agent_type": "backend-specialist",
  "metrics": {
    "p50_ms": 180,
    "p95_ms": 450,
    "p99_ms": 900
  },
  "meets_targets": true
}
```

### Hook Retention

Hooks are ephemeral - archive after sprint completion:

```bash
# Archive Sprint 12 hooks
mkdir -p .claude-flow/archive/sprint-12/
mv .claude-flow/hooks/*/*.json .claude-flow/archive/sprint-12/
```

### Memory Versioning

Track memory changes for rollback:

```bash
# Before major changes
cp .claude-flow/memory/api-contracts.json \
   .claude-flow/memory/api-contracts.json.backup-2025-12-26
```

## Integration with Existing Systems

### Traycer AI

Traycer prompts → SwarmLead via hooks:

```bash
# scripts/traycer-workflow.sh already integrated
./scripts/traycer-workflow.sh <issue-id>
# Automatically reads .claude-flow/memory/ and writes hooks
```

### Beads Issue Tracking

SwarmLead syncs with beads:

```bash
# Check for .beads
if [ -d .beads ]; then
  bd status                           # Get open issues
  # ... work happens via hooks ...
  bd close <issue-id>                # On completion
fi
```

### CodeRabbit

CodeRabbit feedback → Blocker hooks:

```bash
# If CodeRabbit suggests architecture change
{
  "blocker_type": "architecture_decision_required",
  "severity": "medium",
  "description": "CodeRabbit suggests extracting shared validation logic",
  "requires_human": true
}
```

## Summary

The hook-based swarm coordination system provides:

- **Context Efficiency**: No TaskOutput contamination
- **Clear Communication**: JSON hooks for all agent interactions
- **Quality Assurance**: Enforced quality gates before PR
- **Self-Healing**: Blocker escalation for stuck agents
- **Knowledge Sharing**: Memory system prevents duplicate work

**Key Files**:
- **Strategy**: `.claude-flow/swarm-coordination-plan.md`
- **Memory**: `.claude-flow/memory/*.json`
- **Hooks**: `.claude-flow/hooks/*/`
- **Templates**: `.claude-flow/templates/*.json`

**Next Steps**:
1. Test single-layer task pattern (Frontend Specialist)
2. Test cross-layer feature pattern (Integration Coordinator)
3. Iterate on hook schemas based on usage
4. Expand to bug investigation patterns

---

**Version**: 1.0
**Last Updated**: 2025-12-26
**Maintainer**: SwarmLead Coordinator
