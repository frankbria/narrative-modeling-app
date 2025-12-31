# Collective Memory Architecture for Swarm Agents

## Overview

This document defines the hierarchical key structure and patterns for organizing collective memory across swarm agents in the Narrative Modeling App. The memory system enables agents to share knowledge about code structure, test patterns, architectural decisions, and implementation insights across sessions.

**Key Principle**: Memory is organized hierarchically by concern (app, domain, artifact type), enabling fast retrieval and preventing cross-contamination of unrelated knowledge.

---

## 1. Key Naming Conventions

### Structure Format
```
{app}/{domain}/{artifact-type}/{sub-domain}/{identifier}
```

### Root Namespaces

```
frontend/                  # Next.js app (TypeScript)
  auth/                    # Authentication concerns
  components/              # UI components
  pages/                   # Page patterns
  hooks/                   # Custom React hooks
  utils/                   # Utility functions
  integration/             # API integration patterns

backend/                   # FastAPI app (Python)
  auth/                    # Authentication/authorization
  api/                     # API endpoints
  services/                # Business logic services
  models/                  # Database models
  schemas/                 # Pydantic schemas
  processing/              # Data processing pipelines
  ml/                      # ML/AI model training

mcp/                       # FastMCP server (Python)
  tools/                   # Tool implementations
  processing/              # Data processing
  integration/             # External service integrations

shared/                    # Cross-app knowledge
  patterns/                # Common design patterns
  security/                # Security patterns (auth, encryption)
  testing/                 # Testing strategies and fixtures
  deployment/              # Deployment patterns
  monitoring/              # Observability patterns
```

---

## 2. Memory Patterns by Artifact Type

### 2.1 Specifications (`specs/`)

**Location**: `{app}/{domain}/specs/{feature-name}`

**Purpose**: Store feature specifications, API contracts, and architectural decisions

**Structure**:
```
frontend/components/specs/recipe-export
├── requirements.md          # Feature requirements
├── api-contract.md         # Expected API calls
├── ui-design.md           # Component behavior & props
└── test-plan.md           # Test scenarios

backend/api/specs/dataset-upload
├── endpoint-spec.md        # Route definition, request/response
├── schema-definition.md    # Pydantic models
├── validation-rules.md     # Input validation
└── error-scenarios.md      # Error handling
```

**Content Example**:
```markdown
# Recipe Export Feature Specification

## API Endpoint
- POST `/api/recipes/{recipeId}/export`
- Request: { format: 'json' | 'csv', includeMetadata: boolean }
- Response: { downloadUrl: string, expiresAt: timestamp }

## Status Codes
- 200: Successful export
- 400: Invalid format
- 404: Recipe not found
- 409: Export in progress

## Testing Scope
- Valid format selection
- Missing parameters
- Permission validation
- Large dataset handling
```

**Memory Operations**:
```python
# Store specification
memory.set(
    "frontend/components/specs/recipe-export/requirements",
    content=spec_content,
    tags=["spec", "recipe-export", "v2.0"]
)

# Retrieve for implementation
spec = memory.get("frontend/components/specs/recipe-export")
```

### 2.2 Code Patterns (`patterns/`)

**Location**: `{app}/{domain}/patterns/{pattern-name}`

**Purpose**: Store reusable code patterns, architectural examples, and implementation templates

**Structure**:
```
frontend/hooks/patterns/use-async-data
├── implementation.ts      # Pattern code with annotations
├── usage-guide.md        # How to use the pattern
└── test-example.tsx      # Example test implementation

backend/services/patterns/database-transaction
├── implementation.py      # Pattern code
├── usage-guide.md        # How to use in services
└── test-example.py       # Integration test template
```

**Content Example**:
```typescript
// frontend/hooks/patterns/use-async-data/implementation.ts
/**
 * Pattern: Async data hook with error handling and cache
 *
 * Key Features:
 * - Loading states
 * - Error boundaries
 * - Automatic retry on failure
 * - Cache invalidation
 *
 * Usage:
 * const { data, loading, error } = useAsyncData(fetchFn, dependencies)
 */
export function useAsyncData<T>(
  fetchFn: () => Promise<T>,
  deps: DependencyList = []
): AsyncDataState<T> {
  // Implementation details...
}
```

**Memory Operations**:
```python
# Store pattern
memory.set(
    "frontend/hooks/patterns/use-async-data",
    content=pattern_code,
    tags=["pattern", "hooks", "async", "react"],
    ttl=None  # Persistent
)

# Search patterns by tag
patterns = memory.search(tags=["pattern", "async"])

# Retrieve specific pattern
pattern = memory.get("frontend/hooks/patterns/use-async-data/implementation.ts")
```

### 2.3 Test Patterns (`tests/`)

**Location**: `{app}/{domain}/tests/{test-type}/{feature-name}`

**Purpose**: Store test fixtures, test data, and testing strategies

**Structure**:
```
backend/api/tests/unit/dataset-upload
├── test-fixtures.py       # Sample data and mocks
├── test-strategy.md       # Testing approach
└── test-patterns.py       # Reusable test patterns

frontend/components/tests/e2e/recipe-export
├── test-fixtures.json     # Mock API responses
├── page-objects.ts        # Playwright helpers
└── test-scenarios.md      # E2E test cases
```

**Content Example**:
```python
# backend/api/tests/unit/dataset-upload/test-fixtures.py
"""
Test Fixtures for Dataset Upload API

Strategy:
- Unit tests: Mock S3 and database
- Integration tests: Real MongoDB, real S3 (test bucket)
- E2E tests: Full workflow in staging environment
"""

@pytest.fixture
def sample_csv_file():
    """Sample valid CSV for upload testing"""
    return {
        "name": "test.csv",
        "content": "col1,col2,col3\n1,2,3\n4,5,6",
        "size": 1024,
        "mime_type": "text/csv"
    }

@pytest.fixture
def dataset_service_with_mocks(mocker):
    """DatasetService with mocked external dependencies"""
    mocker.patch('app.services.S3Service')
    mocker.patch('app.db.models.Dataset')
    return DatasetService()
```

**Memory Operations**:
```python
# Store test fixtures
memory.set(
    "backend/api/tests/unit/dataset-upload/test-fixtures",
    content=fixtures_code,
    tags=["test", "fixture", "dataset", "unit"]
)

# Retrieve test pattern for similar feature
fixture = memory.get("backend/api/tests/unit/dataset-upload/test-fixtures")

# Search for test patterns in domain
patterns = memory.search(
    path_pattern="backend/api/tests/*",
    tags=["test"]
)
```

### 2.4 Decisions & Architecture (`decisions/`)

**Location**: `shared/decisions/{decision-id}` or `{app}/decisions/{local-decision}`

**Purpose**: Record architectural decisions, trade-offs, and rationale (Architecture Decision Records)

**Structure**:
```
shared/decisions/adr-001-authentication-strategy
├── decision.md            # The decision record
├── implementation.md      # How it's implemented
└── alternatives.md        # Alternatives considered

backend/decisions/adr-backend-001-mongodb-indexing
├── decision.md
└── implementation-guide.md
```

**Content Example** (ADR Format):
```markdown
# ADR-001: Authentication Strategy

## Status
ACCEPTED (implemented in Sprint 11)

## Context
The app requires multi-provider authentication (Google, GitHub) with role-based access control.

## Decision
Implement NextAuth.js v5 with MongoDB adapter for frontend, enforce backend validation with JWT tokens.

## Consequences
- Pros: Industry standard, secure by default, provider flexibility
- Cons: Additional dependency, session management overhead
- Risk: Provider API changes require adapter updates

## Implementation Details
- Frontend: NextAuth configuration in `apps/frontend/auth.ts`
- Backend: JWT validation middleware in `apps/backend/app/middleware/auth.py`
- Database: User roles stored in MongoDB User collection

## Related Patterns
- `backend/auth/patterns/jwt-validation`
- `frontend/auth/specs/oauth-flow`
```

**Memory Operations**:
```python
# Store decision
memory.set(
    "shared/decisions/adr-001-authentication-strategy",
    content=adr_content,
    tags=["decision", "architecture", "auth", "accepted"]
)

# Retrieve decision by status
decisions = memory.search(
    tags=["decision", "accepted"]
)

# Track decision lifecycle
memory.update(
    "shared/decisions/adr-001-authentication-strategy",
    status="accepted",
    implemented_date="2024-11-15"
)
```

### 2.5 Implementation Notes (`notes/`)

**Location**: `{app}/{domain}/notes/{feature-name}`

**Purpose**: Store implementation progress, gotchas, and lessons learned (short-lived, contextual)

**Structure**:
```
frontend/components/notes/recipe-export-feature
├── implementation-log.md      # Day-by-day progress
├── gotchas-and-fixes.md       # Issues discovered & solutions
└── performance-insights.md    # Optimization findings

backend/services/notes/ml-pipeline-refactor
├── refactoring-progress.md
├── performance-benchmarks.md
└── test-coverage-analysis.md
```

**Content Example**:
```markdown
# Recipe Export Implementation Notes

## Session 1: Components & API Integration
- ✅ Created ExportDialog component with format selector
- ✅ Integrated with backend export endpoint
- ⚠️ GOTCHA: File download timing issue in Firefox
  - Solution: Added 500ms delay before cleanup
  - Related to: browser.cleanup() race condition
- ⏸️ TODO: Handle large file streaming (>100MB)

## Performance Insights
- Initial render: 850ms → 280ms (after memoization)
- File generation: 2.3s for 50MB CSV
- Network: Consider chunked upload for production

## Test Status
- Unit: 12/12 passing
- E2E: 8/8 passing
- Coverage gap: Error retry logic not tested
```

**Memory Operations** (Short-lived):
```python
# Store implementation notes with TTL
memory.set(
    "frontend/components/notes/recipe-export-feature/implementation-log",
    content=log_content,
    tags=["note", "implementation", "in-progress"],
    ttl=86400 * 7  # 7 days
)

# Update progress
memory.append(
    "frontend/components/notes/recipe-export-feature/implementation-log",
    new_entry="## Session 2: Testing & Polish"
)
```

### 2.6 Vulnerabilities & Security (`security/`)

**Location**: `shared/security/{vulnerability-id}` or `{app}/security/{concern}`

**Purpose**: Track security patterns, vulnerability findings, and mitigations

**Structure**:
```
shared/security/cve-findings/
├── openssl-vulnerability.md
├── sql-injection-patterns.md
└── xss-prevention.md

backend/security/auth-validation
├── input-validation-rules.md
└── jwt-security-patterns.md
```

**Content Example**:
```markdown
# SQL Injection Prevention Pattern

## Vulnerability Type
Code Injection (SQL)

## Location
All database queries in `app/services/*.py`

## Mitigation Strategy
1. Use Beanie ODM parameterized queries (automatic)
2. Validate input length and format before queries
3. Sanitize user input with Pydantic models
4. No string concatenation in queries

## Safe Pattern
```python
# ✅ SAFE: Uses Beanie ODM
dataset = await Dataset.find_one(Dataset.name == user_input)

# ❌ UNSAFE: String concatenation
query = f"SELECT * FROM datasets WHERE name = '{user_input}'"
```

## Test Coverage
- Unit test: `test_injection_prevention` (backend/tests/test_security/)
- E2E: Malicious input tests in integration suite

## Review Checklist
- [ ] All queries use parameterized format
- [ ] Input validation before query execution
- [ ] Code reviewed by security-aware dev
```

**Memory Operations**:
```python
# Store security finding
memory.set(
    "shared/security/sql-injection-prevention",
    content=security_content,
    tags=["security", "vulnerability", "sql-injection", "critical"],
    priority="high"
)

# Search for security concerns in domain
vulnerabilities = memory.search(
    tags=["security", "critical"],
    app="backend"
)
```

---

## 3. Storage Patterns by Artifact Type

### 3.1 Persistent Storage (`.claude-flow/memory/`)

**Use for**: Specifications, architecture decisions, patterns, security guidelines

**Characteristics**:
- No TTL (lives indefinitely)
- Versioned (track changes)
- Searchable by tags and content
- Git-tracked for visibility

**Directory Structure**:
```
.claude-flow/memory/
├── frontend/
│   ├── auth/
│   │   ├── specs/
│   │   │   └── oauth-integration.md
│   │   └── patterns/
│   │       └── use-auth-context.ts
│   ├── components/
│   │   ├── specs/
│   │   └── patterns/
│   └── hooks/
├── backend/
│   ├── auth/
│   ├── api/
│   ├── services/
│   └── ml/
├── mcp/
├── shared/
│   ├── decisions/
│   ├── patterns/
│   ├── security/
│   └── testing/
└── index.json
```

**File Format**:
- Markdown (`.md`) for specifications, decisions, guides
- Code files (`.ts`, `.py`, `.tsx`) for patterns and examples
- JSON (`.json`) for structured data (fixtures, schemas)
- YAML (`.yaml`) for configuration examples

### 3.2 Ephemeral Storage (`.swarm/memory.db`)

**Use for**: Implementation progress, session notes, temporary insights

**Characteristics**:
- TTL-based automatic expiration (default: 7 days)
- Binary database format (SQLite)
- Fast in-memory queries
- Automatically garbage collected

**Schema**:
```sql
-- memory entries
CREATE TABLE memory (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,          -- e.g., "frontend/components/notes"
    key TEXT NOT NULL,                -- e.g., "recipe-export-progress"
    value JSONB NOT NULL,             -- content, metadata
    tags TEXT [],                     -- searchable tags
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,             -- TTL expiration
    UNIQUE(namespace, key)
);

CREATE INDEX memory_namespace ON memory(namespace);
CREATE INDEX memory_tags ON memory USING GIN(tags);
CREATE INDEX memory_expires_at ON memory(expires_at);
```

### 3.3 Agents' Working Memory (Agent-Specific)

**Location**: `.swarm/agents/{agent-id}/` or inline in agent context

**Use for**: Current task state, in-progress work, agent-to-agent communication

**Pattern**:
```
.swarm/agents/
├── typescript-expert/
│   ├── current-task.json
│   ├── context.md
│   └── findings.json
├── python-expert/
│   ├── current-task.json
│   └── findings.json
└── architecture-reviewer/
    └── review-checklist.json
```

---

## 4. Retrieval & Search Strategies

### 4.1 Direct Access (By Path)

**Best for**: Known artifact location

```python
# Retrieve specification
spec = memory.get("frontend/components/specs/recipe-export/requirements")

# Retrieve pattern
pattern = memory.get("backend/services/patterns/database-transaction/implementation.py")

# Retrieve decision
decision = memory.get("shared/decisions/adr-001-authentication-strategy")
```

### 4.2 Tag-Based Search

**Best for**: Finding related artifacts across domains

```python
# Find all auth patterns
auth_patterns = memory.search(tags=["pattern", "auth"])

# Find all test fixtures
fixtures = memory.search(
    tags=["test", "fixture"],
    app="backend"
)

# Find accepted architectural decisions
decisions = memory.search(
    tags=["decision", "accepted"],
    status="accepted"
)

# Find security vulnerabilities
vulnerabilities = memory.search(
    tags=["security", "critical"],
    priority="high"
)
```

### 4.3 Full-Text Search

**Best for**: Discovery when you don't know the exact path

```python
# Search for JWT-related content
jwt_docs = memory.search(
    query="JWT validation middleware",
    content_type="pattern|spec|decision"
)

# Search for MongoDB patterns
mongo_patterns = memory.search(
    query="MongoDB indexing strategy",
    tags=["pattern"]
)

# Find vulnerabilities by description
sql_issues = memory.search(
    query="SQL injection prevention",
    tags=["security"]
)
```

### 4.4 Namespace-Based Discovery

**Best for**: Exploring domain knowledge

```python
# List all backend auth resources
auth_resources = memory.list_namespace("backend/auth")

# Get all patterns in domain
all_patterns = memory.list_namespace(
    "frontend/components/patterns",
    recursive=True
)

# List all decisions across app
decisions = memory.list_namespace(
    "shared/decisions",
    filter_tags=["decision"]
)

# Find all tests in backend
tests = memory.list_namespace(
    "backend/*/tests",
    recursive=True
)
```

### 4.5 Contextual Retrieval for Agents

**Best for**: Agents loading context for a task

```python
# Frontend agent preparing to work on recipe export
context = memory.get_context(
    app="frontend",
    domain="components",
    feature="recipe-export",
    include=["specs", "patterns", "tests", "decisions"]
)
# Returns: {
#   "specs": [...],
#   "patterns": [...],
#   "tests": [...],
#   "related_decisions": [...]
# }

# Backend agent working on dataset service
context = memory.get_context(
    app="backend",
    domain="services",
    service="dataset",
    include=["specs", "models", "tests", "security"]
)
```

---

## 5. Memory Operations for Common Workflows

### 5.1 New Feature Implementation

**Workflow**: Implement a new feature from specification

**Memory Steps**:
```python
# 1. Retrieve feature specification
spec = memory.get("frontend/components/specs/bulk-export/requirements")

# 2. Find similar patterns
similar_patterns = memory.search(
    tags=["pattern", "export"],
    app="frontend"
)

# 3. Get test patterns for component tests
test_pattern = memory.get("frontend/components/tests/unit/component-template")

# 4. Check for security considerations
security_checks = memory.search(
    query="file export security",
    tags=["security"]
)

# 5. Store implementation notes as you progress
memory.set(
    "frontend/components/notes/bulk-export-implementation",
    content=daily_progress,
    tags=["note", "implementation", "bulk-export"],
    ttl=604800  # 7 days
)

# 6. Update decision log if architectural choice made
memory.append(
    "shared/decisions/file-export-strategy",
    new_insight="Chose streaming approach for >100MB files"
)
```

### 5.2 Bug Investigation & Fix

**Workflow**: Track bug investigation and share findings

**Memory Steps**:
```python
# 1. Store bug investigation notes
memory.set(
    "frontend/components/notes/recipe-export-firefox-bug",
    content=bug_analysis,
    tags=["bug", "investigation", "recipe-export"],
    severity="medium",
    ttl=345600  # 4 days
)

# 2. Search for related issues
related_issues = memory.search(
    query="file download timing issues",
    tags=["bug", "solved"]
)

# 3. Document the solution
memory.append(
    "frontend/components/notes/recipe-export-firefox-bug",
    solution_details=fix_explanation
)

# 4. Update pattern if this becomes a reusable pattern
if solution_is_generalizable:
    memory.set(
        "frontend/components/patterns/file-download-with-delay",
        content=pattern_code,
        tags=["pattern", "file-download", "browser-compatibility"]
    )
```

### 5.3 Code Review & Architecture Decision

**Workflow**: Review code change and record architectural decision

**Memory Steps**:
```python
# 1. Document the review findings
memory.set(
    "backend/decisions/review-dataset-service-refactor",
    content=review_notes,
    tags=["review", "architecture", "dataset"],
    status="in-review"
)

# 2. Search for related patterns/decisions
existing_decisions = memory.search(
    tags=["decision", "database", "transactions"]
)

# 3. If decision made, record as ADR
if decision_approved:
    memory.set(
        "backend/decisions/adr-backend-003-transaction-handling",
        content=adr_content,
        tags=["decision", "accepted", "database"],
        status="accepted"
    )

# 4. Update implementation guide
memory.set(
    "backend/services/patterns/database-transaction",
    content=updated_pattern,
    tags=["pattern", "database", "transactions"]
)
```

### 5.4 Testing & Quality Assurance

**Workflow**: Store test patterns and coverage insights

**Memory Steps**:
```python
# 1. Retrieve test pattern for domain
test_pattern = memory.get("backend/api/tests/unit/dataset-upload/test-fixtures")

# 2. Search for similar test scenarios
similar_tests = memory.search(
    tags=["test", "api", "validation"],
    app="backend"
)

# 3. Store test coverage findings
memory.set(
    "backend/api/notes/dataset-upload-test-analysis",
    content=coverage_report,
    tags=["test", "coverage", "dataset"],
    ttl=604800  # 7 days
)

# 4. Document edge cases discovered
memory.append(
    "backend/api/tests/unit/dataset-upload/test-patterns",
    edge_case_found="Large file handling with slow connections"
)

# 5. Record performance benchmarks
memory.set(
    "backend/services/notes/ml-pipeline-performance",
    content=benchmark_results,
    tags=["note", "performance", "ml"],
    ttl=604800
)
```

### 5.5 Security Review & Vulnerability Tracking

**Workflow**: Identify security issues and track mitigations

**Memory Steps**:
```python
# 1. Search for existing security patterns
auth_patterns = memory.search(
    tags=["security", "auth"],
    app="backend"
)

# 2. Document the vulnerability finding
memory.set(
    "backend/security/input-validation-audit",
    content=audit_findings,
    tags=["security", "audit", "input-validation"],
    priority="high",
    status="open"
)

# 3. Record the mitigation strategy
memory.set(
    "backend/security/patterns/request-validation",
    content=validation_pattern,
    tags=["pattern", "security", "validation"]
)

# 4. Add to security review checklist
memory.append(
    "shared/security/code-review-checklist",
    item="Verify all string inputs validated with Pydantic models"
)

# 5. Track remediation progress
memory.update(
    "backend/security/input-validation-audit",
    status="in-progress",
    files_reviewed=5,
    issues_found=2,
    issues_fixed=1
)
```

### 5.6 Cross-App Knowledge Sharing

**Workflow**: Share pattern found in one app with others

**Memory Steps**:
```python
# 1. Backend agent discovers optimal pattern
memory.set(
    "backend/services/patterns/async-task-queue",
    content=pattern_code,
    tags=["pattern", "async", "background-jobs"],
    discovered_in="backend",
    shareable=True
)

# 2. Frontend agent searches for similar patterns
async_patterns = memory.search(
    query="async background task",
    tags=["pattern", "async"]
)

# 3. Adapt to frontend context
memory.set(
    "frontend/hooks/patterns/use-background-task",
    content=adapted_pattern,
    tags=["pattern", "async", "hooks"],
    based_on="backend/services/patterns/async-task-queue",
    adapted=True
)

# 4. MCP agent reuses in tools
memory.set(
    "mcp/tools/patterns/async-tool-execution",
    content=mcp_pattern,
    tags=["pattern", "async", "tools"],
    based_on=["backend/services/patterns/async-task-queue"]
)

# 5. Add to shared patterns library
memory.set(
    "shared/patterns/async-execution",
    content=unified_pattern,
    tags=["pattern", "async", "shared"],
    implementations=[
        "backend/services/patterns/async-task-queue",
        "frontend/hooks/patterns/use-background-task",
        "mcp/tools/patterns/async-tool-execution"
    ]
)
```

---

## 6. Memory Synchronization Patterns

### 6.1 Persistent → Ephemeral (Loading Context)

**When**: Agent loads context for a task

```python
class Agent:
    def __init__(self, memory: MemoryStore):
        self.memory = memory
        self.context = {}

    def load_context(self, app: str, domain: str, feature: str):
        """Load persistent memory into agent context"""
        # Load specifications
        self.context['specs'] = self.memory.get(
            f"{app}/{domain}/specs/{feature}"
        )

        # Load relevant patterns
        self.context['patterns'] = self.memory.search(
            tags=["pattern"],
            namespace=f"{app}/{domain}"
        )

        # Load test patterns
        self.context['tests'] = self.memory.search(
            tags=["test"],
            namespace=f"{app}/{domain}"
        )

        # Load related decisions
        self.context['decisions'] = self.memory.search(
            tags=["decision"],
            related_to=[app, domain, feature]
        )

        # Load security considerations
        self.context['security'] = self.memory.search(
            tags=["security"],
            app=app
        )

        return self.context
```

### 6.2 Ephemeral → Persistent (Promoting Insights)

**When**: Session-specific notes become reusable patterns

```python
def promote_to_pattern(memory: MemoryStore, session_note_key: str):
    """Promote implementation note to permanent pattern"""
    # Retrieve session note
    note = memory.get(session_note_key, expire_protection=True)

    # Extract reusable pattern
    pattern = extract_pattern_from_note(note)

    # Store as permanent pattern
    memory.set(
        pattern.key,
        content=pattern.code,
        tags=pattern.tags + ["pattern"],
        ttl=None  # Permanent
    )

    # Link back to original note
    memory.update(
        session_note_key,
        promoted_to=pattern.key,
        promotion_date=datetime.now()
    )
```

### 6.3 Agent-to-Agent Communication

**When**: Multiple agents coordinate on same feature

```python
# Agent A: Frontend agent completes work
memory.set(
    "frontend/components/notes/recipe-export-implementation",
    content=final_notes,
    tags=["note", "implementation", "recipe-export", "completed"],
    status="ready-for-backend",
    api_contract=api_contract_json,
    ttl=604800
)

# Agent B: Backend agent discovers the note
backend_context = memory.search(
    query="recipe-export",
    tags=["note", "ready-for-backend"],
    app="frontend"
)

# Extract API contract
api_contract = memory.get(
    "frontend/components/notes/recipe-export-implementation",
    field="api_contract"
)

# Backend implements based on contract
memory.set(
    "backend/api/notes/recipe-export-backend-implementation",
    content=implementation_notes,
    tags=["note", "implementation", "recipe-export"],
    implements=api_contract,
    ttl=604800
)
```

### 6.4 Conflict Resolution (Versioning)

**When**: Multiple agents update same memory entry

```python
class MemoryVersion:
    key: str
    version: int
    timestamp: datetime
    author_agent: str
    content: str
    change_summary: str
    parent_version: Optional[int]

# Agent A updates pattern
memory.update(
    "backend/services/patterns/database-transaction",
    content=new_content,
    change_summary="Add connection pooling optimization",
    agent="python-expert-1"
)
# Creates: version 2, timestamp 2024-12-26T10:30:00, parent: 1

# Agent B simultaneously updates
memory.update(
    "backend/services/patterns/database-transaction",
    content=other_content,
    change_summary="Add error retry logic",
    agent="python-expert-2"
)
# Creates: version 3, timestamp 2024-12-26T10:30:05, parent: 1

# Memory system detects conflict, stores both versions
versions = memory.get_versions("backend/services/patterns/database-transaction")
# Returns: [v1, v2, v3] with conflict_detected=True

# Manual merge or auto-merge policy
merged = memory.merge_versions([v2, v3])
# Creates: version 4 with both optimizations
```

---

## 7. Memory Lifecycle Management

### 7.1 Retention Policies

| Artifact Type | Default TTL | Use Case | Action |
|--------------|-----------|----------|--------|
| Specification | Never expire | Source of truth | Keep indefinitely |
| Architecture Decision | Never expire | Historical record | Archive old decisions |
| Reusable Pattern | Never expire | Knowledge base | Version when updated |
| Test Pattern | Never expire | Test template | Update with new insights |
| Security Pattern | Never expire | Critical guidance | Review quarterly |
| Implementation Note | 7 days | Session-specific context | Auto-delete after TTL |
| Session Progress | 7 days | Temporary tracking | Auto-delete after TTL |
| Bug Investigation | 4 days | Problem solving | Convert to pattern if reusable |
| Performance Benchmark | 30 days | Performance tracking | Aggregate and archive |

### 7.2 Archive Strategy

**When**: TTL expires or marked for archival

```python
# Archive old session notes to historical storage
archived = memory.archive(
    older_than=timedelta(days=30),
    filter_tags=["note"],
    destination=".claude-flow/memory/archives/"
)

# Archive by date range
memory.archive(
    from_date="2024-11-01",
    to_date="2024-11-30",
    destination=".claude-flow/memory/archives/2024-11/"
)

# Manually archive important session notes
memory.archive_entry(
    "backend/services/notes/ml-pipeline-optimization",
    destination=".claude-flow/memory/archived/sprints/sprint-11/"
)
```

### 7.3 Indexing & Searchability

**Automatic Indexing**:
- Full-text search on content
- Tag-based indexing
- Namespace path indexing
- Timestamp indexing (for TTL)
- Author/agent indexing (who created it)

**Index Rebuild**:
```bash
# Rebuild search indexes
memory-manager rebuild-index

# Optimize database
memory-manager optimize

# Cleanup expired entries
memory-manager cleanup-expired

# Generate statistics
memory-manager stats --output stats.json
```

---

## 8. Integration with Agent Orchestration

### 8.1 Memory Access in Agent Workflows

**Agent Initialization**:
```python
class SwarmAgent(BaseAgent):
    def __init__(self, role: str, app: str, domain: str):
        self.memory = MemoryStore(db_path=".swarm/memory.db")
        self.context = {}

    def on_task_start(self, task_id: str, feature: str):
        """Load context when task begins"""
        self.context = self.memory.load_context(
            app=self.app,
            domain=self.domain,
            feature=feature
        )

        # Make context available to agent
        self.set_system_context(
            f"""
            You have access to the following knowledge base entries:

            Specifications: {len(self.context['specs'])} items
            Patterns: {len(self.context['patterns'])} items
            Tests: {len(self.context['tests'])} items
            Decisions: {len(self.context['decisions'])} items

            Use memory.get() to retrieve specific entries.
            Use memory.search() to find related content.
            """
        )
```

### 8.2 Memory Notifications

**When**: Notable memory updates occur

```python
# Agent completes important work
memory.set(
    "frontend/components/notes/bulk-export-implementation",
    content=work_summary,
    tags=["note", "implementation", "completed"],
    notify=["python-expert", "architecture-reviewer"],
    priority="high"
)

# Notified agents can retrieve and react
def on_memory_notification(event: MemoryEvent):
    if event.priority == "high" and event.tags & {"completed"}:
        # Load and review the work
        work = memory.get(event.key)
        # Trigger code review or next task
```

---

## 9. Example: Complete Feature Workflow with Memory

### Scenario: Implementing Recipe Bulk Export

**1. Specification Phase**:
```python
# Store API specification
memory.set(
    "backend/api/specs/recipe-bulk-export",
    content="""
    POST /api/recipes/bulk-export
    Request: { recipeIds: string[], format: 'json'|'csv', includeMetadata: bool }
    Response: { downloadUrl: string, jobId: string, expiresAt: timestamp }
    """,
    tags=["spec", "api", "recipe-export", "v1.0"]
)

# Store UI specification
memory.set(
    "frontend/components/specs/recipe-bulk-export-dialog",
    content="""
    Component: RecipeBulkExportDialog
    Props: { isOpen: bool, recipes: Recipe[], onExport: (config) => void }
    States: idle, selecting, exporting, success, error
    """,
    tags=["spec", "component", "recipe-export", "v1.0"]
)
```

**2. Backend Implementation**:
```python
# Frontend agent loads context
context = memory.load_context("frontend", "components", "recipe-bulk-export-dialog")

# Backend agent loads context
context = memory.load_context("backend", "api", "recipe-bulk-export")

# Both store progress notes
memory.set(
    "frontend/components/notes/bulk-export-implementation",
    content="Day 1: Component structure complete, API integration in progress",
    tags=["note", "implementation", "recipe-export"],
    ttl=604800
)

memory.set(
    "backend/api/notes/bulk-export-implementation",
    content="Day 1: Endpoint defined, queuing system setup",
    tags=["note", "implementation", "recipe-export"],
    ttl=604800
)
```

**3. Testing & QA**:
```python
# Retrieve test patterns
test_fixtures = memory.get("backend/api/tests/unit/recipe-export/test-fixtures")
test_e2e = memory.get("frontend/components/tests/e2e/bulk-export-dialog")

# Store test coverage findings
memory.set(
    "backend/api/notes/bulk-export-test-analysis",
    content="Coverage: 94%, Gap: Large file edge cases",
    tags=["test", "coverage", "recipe-export"],
    ttl=604800
)
```

**4. Code Review & Finalization**:
```python
# Document architectural decision
memory.set(
    "backend/decisions/adr-backend-002-bulk-export-queuing",
    content="""
    # Decision: Background Job Queue for Bulk Export

    Used Redis-backed Celery queue for async processing.
    Allows clients to check export progress via jobId.
    """,
    tags=["decision", "accepted", "recipe-export"],
    status="accepted"
)

# Promote key patterns to permanent library
memory.set(
    "backend/services/patterns/async-bulk-operation",
    content=generalized_pattern,
    tags=["pattern", "async", "bulk-operation"],
    based_on="backend/api/implementation/recipe-bulk-export"
)
```

**5. Documentation & Knowledge Transfer**:
```python
# Create implementation guide for future features
memory.set(
    "shared/patterns/bulk-export-pattern",
    content="""
    # Bulk Export Pattern

    Applicable when: Exporting large datasets asynchronously

    Components:
    - Frontend dialog for selection and format choice
    - Backend async job queue
    - Progress tracking via jobId
    - Signed download URLs

    Implementation references:
    - frontend/components/specs/recipe-bulk-export-dialog
    - backend/api/specs/recipe-bulk-export
    - backend/services/patterns/async-bulk-operation
    """,
    tags=["pattern", "shared", "bulk-operation", "export"],
    cross_references=[
        "frontend/components/patterns/bulk-export-dialog",
        "backend/services/patterns/async-bulk-operation"
    ]
)
```

---

## 10. Access Control & Permissions

### Memory Visibility by Role

| Role | Read Access | Write Access | Delete Access |
|------|-----------|-------------|--------------|
| Agent (own domain) | Own domain + shared | Own domain only | Own temp notes |
| Architecture Reviewer | All | Decisions + security | None |
| Tech Lead | All | All | All |
| CI/CD Pipeline | Limited (patterns, specs) | None | None |

**Implementation**:
```python
class MemoryStore:
    def get(self, key: str, agent: Optional[str] = None) -> dict:
        entry = self._load(key)

        # Check visibility
        if not self._can_read(entry, agent):
            raise PermissionError(f"Cannot read {key}")

        return entry

    def set(self, key: str, content: str, agent: str):
        # Check write permission
        domain = key.split('/')[0]

        if not self._can_write(domain, agent):
            raise PermissionError(f"Cannot write to {domain}")

        self._save(key, content)
```

---

## 11. Health & Monitoring

### Memory System Metrics

**Track**:
- Total entries by type
- Search query patterns (what agents are looking for)
- TTL expiration rates
- Conflict resolution frequency
- Access patterns (read/write ratio)
- Storage size usage

**Monitoring Dashboard**:
```bash
# View memory statistics
memory-manager stats

# Monitor access patterns
memory-manager monitor --interval 60

# Audit entry modifications
memory-manager audit --start 2024-12-26 --agent python-expert

# Health check
memory-manager health
```

---

## 12. Quick Reference: Common Commands

```python
# === RETRIEVAL ===
memory.get("backend/api/specs/dataset-upload")
memory.search(tags=["pattern", "async"], app="backend")
memory.search(query="JWT validation")
memory.list_namespace("frontend/components/patterns", recursive=True)

# === STORAGE ===
memory.set("frontend/hooks/specs/use-async-data", content, tags=[...])
memory.append("frontend/components/notes/progress", new_entry)
memory.update("backend/decisions/adr-001", status="accepted")

# === LIFECYCLE ===
memory.archive(older_than=timedelta(days=30), filter_tags=["note"])
memory.cleanup_expired()
memory.rebuild_index()

# === SEARCHING ===
patterns = memory.search(tags=["pattern"], app="frontend")
decisions = memory.search(query="authentication", tags=["decision"])
context = memory.get_context(app="backend", domain="services", include=["specs", "patterns"])

# === CONTEXT LOADING ===
context = memory.load_context("frontend", "components", "recipe-export")
```

---

## 13. Migration Guide: From .apm to Unified Memory

**Current State**: Agent memory in `.apm/memory/` (per-backend)

**Target State**: Unified memory across all apps in `.swarm/memory.db` + `.claude-flow/memory/`

**Migration Steps**:
```bash
# 1. Export existing .apm entries
memory-manager export-apm --source apps/backend/.apm/memory --output exported.json

# 2. Transform to new hierarchy
memory-manager transform --input exported.json --schema new-hierarchy.json --output transformed.json

# 3. Import to unified store
memory-manager import --input transformed.json --destination .swarm/memory.db

# 4. Verify migration
memory-manager verify-migration --compare apps/backend/.apm/memory .swarm/memory.db

# 5. Archive old .apm
mv apps/backend/.apm/memory .claude-flow/memory/archives/legacy-apm-backup/
```

---

## Summary

This memory architecture provides:

✅ **Hierarchical Organization**: Clear namespace structure by app, domain, and artifact type
✅ **Flexible Retrieval**: Direct access, tag search, full-text search, namespace discovery
✅ **Persistent Knowledge**: Specifications, patterns, decisions live indefinitely
✅ **Session Context**: Implementation notes and progress with TTL-based cleanup
✅ **Agent Coordination**: Shared state and notifications for multi-agent workflows
✅ **Security Tracking**: Dedicated security patterns and vulnerability management
✅ **Easy Integration**: Simple API for agent access and context loading
✅ **Scalability**: Supports growth across multiple apps and features

**Next Steps**:
1. Implement memory storage backend (SQLite + file-based persistent storage)
2. Create agent SDK integration for memory access
3. Build memory visualization/dashboard for monitoring
4. Establish team conventions for adding new memory entries
