# Memory Index Template

## Overview

This document shows what memory entries should exist for the Narrative Modeling App, organized by current state and what should be populated during active development.

---

## Current Memory Structure

### Persistent Memory (`.claude-flow/memory/`)

```
.claude-flow/memory/
├── index.json                          # Master index of all entries
│
├── frontend/
│   ├── auth/
│   │   ├── specs/
│   │   │   └── oauth-integration/
│   │   │       ├── requirements.md
│   │   │       ├── oauth-flow.md
│   │   │       └── session-management.md
│   │   │
│   │   └── patterns/
│   │       └── use-auth-context/
│   │           ├── implementation.tsx
│   │           ├── usage-guide.md
│   │           └── test-example.tsx
│   │
│   ├── components/
│   │   ├── specs/
│   │   │   ├── recipe-export-dialog/
│   │   │   └── recipe-bulk-export-dialog/
│   │   │
│   │   └── patterns/
│   │       ├── dialog-component-pattern/
│   │       └── async-data-loading-pattern/
│   │
│   ├── pages/
│   │   └── specs/
│   │       ├── dashboard-page/
│   │       └── recipe-detail-page/
│   │
│   └── hooks/
│       └── patterns/
│           ├── use-async-data/
│           └── use-form-validation/
│
├── backend/
│   ├── auth/
│   │   └── patterns/
│   │       └── jwt-validation-middleware/
│   │
│   ├── api/
│   │   ├── specs/
│   │   │   ├── dataset-upload/
│   │   │   ├── recipe-management/
│   │   │   └── recipe-export/
│   │   │
│   │   └── tests/
│   │       ├── unit/
│   │       │   ├── dataset-upload/
│   │       │   │   └── test-fixtures.py
│   │       │   └── recipe-export/
│   │       │       └── test-fixtures.py
│   │       │
│   │       └── integration/
│   │           ├── dataset-service/
│   │           └── recipe-service/
│   │
│   ├── services/
│   │   ├── patterns/
│   │   │   ├── database-transaction-pattern/
│   │   │   └── async-task-queue-pattern/
│   │   │
│   │   └── tests/
│   │       └── unit/
│   │           ├── dataset-service/
│   │           └── recipe-service/
│   │
│   ├── models/
│   │   └── specs/
│   │       ├── dataset-model/
│   │       └── recipe-model/
│   │
│   └── ml/
│       ├── patterns/
│       │   ├── model-training-pattern/
│       │   └── feature-engineering-pattern/
│       │
│       └── tests/
│           └── unit/
│               ├── problem-detector/
│               └── feature-engineer/
│
├── mcp/
│   ├── tools/
│   │   ├── specs/
│   │   │   └── data-processing-tools/
│   │   │
│   │   └── patterns/
│   │       ├── data-transformation-pattern/
│   │       └── async-tool-execution-pattern/
│   │
│   └── integration/
│       └── patterns/
│           └── external-service-integration/
│
└── shared/
    ├── decisions/
    │   ├── adr-001-authentication-strategy.md
    │   ├── adr-002-database-schema.md
    │   ├── adr-003-async-job-queue.md
    │   └── adr-004-file-storage-strategy.md
    │
    ├── patterns/
    │   ├── bulk-export-pattern/
    │   ├── async-processing-pattern/
    │   └── file-upload-pattern/
    │
    ├── security/
    │   ├── sql-injection-prevention.md
    │   ├── xss-prevention-guidelines.md
    │   ├── jwt-security-patterns.md
    │   ├── input-validation-rules.md
    │   └── file-upload-security.md
    │
    └── testing/
        ├── test-fixtures-guide.md
        └── integration-test-strategy.md
```

---

## Ephemeral Memory (`.swarm/memory.db`)

Automatically created during active development:

```
Session Notes (TTL: 7 days):
- frontend/components/notes/recipe-export-sprint-11
- backend/services/notes/ml-pipeline-optimization-sprint-11
- backend/api/notes/dataset-upload-refactor

Bug Investigations (TTL: 4 days):
- frontend/components/notes/firefox-file-download-bug
- backend/api/notes/jwt-validation-race-condition

Performance Benchmarks (TTL: 30 days):
- backend/services/notes/query-optimization-results
- frontend/hooks/notes/render-performance-analysis
```

---

## Populated Entries (Current State)

### Specifications (Existing)
- ✅ Backend dataset upload API (from requirements)
- ✅ Backend recipe management API (from requirements)
- ✅ Frontend recipe export dialog (from requirements)
- ✅ Database schemas (from models)

### Patterns (Should Exist)
- ✅ JWT authentication pattern (from auth.ts)
- ✅ Dataset service pattern (from services/)
- ✅ Async ML processing pattern (from background tasks)
- ⏳ Frontend hooks patterns (to document)
- ⏳ Bulk export pattern (to document)

### Decisions (Should Exist)
- ✅ ADR-001: NextAuth.js authentication (Sprint 11)
- ✅ ADR-002: MongoDB schema design (Sprint 8)
- ✅ ADR-003: Redis for job queue (Sprint 10)
- ✅ ADR-004: S3 for file storage (Sprint 9)

### Security Patterns (Should Exist)
- ✅ SQL injection prevention (Pydantic validation)
- ✅ JWT validation middleware (auth.py)
- ✅ CORS security patterns (middleware.py)
- ⏳ File upload security guidelines

### Tests (Should Document)
- ✅ Unit test fixtures (tests/test_services)
- ✅ Integration test patterns (tests/integration)
- ⏳ E2E test examples (Playwright)

---

## Entry Template Examples

### Specification Entry

**Location**: `.claude-flow/memory/backend/api/specs/dataset-upload/endpoint-spec.md`

```markdown
# Dataset Upload Endpoint Specification

## Route
POST /api/datasets/upload

## Request
```json
{
  "name": string,
  "description": string,
  "file": multipart/form-data (CSV, Excel)
}
```

## Response (200)
```json
{
  "id": string,
  "name": string,
  "status": "processing",
  "uploadedAt": ISO8601,
  "rowCount": number
}
```

## Status Codes
- 200: Upload started successfully
- 400: Invalid file format
- 413: File too large
- 409: Dataset name exists

## Validation Rules
- File size < 100MB
- Supported formats: CSV, XLSX
- Column count > 0

## Security
- Require authentication
- Validate MIME type
- Scan for malware (server-side)
```

### Pattern Entry

**Location**: `.claude-flow/memory/backend/services/patterns/database-transaction-pattern/implementation.py`

```python
"""
Pattern: Reliable Database Transactions

Context:
When updating multiple related documents in MongoDB, ensure consistency.

Implementation:
```python
async def transfer_recipe(from_user: str, to_user: str, recipe_id: str):
    """
    Transfer recipe between users with transaction safety.

    Uses Beanie transactions for ACID compliance.
    """
    async with await motor_client.start_session() as session:
        async with session.start_transaction():
            # Load recipe (with lock)
            recipe = await Recipe.find_one(
                Recipe.id == ObjectId(recipe_id),
                session=session
            )

            if not recipe or recipe.owner != from_user:
                raise ValueError("Recipe not found or unauthorized")

            # Update recipe owner
            recipe.owner = to_user
            await recipe.save(session=session)

            # Update user collections
            await User.find_one(
                User.id == from_user,
                session=session
            ).update({"$pull": {"recipe_ids": recipe.id}})

            await User.find_one(
                User.id == to_user,
                session=session
            ).update({"$push": {"recipe_ids": recipe.id}})

            # All-or-nothing: transaction commits atomically

# Usage
try:
    await transfer_recipe(from_user="user1", to_user="user2", recipe_id="123")
except Exception as e:
    # Transaction rolled back automatically
    logger.error(f"Transfer failed: {e}")
```

## Key Points
- Always use sessions for multi-document operations
- Rollback is automatic on exception
- Beanie handles transaction semantics

## Related
- Test: `backend/api/tests/integration/recipe-transfer-test`
- Decision: `shared/decisions/adr-002-mongodb-transactions`
```

### Decision Entry

**Location**: `.claude-flow/memory/shared/decisions/adr-001-authentication-strategy.md`

```markdown
# ADR-001: Authentication Strategy

## Status
ACCEPTED (Sprint 11)

## Context
The app requires user authentication with multiple providers (Google, GitHub).
We need a solution that is:
- Secure by default
- Minimal maintenance burden
- Works with MongoDB
- Supports role-based access control (RBAC)

## Decision
Use NextAuth.js v5 for frontend authentication with MongoDB adapter.
Enforce backend validation using JWT tokens.

## Consequences

### Pros
- Industry standard (widely adopted)
- Secure session management (httpOnly cookies)
- Provider ecosystem (Google, GitHub, Discord, etc.)
- Automatic token refresh
- Built-in CSRF protection

### Cons
- Additional dependency (NextAuth.js)
- Session storage in MongoDB
- Provider API changes require adapter updates

### Risk
- Provider outages block login
- Mitigation: Graceful degradation with offline mode

## Implementation

### Frontend (Next.js)
```typescript
import { auth } from "@/auth"

export default async function Dashboard() {
  const session = await auth()
  if (!session) redirect("/login")
  return <div>Authenticated: {session.user.email}</div>
}
```

### Backend (FastAPI)
```python
from app.middleware.auth import require_auth

@router.get("/api/user/profile")
@require_auth()
async def get_profile(current_user: User) -> ProfileResponse:
    return ProfileResponse.from_user(current_user)
```

## Related Patterns
- `frontend/auth/patterns/use-auth-context`
- `backend/auth/patterns/jwt-validation-middleware`

## References
- NextAuth.js docs: https://next-auth.js.org/
- JWT security: https://tools.ietf.org/html/rfc7519
- OWASP session management: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html

## Approved By
Technical steering committee, Sprint 11 kickoff

## Implementation Date
2024-11-15

## Review Date
2025-01-15 (scheduled quarterly review)
```

### Test Fixture Entry

**Location**: `.claude-flow/memory/backend/api/tests/unit/dataset-upload/test-fixtures.md`

```markdown
# Dataset Upload Test Fixtures

## Testing Strategy

### Unit Tests (No Database)
- Mock S3 client
- Mock MongoDB
- Test input validation
- Test error handling

### Integration Tests (Real MongoDB)
- Use test database (`narrative_modeling_test`)
- Real S3 bucket (test prefix)
- Test transaction handling
- Test data persistence

### E2E Tests (Full Stack)
- Deploy to staging
- Create test user
- Full upload workflow
- Verify data in UI

## Sample Data

### Valid CSV
```csv
name,age,city
John,30,NYC
Jane,25,SF
```

### Edge Cases
- Empty file (0 bytes)
- Large file (99MB)
- Unicode characters
- Special characters in headers
- Duplicate column names

## Fixtures

```python
@pytest.fixture
def valid_csv():
    return "name,age,city\nJohn,30,NYC"

@pytest.fixture
def mock_s3_service(mocker):
    return mocker.patch("app.services.S3Service")

@pytest.fixture
def dataset_service(mock_s3_service):
    return DatasetService(s3_service=mock_s3_service)
```

## Coverage Goals
- Input validation: 100%
- Error paths: 95%
- S3 interaction: 90%
- Database operations: 85%

Current: 92% (Sprint 11)
```

---

## Priority Entry Creation Order

### Phase 1: Specifications (Week 1)
- All endpoint specifications
- All component/model specifications
- All schema specifications

### Phase 2: Architectural Decisions (Week 1-2)
- All major architecture decisions
- Trade-offs documented
- Approved by team lead

### Phase 3: Reusable Patterns (Week 2-4)
- Generalize code patterns from implementation
- Document with examples
- Link to real implementations

### Phase 4: Security Patterns (Week 2-3)
- Document all security requirements
- Create validation checklists
- Link to implementations

### Phase 5: Test Patterns (Week 3-4)
- Capture test fixtures
- Document testing strategy
- Share patterns across team

### Phase 6: Session Notes (Ongoing)
- Implementation progress logs
- Bug investigations
- Performance insights

---

## Maintenance Schedule

### Daily
- Create session notes as you work
- Update implementation progress
- Document bugs found

### Weekly
- Review and promote useful session notes to patterns
- Archive old notes (>30 days)
- Update decision statuses

### Monthly
- Review architecture decisions
- Consolidate duplicate patterns
- Generate memory statistics

### Quarterly
- Archive old patterns (document migration path)
- Review security patterns (check for CVEs)
- Plan memory reorganization if needed

---

## Common Queries (Examples)

### "Show me all auth patterns"
```python
memory.search(tags=["pattern", "auth"])
```
Returns: OAuth, JWT, session management patterns

### "What decisions did we make about async processing?"
```python
memory.search(tags=["decision", "async"])
```
Returns: Job queue decision, async pattern decision

### "Show me all dataset-related specs"
```python
memory.search(query="dataset", tags=["spec"])
```
Returns: Dataset upload, dataset processing specs

### "What security vulnerabilities exist?"
```python
memory.search(tags=["security"], priority="critical")
```
Returns: Open security findings

### "Load full context for recipe export feature"
```python
context = memory.load_context("frontend", "components", "recipe-export")
```
Returns: Specs, patterns, tests, decisions for feature

---

## Memory Health Checks

Run these queries monthly to ensure memory is healthy:

```python
# 1. Check coverage
specs = memory.search(tags=["spec"]).total_count
patterns = memory.search(tags=["pattern"]).total_count
decisions = memory.search(tags=["decision"]).total_count

print(f"Specs: {specs}, Patterns: {patterns}, Decisions: {decisions}")

# 2. Find orphaned entries (no usage)
orphaned = memory.search(updated_at < 90_days_ago, tags=["note"])

# 3. Find duplicate patterns
patterns = memory.search(tags=["pattern"])
# Check for semantic duplicates

# 4. Verify all decisions have implementations
decisions = memory.search(tags=["decision"])
for decision in decisions:
    if not decision.metadata.get("implemented"):
        print(f"WARNING: Decision {decision.key} not yet implemented")
```

---

## Quick Setup Checklist

To bootstrap memory for this project:

- [ ] Create root namespace structure
- [ ] Add current architecture specifications
- [ ] Document existing architectural decisions
- [ ] Capture existing code patterns
- [ ] Document current security patterns
- [ ] Add test fixtures and strategies
- [ ] Create agent registry with roles
- [ ] Setup CLI tools
- [ ] Train team on memory conventions
- [ ] Create monitoring/stats dashboard

---

## Example: Initial Population Command

```python
# scripts/bootstrap_memory.py
from shared.memory.store import MemoryStore
from pathlib import Path

memory = MemoryStore()

# Load and store architecture decisions
decisions_dir = Path("docs/decisions")
for adr_file in decisions_dir.glob("*.md"):
    with open(adr_file) as f:
        content = f.read()

    memory.set(
        key=f"shared/decisions/{adr_file.stem}",
        content=content,
        tags=["decision", "architecture"],
        artifact_type="decision"
    )
    print(f"✓ Loaded {adr_file.stem}")

print("Memory bootstrap complete")
```

Run with: `python scripts/bootstrap_memory.py`
