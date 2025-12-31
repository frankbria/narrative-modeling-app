# Collective Memory System for Swarm Agents

## What is This?

A hierarchical, multi-tier memory system that enables swarm agents (AI workers) to share knowledge about the Narrative Modeling App codebase. Agents can store and retrieve specifications, code patterns, architectural decisions, and implementation insights across development sessions.

**Key Achievement**: Agents working on different parts of the codebase can leverage each other's knowledge without manual hand-offs.

---

## The Problem Solved

Without a memory system:
- ❌ Each agent re-learns code patterns
- ❌ Duplicate implementations across features
- ❌ Security patterns not shared
- ❌ Architectural decisions made multiple times
- ❌ Test patterns not leveraged
- ❌ No knowledge transfer between sessions

With this memory system:
- ✅ Agents load specifications → patterns → tests in seconds
- ✅ Consistent implementation across features
- ✅ Security patterns audited once, used everywhere
- ✅ Architectural decisions documented and reused
- ✅ Test patterns shared across team
- ✅ Knowledge persists across sessions

---

## Architecture at a Glance

### Two-Tier Storage

```
Persistent Storage (.claude-flow/memory/)
├── Specifications        (Source of truth)
├── Patterns             (Reusable code)
├── Decisions            (Architectural choices)
├── Security Patterns    (Vulnerability guidance)
└── Test Fixtures        (Quality templates)
    → Lives forever
    → Git-tracked
    → Searchable index

Ephemeral Storage (.swarm/memory.db)
├── Implementation Notes (Session progress)
├── Bug Investigations   (Problem-solving)
└── Performance Insights (Optimization data)
    → Auto-expires (7-30 days)
    → SQLite database
    → Fast queries
```

### Key Organization (Hierarchical)

```
{app}/{domain}/{artifact-type}/{identifier}

Examples:
├── frontend/components/specs/recipe-export
├── backend/api/patterns/async-bulk-operation
├── backend/services/tests/unit/dataset-service
├── shared/decisions/adr-001-authentication-strategy
└── shared/security/sql-injection-prevention
```

---

## Files in This Directory

### 1. **memory-architecture.md** (39 KB) — Complete Reference
   - Comprehensive specification of the entire system
   - All artifact types (specs, patterns, tests, decisions, security)
   - Retrieval strategies (direct, tag-based, full-text, namespace)
   - Memory synchronization patterns
   - Cross-app knowledge sharing
   - Access control and permissions
   - **Read this if**: You need to understand the complete system

### 2. **memory-quick-reference.md** (11 KB) — Fast Lookup
   - One-page cheat sheet
   - Common workflows with code
   - Tags reference
   - Storage locations
   - API quick reference
   - **Read this if**: You need to remember how to use memory

### 3. **memory-implementation-guide.md** (30 KB) — For Developers
   - Python implementation of MemoryStore class
   - Agent base class with memory integration
   - Agent registry pattern
   - Common workflow examples
   - CLI tools for memory management
   - Testing patterns
   - **Read this if**: You're implementing the memory system

### 4. **memory-index-template.md** (16 KB) — Current State & Examples
   - Template of what memory entries should exist
   - Organized by project structure (frontend, backend, mcp, shared)
   - Example entries (specification, pattern, decision, test fixture)
   - Entry creation priority order
   - Maintenance schedule
   - Health check queries
   - **Read this if**: You want to populate memory for the project

### 5. **MEMORY_SYSTEM_README.md** (This file)
   - Executive summary
   - Quick start guide
   - Integration points
   - Common questions

---

## Quick Start: Using Memory

### As an Agent (Loading Context)

```python
# 1. Load all relevant knowledge for your task
from shared.memory.store import MemoryStore

memory = MemoryStore()
context = memory.load_context(
    app="frontend",
    domain="components",
    feature="recipe-export"
)

# 2. Now you have access to:
# - context['specs']: What to build
# - context['patterns']: How similar features were built
# - context['tests']: How to test it
# - context['decisions']: Why previous choices were made

# 3. Store your progress for the team
memory.set(
    "frontend/components/notes/recipe-export-day1",
    content="Implemented dialog component, API integration pending",
    tags=["note", "implementation", "recipe-export"],
    ttl=604800  # 7 days
)
```

### As a Developer (Searching Memory)

```python
# Find similar patterns
async_patterns = memory.search(
    tags=["pattern", "async"],
    app="backend"
)

# Search by content
jwt_docs = memory.search(
    query="JWT validation"
)

# List all test fixtures in domain
fixtures = memory.list_namespace("backend/api/tests", recursive=True)
```

### Via CLI

```bash
# Search memory
python scripts/memory-cli.py search "async pattern" --tags pattern,async

# Get specific entry
python scripts/memory-cli.py get "backend/api/specs/dataset-upload"

# List namespace
python scripts/memory-cli.py list "frontend/components" --recursive

# View statistics
python scripts/memory-cli.py stats
```

---

## Memory by Artifact Type

### Specifications (`specs/`)
**What**: Feature requirements, API contracts, UI specifications
**Where**: `{app}/{domain}/specs/{feature}/`
**Example**: `backend/api/specs/recipe-export/endpoint-spec.md`
**Duration**: Never expires
**Used by**: Developers implementing features

### Patterns (`patterns/`)
**What**: Reusable code examples with documentation
**Where**: `{app}/{domain}/patterns/{pattern-name}/`
**Example**: `backend/services/patterns/async-bulk-operation/implementation.py`
**Duration**: Never expires
**Used by**: Developers building similar features

### Tests (`tests/`)
**What**: Test fixtures, test data, testing strategies
**Where**: `{app}/{domain}/tests/{test-type}/{feature}/`
**Example**: `backend/api/tests/unit/dataset-upload/test-fixtures.py`
**Duration**: Never expires
**Used by**: QA engineers and developers writing tests

### Decisions (`decisions/`)
**What**: Architectural decisions in ADR format
**Where**: `shared/decisions/adr-###-{name}/` or `{app}/decisions/`
**Example**: `shared/decisions/adr-001-authentication-strategy.md`
**Duration**: Never expires
**Used by**: Architects making design choices

### Notes (`notes/`)
**What**: Implementation progress, session logs, gotchas
**Where**: `{app}/{domain}/notes/{feature}-{session}/`
**Example**: `frontend/components/notes/recipe-export-day1`
**Duration**: 7 days (auto-expires)
**Used by**: Team coordination and knowledge transfer

### Security (`security/`)
**What**: Vulnerability findings, prevention patterns
**Where**: `shared/security/{concern}/` or `{app}/security/`
**Example**: `shared/security/sql-injection-prevention.md`
**Duration**: Never expires
**Used by**: Security reviewers and developers

---

## Integration Points

### 1. Agent Initialization
```python
# Agents load context when starting work
agent = SwarmAgent(agent_id="typescript-expert", app="frontend", domain="components")
agent.load_context(feature="recipe-export")
# Now has specs, patterns, tests, decisions in context
```

### 2. CI/CD Pipeline
```bash
# Load patterns before running tests
test_patterns=$(memory-cli get "backend/api/tests/unit" --format json)
pytest --fixtures="$test_patterns"
```

### 3. Code Review
```bash
# Review against architectural decisions
decisions=$(memory-cli search --tags "decision,backend" --format json)
coderabbit --decisions="$decisions"
```

### 4. Team Communication
- Implementation notes visible to all agents
- Patterns promoted as work is completed
- Decisions documented before coding starts

---

## Common Workflows

### Workflow 1: Implement New Feature
1. **Load Spec**: `memory.get("frontend/components/specs/feature-name")`
2. **Find Patterns**: `memory.search(tags=["pattern", "similar-feature"])`
3. **Get Test Examples**: `memory.get("frontend/components/tests/unit/similar-feature")`
4. **Store Progress**: `memory.set("frontend/components/notes/feature-name-day1", ...)`
5. **Document Decision**: `memory.set("shared/decisions/adr-feature-name", ...)`

### Workflow 2: Debug Issue
1. **Search for Similar Issues**: `memory.search(query="error message")`
2. **Document Investigation**: `memory.set("backend/api/notes/bug-investigation", ...)`
3. **Check Security Impact**: `memory.search(tags=["security"], query="affected system")`
4. **Update Pattern if Reusable**: `memory.set("backend/services/patterns/fix-pattern", ...)`

### Workflow 3: Security Review
1. **Load Security Patterns**: `memory.search(tags=["security"], app="backend")`
2. **Check Against OWASP**: Review relevant security entries
3. **Document Findings**: `memory.set("backend/security/audit-findings", ...)`
4. **Update Security Patterns**: Add new vulnerability patterns discovered

### Workflow 4: Cross-App Knowledge Sharing
1. **Discover Pattern in Backend**: `memory.get("backend/services/patterns/async-queue")`
2. **Adapt for Frontend**: Create new pattern based on backend version
3. **Register Both**: Link implementations to shared pattern
4. **Update Shared Pattern**: Document both approaches in central location

---

## Setup & Installation

### Prerequisites
- Python 3.10+ (for MemoryStore implementation)
- SQLite3 (built-in)
- Git (for version control)

### Bootstrap Memory
```bash
# 1. Initialize memory directories
mkdir -p .claude-flow/memory/{frontend,backend,mcp,shared}
mkdir -p .swarm

# 2. Create MemoryStore implementation
cp templates/shared/memory/store.py shared/memory/store.py

# 3. Create CLI tools
cp templates/scripts/memory-cli.py scripts/memory-cli.py

# 4. Populate initial entries (optional)
python scripts/bootstrap_memory.py

# 5. Verify setup
python scripts/memory-cli.py stats
```

### Configuration
Add to `.env`:
```bash
MEMORY_DB_PATH=.swarm/memory.db
MEMORY_PERSISTENT_DIR=.claude-flow/memory
MEMORY_CLEANUP_TTL=604800  # 7 days
```

---

## Team Guidelines

### Creating Memory Entries

**Always Create**:
- ✅ Feature specifications (before coding starts)
- ✅ Architectural decisions (when made)
- ✅ Reusable code patterns (when generalizing code)
- ✅ Security findings (for audit trail)

**Create When Useful**:
- ✅ Pattern used by 2+ features
- ✅ Bug has reusable solution
- ✅ Major optimization insight

**Don't Create**:
- ❌ Inline code comments (keep in code)
- ❌ Personal task lists (use .beads issues)
- ❌ Duplicate of existing entry

### Naming Conventions
- **Specs**: Noun form — `recipe-export`, `dataset-upload`
- **Patterns**: Pattern format — `use-async-data`, `database-transaction`
- **Notes**: Feature + day — `recipe-export-day1`, `ml-optimization-sprint11`
- **Decisions**: ADR format — `adr-001-authentication`, `adr-backend-002-queuing`
- **Security**: Concern-based — `sql-injection-prevention`, `jwt-security`

### Review Process
1. **Specification Review**: Tech lead approves before implementation
2. **Pattern Review**: Senior dev validates reusability
3. **Decision Review**: Architecture team approves
4. **Security Review**: Security officer validates

---

## FAQ

### Q: What happens to notes after 7 days?
**A**: They auto-expire and are cleaned up from ephemeral storage. If they're useful, promote them to patterns (persistent storage) first.

### Q: Can agents modify other agents' entries?
**A**: No. Agents can only write to their own domain. For cross-domain updates, go through tech lead or establish a team convention.

### Q: How do I search if I don't know the exact path?
**A**: Use `memory.search()` with queries and tags. Examples:
```python
memory.search(query="JWT validation")
memory.search(tags=["pattern", "async"], app="backend")
```

### Q: Where should test data live?
**A**: As persistent entries under `{app}/{domain}/tests/{test-type}/{feature}/`. Example: `backend/api/tests/unit/dataset-upload/test-fixtures.py`

### Q: Can memory entries link to each other?
**A**: Yes! Use the `metadata` field and cross-references in content. Example:
```python
memory.set(
    key="frontend/hooks/patterns/use-export",
    content="Based on backend/services/patterns/bulk-export",
    metadata={"based_on": "backend/services/patterns/bulk-export"}
)
```

### Q: What if the memory database gets corrupted?
**A**: Persistent entries (.claude-flow/memory/) are in Git. Ephemeral entries (.swarm/memory.db) can be rebuilt from scratch with `memory-cli optimize`. Run `memory-cli cleanup` periodically.

### Q: How do I migrate old memory to the new structure?
**A**: See `memory-architecture.md` Section 13 for migration guide.

---

## Next Steps

1. **Read**: Start with `memory-quick-reference.md` (5 min read)
2. **Understand**: Review `memory-architecture.md` sections 1-3 (15 min)
3. **Implement**: Follow `memory-implementation-guide.md` to build MemoryStore class
4. **Populate**: Use `memory-index-template.md` to add initial entries
5. **Train**: Share `memory-quick-reference.md` with team

---

## Monitoring & Health

### Monthly Health Check
```bash
# Check entry counts
memory-cli stats

# Find orphaned entries
memory-cli search --updated-before 90-days --tag note

# Verify database integrity
memory-cli optimize
```

### Useful Queries
```python
# Find all persistent entries
memory.search(artifact_type="spec|pattern|decision")

# Check coverage
specs = memory.search(tags=["spec"]).total_count
patterns = memory.search(tags=["pattern"]).total_count

# Find decisions without implementation
memory.search(tags=["decision"], status="pending")
```

---

## Support & Questions

- **How does X work?** → Check `memory-quick-reference.md`
- **I want to understand the full system** → Read `memory-architecture.md`
- **How do I implement this?** → See `memory-implementation-guide.md`
- **What should memory contain?** → Review `memory-index-template.md`
- **API reference?** → Section 3 of `memory-architecture.md`

---

## Summary

This memory system enables:
- **Persistent Knowledge**: Specifications, patterns, decisions live indefinitely
- **Session Context**: Implementation notes with automatic cleanup
- **Fast Retrieval**: Direct access by path or search by tag/content
- **Agent Coordination**: Shared state and knowledge transfer
- **Quality Guarantees**: Reusable patterns, test templates, security guidance

**Result**: Your swarm of agents becomes progressively smarter, building on each other's work rather than rediscovering solutions.

---

## Document Map

```
.claude-flow/
├── MEMORY_SYSTEM_README.md (you are here)
│   └── Start here: Executive summary and quick start
│
├── memory-quick-reference.md
│   └── 1-page cheat sheet for daily use
│
├── memory-architecture.md
│   └── Complete reference: All concepts, patterns, strategies
│
├── memory-implementation-guide.md
│   └── Code implementation: MemoryStore, agents, CLI
│
├── memory-index-template.md
│   └── What memory entries should exist and examples
│
└── metrics/
    └── System statistics and performance data
```

**Recommended Reading Order**:
1. This file (5 min)
2. `memory-quick-reference.md` (10 min)
3. `memory-architecture.md` sections 1-3 (15 min)
4. Implementation guide for your role (30 min)
