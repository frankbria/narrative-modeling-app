# Narrative Modeling App - Swarm Quick Reference

**For**: AI Agent Orchestration
**Status**: Ready for swarm activation
**Created**: 2025-12-26

---

## Swarm Composition (3 Primary Agents)

### 1. TypeScript/React Expert (Frontend)
- **Location**: `apps/frontend/`
- **Frameworks**: Next.js 15.5, React 19.2, TypeScript 5.9
- **Testing**: Jest (unit) + Playwright (E2E)
- **Test Command**: `cd apps/frontend && npm test`
- **Responsibilities**: Pages, components, styling, forms, visualizations
- **Quality Gate**: All tests pass, tsc clean, eslint clean, >85% coverage

### 2. Python/FastAPI Expert (Backend)
- **Location**: `apps/backend/`
- **Frameworks**: FastAPI 0.115, Pydantic 2.11, Beanie 1.30, MongoDB
- **Testing**: pytest 8.4 + pytest-asyncio, pytest-benchmark
- **Test Commands**:
  - Full: `cd apps/backend && uv run pytest`
  - Unit only: `cd apps/backend && uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ tests/test_model_training/test_problem_detector.py tests/test_model_training/test_feature_engineer.py -v`
- **Responsibilities**: API routes, services, schemas, data processing, ML training
- **Quality Gate**: 100% tests passing (214/214), >85% coverage, mypy clean
- **Database**: MongoDB (required for integration tests)

### 3. Python/FastMCP Expert (MCP Server)
- **Location**: `apps/mcp/`
- **Framework**: FastMCP
- **Testing**: pytest
- **Test Command**: `cd apps/mcp && uv run pytest`
- **Responsibilities**: Tool development, data processing algorithms, integration
- **Status**: On-demand (activate when MCP tools needed)

---

## Critical Quality Requirements (NON-NEGOTIABLE)

```
BEFORE ANY PR MERGE:
✅ Backend: 214/214 tests passing (100%)
✅ Frontend: All tests passing (Jest + Playwright)
✅ Coverage: >85% (Backend + Frontend)
✅ Type Safety: tsc clean (Frontend), mypy clean (Backend)
✅ Linting: eslint clean (Frontend), ruff clean (Backend)
✅ Documentation: API.md, docstrings, CLAUDE.md synchronized
✅ Security: No cross-tenant data leaks, PII detection active
✅ No TODO/FIXME/NotImplementedError markers
```

---

## Task Distribution Matrix

| Task Type | Agent | Notes |
|-----------|-------|-------|
| New page/component | Frontend | Jest + Playwright tests required |
| API route/schema | Backend | TDD approach, async patterns |
| Service layer | Backend | Complex logic, unit + integration tests |
| Data transformation | Backend | Performance benchmarks required |
| ML training | Backend | Validation tests mandatory |
| Database schema | Backend | Migration + test fixtures |
| Styling/Layout | Frontend | Tailwind CSS, responsive design |
| Visualization | Frontend | Chart.js or Recharts integration |
| Form handling | Frontend | Validation, error handling |
| Authentication | Frontend | NextAuth v5 patterns |
| MCP tool | MCP Expert | Tool definition + integration test |
| DevOps/CI | DevOps Agent | GitHub Actions, deployment |

---

## Key Project Patterns

### Data Model Architecture
```
DatasetMetadata ──> TransformationConfig ──> ModelConfig
         │                  │                      │
         └──────────────────┴──────────────────────┘
                      ↓
                Service Layer
         (DatasetService, TransformationService, ModelService)
```

### Version & Lineage Tracking
- Every data operation tracks version history
- Parent-child relationships maintained
- Recipe system for reusable transformations
- Ownership validation (prevent cross-tenant leaks)

### Performance Targets
- P50: <200ms
- P95: <500ms
- P99: <1s
- Redis caching active
- Connection pooling enabled

---

## Environment Setup

### Backend
```bash
cd apps/backend
python -m venv .venv
source .venv/bin/activate
uv sync
# Start MongoDB if needed
uv run pytest
```

### Frontend
```bash
cd apps/frontend
npm install
npm test
npm test:e2e:smoke
```

### MCP
```bash
cd apps/mcp
uv sync
uv run pytest
```

---

## Current Sprint Status

**Sprint 12**: 87% Complete (33/38 points)

### Completed (4 stories)
- Story 12.1: API Integration (10 pts) ✅
- Story 12.2: Data Versioning (8 pts) ✅
- Story 12.3: Production Deployment (10 pts) ✅
- Story 12.4: Performance Optimization (5 pts) ✅

### Pending
- Story 12.5: E2E Integration Testing (5 pts) - 6-8 hours
  - Fix test fixture dependencies
  - Update mocking for domain models
  - Add workflow coverage

---

## Common Commands

### Backend
```bash
# Full test suite
cd apps/backend && uv run pytest

# Unit tests only (no DB)
cd apps/backend && uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ tests/test_model_training/test_problem_detector.py tests/test_model_training/test_feature_engineer.py -v

# With coverage
cd apps/backend && uv run pytest --cov=app --cov-report=html

# Performance benchmarks
cd apps/backend && uv run pytest tests/benchmarks/ -v --benchmark-only

# Run server
cd apps/backend && uv run python -m uvicorn app.main:app --reload
```

### Frontend
```bash
# Unit tests
cd apps/frontend && npm test

# E2E smoke tests
cd apps/frontend && npm test:e2e:smoke

# E2E full suite
cd apps/frontend && npm test:e2e:full

# Multi-browser E2E
cd apps/frontend && npm test:e2e:all

# Dev server
cd apps/frontend && npm run dev

# Build
cd apps/frontend && npm run build
```

### MCP
```bash
# Tests
cd apps/mcp && uv run pytest

# Dev server
cd apps/mcp && uv run mcp dev server.py
```

---

## Documentation Access

**Key Files to Read First**:
1. `/home/frankbria/projects/narrative-modeling-app/CLAUDE.md` - Project patterns
2. `apps/backend/docs/SPRINTS.md` - Sprint history
3. `apps/backend/docs/TDD_GUIDE.md` - Testing methodology
4. `apps/backend/docs/TEST_INFRASTRUCTURE.md` - Test organization
5. `.claude-flow/project-requirements-analysis.md` - This analysis

**API Documentation**:
- `apps/backend/docs/API.md` - Current API endpoints
- `apps/backend/docs/TRANSFORMATIONS.md` - Transformation patterns
- `apps/backend/docs/VERSIONING.md` - Version system
- `apps/backend/docs/RECIPE_SYSTEM.md` - Recipe patterns

---

## Coordination Protocol

### Feature Development Flow
```
1. Spec/Design (Human)
2. Backend: API schema + routes
3. Frontend: Components + UI (parallel with backend)
4. MCP: Tools if needed (parallel)
5. Quality Check: All tests pass
6. Documentation Update: All agents contribute
7. PR Review + Merge
```

### Agent Handoff Points
- Backend publishes API contract (routes + schemas)
- Frontend consumes API and builds UI
- MCP integrates specialized operations
- All agents update docs before merge

### Quality Validation
```
Before Merge:
□ Backend: uv run pytest (100% pass)
□ Frontend: npm test (100% pass)
□ Coverage: >85%
□ Types: tsc/mypy clean
□ Linting: eslint/ruff clean
□ Docs: API.md, docstrings, CLAUDE.md
□ Security: No vulnerabilities
```

---

## Troubleshooting Quick Fixes

| Issue | Fix |
|-------|-----|
| MongoDB not found | `docker-compose up mongo` in project root |
| Tests fail (async) | Check pytest-asyncio markers on tests |
| Type errors (TS) | Run `tsc --noEmit` to find all type issues |
| Import errors (Py) | Ensure `uv sync` completed and venv activated |
| S3 test failures | Mock S3 with moto (already in test fixtures) |
| Playwright fails | Ensure browsers installed: `playwright install` |
| Port conflicts | Check 8000 (backend), 3000 (frontend) availability |

---

## Critical Patterns to Remember

### MUST DO
- Write tests BEFORE code (TDD)
- Use real MongoDB/Redis in integration tests (no mocks)
- Update documentation immediately with code
- Run full test suite before PR
- Add docstrings to all public functions
- Validate cross-tenant isolation in security tests
- Update CLAUDE.md with new patterns

### MUST NOT DO
- Skip tests to speed up delivery
- Mock real services (use real ones in integration tests)
- Commit code without updated docs
- Create TODO/FIXME markers
- Ignore linting/type checking errors
- Bypass security patterns
- Assume cross-tenant safety

---

## MCP Server Configuration (For Agent Context)

**Recommended MCP Servers**:
- **Context7**: Library documentation (Tailwind, Pydantic, FastAPI, Playwright)
- **Tavily**: Web search for research and documentation
- **morph-mcp**: Semantic code search (natural language queries)

**Discovery**:
```bash
npx mcporter list                    # All available servers
npx mcporter list context7           # Tools in context7
npx mcporter list tavily             # Tools in tavily
```

**Usage Examples**:
```bash
# Tailwind CSS documentation
npx mcporter call context7.query --args '{"library": "tailwindcss", "query": "responsive grid"}'

# Web search
npx mcporter call tavily.tavily_search --args '{"query": "fastapi async patterns"}'

# Semantic code search
npx mcporter call morph-mcp.warpgrep_codebase_search --args '{"query": "authentication logic"}'
```

---

## Success Criteria for Swarm

**Per Feature Delivery**:
- ✅ Feature implemented with tests
- ✅ 100% test pass rate (no flakes)
- ✅ >85% test coverage
- ✅ Documentation synchronized
- ✅ Security scan clear
- ✅ Code review approved

**Per Sprint** (Target: 3-4 features):
- ✅ Story points delivered
- ✅ Zero critical bugs
- ✅ Technical debt not increased
- ✅ Documentation lag = 0 days

---

## Activation Checklist

- [ ] Frontend expert configured and ready
- [ ] Backend expert configured and ready
- [ ] MCP expert ready for on-demand activation
- [ ] MongoDB accessible (docker-compose running)
- [ ] All test suites passing locally
- [ ] Documentation reviewed
- [ ] CodeRabbit configured
- [ ] GitHub Actions CI/CD working
- [ ] First feature task assigned to swarm

---

**For full details, see**: `.claude-flow/project-requirements-analysis.md`

**Questions or issues?** Check documentation files listed above.
