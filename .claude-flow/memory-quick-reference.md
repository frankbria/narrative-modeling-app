# Memory Architecture Quick Reference

## Key Principles

- **Hierarchical Structure**: `{app}/{domain}/{artifact-type}/{identifier}`
- **Persistent + Ephemeral**: Specs/decisions live forever; notes auto-expire in 7 days
- **Search First**: Use tags and full-text when you don't know the path
- **Load Context**: Agents load relevant specs/patterns/tests when starting work

---

## Root Namespaces (Quick Map)

```
frontend/              Next.js app - UI, hooks, pages, auth
backend/               FastAPI app - APIs, services, models, ML
mcp/                   MCP server - tools, data processing
shared/                Cross-app patterns, decisions, security
```

---

## Artifact Types (7 Main Categories)

| Type | Path Pattern | TTL | Purpose | Example |
|------|-------------|-----|---------|---------|
| **Spec** | `{app}/{domain}/specs/{feature}` | Never | Feature requirements, API contracts | `backend/api/specs/dataset-upload/endpoint-spec.md` |
| **Pattern** | `{app}/{domain}/patterns/{pattern-name}` | Never | Reusable code + examples | `frontend/hooks/patterns/use-async-data/implementation.ts` |
| **Test** | `{app}/{domain}/tests/{test-type}/{feature}` | Never | Test fixtures, test data, strategy | `backend/api/tests/unit/dataset-upload/test-fixtures.py` |
| **Decision** | `shared/decisions/adr-###` or `{app}/decisions/*` | Never | Architecture decisions (ADR format) | `shared/decisions/adr-001-authentication-strategy` |
| **Note** | `{app}/{domain}/notes/{feature}` | 7 days | Session progress, implementation log | `frontend/components/notes/recipe-export-impl` |
| **Security** | `shared/security/{concern}` or `{app}/security/*` | Never | Vulnerability findings, mitigations | `shared/security/sql-injection-prevention` |
| **Archive** | `.claude-flow/memory/archives/{date}/` | Never | Historical records, old sprint notes | `.claude-flow/memory/archives/2024-11/` |

---

## Common Workflows

### 1. Start New Feature
```python
# Load all related knowledge
context = memory.load_context(
    app="frontend",
    domain="components",
    feature="recipe-export",
    include=["specs", "patterns", "tests", "decisions"]
)
```

### 2. Find Similar Code Pattern
```python
# Search by tag
patterns = memory.search(tags=["pattern", "async"], app="backend")

# Search by query
jwt_patterns = memory.search(query="JWT validation")
```

### 3. Store Implementation Progress
```python
memory.set(
    "frontend/components/notes/feature-name-impl",
    content=daily_notes,
    tags=["note", "implementation", "feature-name"],
    ttl=604800  # 7 days
)
```

### 4. Record Architectural Decision
```python
memory.set(
    "shared/decisions/adr-002-feature-approach",
    content=adr_format_content,
    tags=["decision", "accepted", "feature-name"],
    status="accepted"
)
```

### 5. Share Pattern Across Apps
```python
# Original pattern
memory.set(
    "backend/services/patterns/async-operation",
    content=pattern_code,
    tags=["pattern", "async", "shared"]
)

# Adapted for frontend
memory.set(
    "frontend/hooks/patterns/use-async-operation",
    content=adapted_code,
    tags=["pattern", "async"],
    based_on="backend/services/patterns/async-operation"
)
```

---

## Tags Cheat Sheet

**Artifact Class**:
- `spec` - Specification
- `pattern` - Reusable code pattern
- `test` - Test fixture/strategy
- `decision` - Architectural decision
- `note` - Session note
- `security` - Security pattern/finding

**Status**:
- `in-progress` - Work in progress
- `completed` - Done
- `accepted` - Decision approved
- `open` - Issue open
- `solved` - Problem solved

**Priority** (for security/bugs):
- `critical` - Must fix
- `high` - Important
- `medium` - Nice to have
- `low` - Polish

**Feature Area**:
- `auth` - Authentication
- `api` - API endpoints
- `async` - Async patterns
- `database` - Database patterns
- `export` - Export functionality
- etc.

**Test Type**:
- `unit` - Unit tests
- `integration` - Integration tests
- `e2e` - End-to-end
- `fixture` - Test fixture

---

## Storage Locations

### Persistent (Git-tracked, survives sessions)
```
.claude-flow/memory/
├── frontend/         # Frontend specs, patterns, etc.
├── backend/          # Backend specs, patterns, etc.
├── mcp/              # MCP specs, patterns, etc.
└── shared/           # Shared decisions, security, testing
```

### Ephemeral (Auto-expires, session-based)
```
.swarm/memory.db     # SQLite database (implementation notes, progress)
```

### Agent Context (Working memory)
```
.swarm/agents/{agent-id}/  # Agent-specific state
```

---

## Memory API (Python)

```python
# === READ ===
entry = memory.get("backend/api/specs/dataset-upload")
entries = memory.search(tags=["pattern", "async"])
entries = memory.search(query="JWT validation middleware")
items = memory.list_namespace("frontend/components", recursive=True)
context = memory.load_context("frontend", "components", "feature")
versions = memory.get_versions("backend/services/patterns/async-task")

# === WRITE ===
memory.set("frontend/hooks/specs/use-data", content, tags=[...])
memory.append("frontend/components/notes/progress", new_entry)
memory.update("backend/decisions/adr-001", status="accepted")
memory.move("old/path", "new/path")

# === MANAGE ===
memory.archive(older_than=timedelta(days=30), filter_tags=["note"])
memory.cleanup_expired()
memory.rebuild_index()
versions = memory.get_versions(key, limit=10)
merged = memory.merge_versions([v1, v2])
```

---

## File Organization Examples

### For a Feature
```
frontend/components/specs/recipe-export/
├── requirements.md           # What to build
├── api-contract.md          # Expected API calls
├── ui-design.md            # Component spec
└── test-plan.md            # Test scenarios

frontend/components/patterns/recipe-export-dialog/
├── implementation.tsx        # Component code
├── usage-guide.md           # How to use
└── test-example.tsx         # Example test

backend/api/specs/recipe-export/
├── endpoint-spec.md         # Route + schemas
├── validation-rules.md      # Input validation
└── error-scenarios.md       # Error handling

backend/services/patterns/bulk-export/
├── implementation.py         # Service logic
├── usage-guide.md           # How to use
└── test-example.py          # Example test
```

### For an Architecture Decision
```
shared/decisions/adr-001-authentication/
├── decision.md              # ADR format (status, context, decision, consequences)
├── implementation.md        # How it's implemented
└── alternatives.md          # Alternatives considered
```

### For Session Work
```
frontend/components/notes/recipe-export-sprint11/
├── implementation-log.md    # Daily progress (auto-expires in 7 days)
├── gotchas-and-fixes.md    # Issues + solutions
└── performance-insights.md  # Optimization findings
```

---

## Search Strategies (Examples)

### Find by Exact Path (Fastest)
```python
spec = memory.get("frontend/components/specs/recipe-export")
```

### Find Similar Patterns
```python
patterns = memory.search(tags=["pattern", "export"], app="frontend")
```

### Find All Tests in Domain
```python
tests = memory.list_namespace("backend/api/tests", recursive=True)
```

### Find by Content
```python
jwt_docs = memory.search(query="JWT validation")
```

### Find Related Decisions
```python
decisions = memory.search(
    tags=["decision"],
    related_to=["authentication", "security"]
)
```

### Find Recent Changes
```python
recent = memory.search(
    updated_after=datetime.now() - timedelta(days=1),
    app="backend"
)
```

---

## Team Guidelines

### When to Create Entries

**Always Create**:
- ✅ New feature specs (before coding)
- ✅ Architectural decisions (when made)
- ✅ Reusable patterns (when generalized)
- ✅ Security findings (for audit trail)

**Create When**:
- ✅ Pattern used by 2+ features
- ✅ Bug has reusable solution
- ✅ Major architectural insight

**Don't Create**:
- ❌ Inline comments (keep in code)
- ❌ Personal task lists (use .beads)
- ❌ Duplicate of existing entry

### Naming Conventions

**Specs**: Noun form - `recipe-export`, `dataset-upload`
**Patterns**: Pattern format - `use-async-data`, `async-task-queue`
**Notes**: Descriptor + domain - `recipe-export-implementation`, `ml-optimization-notes`
**Decisions**: ADR format - `adr-001-`, `adr-backend-001-`
**Security**: Concern-based - `sql-injection-prevention`, `jwt-security-patterns`

---

## TTL Defaults

| Category | Duration | Rationale |
|----------|----------|-----------|
| Specs | Never | Source of truth |
| Patterns | Never | Reusable knowledge |
| Tests | Never | Quality reference |
| Decisions | Never | Historical record |
| Implementation Notes | 7 days | Session context |
| Bug Investigations | 4 days | Problem-solving |
| Performance Benchmarks | 30 days | Trend tracking |

---

## Integration Points

### Agent Initialization
```python
agent = SwarmAgent(role="typescript-expert", app="frontend", domain="components")
agent.load_context(feature="recipe-export")
# Now has access to all specs, patterns, tests, decisions
```

### CI/CD Pipeline
```bash
# Load test patterns before running tests
test_patterns=$(memory-cli get "backend/api/tests/unit" --format json)

# Use patterns in test execution
pytest --fixtures="$test_patterns" tests/
```

### Code Review
```bash
# Load related decisions before review
decisions=$(memory-cli search --tags "decision,backend,api" --format json)

# Review against decision context
coderabbit --decisions="$decisions"
```

---

## Troubleshooting

### "Entry not found"
→ Check namespace spelling: `backend` not `backend-app`
→ Use search instead: `memory.search(query="...", app="backend")`

### "Permission denied"
→ Agents can only write to their own domain
→ Ask tech lead to write cross-domain content

### "Search too slow"
→ Use `get()` with exact path (fastest)
→ Narrow search with app/domain filter
→ Run `memory-manager optimize`

### "Too many results"
→ Add more tag filters
→ Narrow namespace: `backend/api/` not `backend/`
→ Use `limit` parameter

---

## Useful Commands

```bash
# List memory statistics
memory-cli stats

# Search memory
memory-cli search --query "async pattern" --app backend

# Get specific entry
memory-cli get "backend/api/specs/dataset-upload"

# List namespace
memory-cli list "frontend/components" --recursive

# Cleanup old notes
memory-cli cleanup --older-than 30 --tag note

# Rebuild indexes
memory-cli optimize
```

---

## See Also

- Full documentation: `.claude-flow/memory-architecture.md`
- Agent integration guide: `.claude-flow/agent-memory-integration.md` (coming soon)
- Example workflows: `.claude-flow/memory-examples.md` (coming soon)
