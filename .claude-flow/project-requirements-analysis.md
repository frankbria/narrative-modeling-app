# Narrative Modeling App - Swarm Requirements Analysis

**Date**: 2025-12-26
**Status**: Complete
**Purpose**: Define agent specialization needs and task types for swarm orchestration

---

## Executive Summary

The Narrative Modeling App is a complex machine learning platform spanning 3 primary applications (Frontend, Backend, MCP Server) across 2 languages (TypeScript, Python). A coordinated swarm requires **3-4 specialized agent types** to handle distinct domains effectively while maintaining quality gates (100% test pass rate, >85% coverage, security scanning).

---

## 1. Project Architecture Overview

### Applications Landscape

| App | Type | Language | Framework | Purpose |
|-----|------|----------|-----------|---------|
| **Frontend** | Web UI | TypeScript | Next.js 15.5 | User interface, data visualization, model exploration |
| **Backend** | API Server | Python | FastAPI | Data processing, ML training, API endpoints |
| **MCP Server** | Tool Provider | Python | FastMCP | Advanced data operations, tool exposure |

### Monorepo Structure
```
narrative-modeling-app/
├── apps/
│   ├── frontend/          # Next.js app
│   │   ├── app/          # 21 feature modules
│   │   ├── __tests__/    # Jest + Playwright tests
│   │   └── package.json  # 33 dependencies
│   ├── backend/          # FastAPI app
│   │   ├── app/          # 7 service modules + API
│   │   ├── tests/        # 214 tests (100% passing)
│   │   └── pyproject.toml # 46 dependencies
│   └── mcp/              # FastMCP server
│       ├── tools/        # Custom MCP tools
│       └── tests/        # Pytest suite
├── .beads/               # Issue tracking database
└── .claude-flow/         # Workflow orchestration
```

---

## 2. Common Task Types & Frequency

### Frontend Tasks (35-40% of work)
**Frequency**: High (2-3 features/sprint)

#### Feature Development
- **Page creation** (Next.js App Router): `upload`, `datasets`, `transform`, `model`, `predict`, etc.
- **Component building**: Forms, dialogs, data tables, visualizations
- **Authentication integration**: NextAuth v5 with Google/GitHub providers
- **Styling**: Tailwind CSS with custom animations and responsive design

#### Testing & Quality
- **Jest unit tests**: Component logic, hooks, utilities
- **Playwright E2E tests**: User workflows, navigation, data flow
- **Type safety**: TypeScript strict mode compliance
- **Linting**: ESLint configuration, Next.js best practices

#### Complex Interactions
- **State management**: React hooks, form handling with complex validation
- **Data visualization**: Chart.js, Recharts integration, real-time updates
- **File operations**: CSV/Excel upload, data transformation UI
- **Modal/dialog workflows**: Complex multi-step data capture

---

### Backend Tasks (35-40% of work)
**Frequency**: High (3-4 features/sprint)

#### API Development
- **Route handlers**: FastAPI endpoints with async/await
- **Schema definition**: Pydantic models with validation
- **Data versioning**: Lineage tracking, recipe management
- **API documentation**: OpenAPI specs, docstring updates

#### Data Processing
- **Transformation pipeline**: CSV parsing, data cleaning, feature engineering
- **Data validation**: Type checking, PII detection, data quality assessment
- **S3 integration**: File upload/download, URL management
- **ML model training**: Scikit-learn, XGBoost, LightGBM integration

#### Database & Persistence
- **MongoDB operations**: Beanie ODM queries, document modeling
- **Query optimization**: Indexing, aggregation pipelines
- **Data migration**: Schema updates, data versioning
- **Connection pooling**: Redis caching, performance optimization

#### Testing & Quality
- **Unit tests**: 203 tests covering services, utilities, security
- **Integration tests**: 11 tests requiring MongoDB, real service interaction
- **Fixture management**: Complex async test setup with real databases
- **Performance testing**: Benchmarking, load testing with pytest-benchmark

---

### MCP Server Tasks (10-15% of work)
**Frequency**: Medium (1-2 features/sprint)

- **Tool development**: FastMCP tool definitions for advanced operations
- **Data processing**: Specialized algorithms, ML utilities
- **Integration**: Bridging frontend/backend through MCP protocol
- **Testing**: Python pytest suite specific to MCP tools

---

### DevOps/Infrastructure (10-15% of work)
**Frequency**: Medium (per-sprint)

- **GitHub Actions**: CI/CD pipeline maintenance, test execution
- **Environment management**: .env configuration, secrets handling
- **Deployment**: Staging server (dev.briaanalytics.com), production deployment
- **Documentation**: API docs, deployment guides, setup instructions

---

## 3. Quality Requirements & Gates

### Testing Standards (MANDATORY - 100% Pass Rate)

#### Backend Requirements
- **Total Tests**: 214/214 passing (100%)
- **Unit Tests**: 203 tests (no database required)
  - Service layer: DatasetService, TransformationService, ModelService
  - Security: PII detection, data validation, auth
  - Processing: Feature engineering, model training, data cleanup
  - Utils: Helpers, formatters, validators
- **Integration Tests**: 11 tests (require MongoDB running)
  - Full workflow tests: upload → transform → train → predict
  - E2E integration paths
- **Performance Tests**: Benchmark suite with regression detection
- **Command**: `cd apps/backend && uv run pytest`
- **Unit Tests Only**: `cd apps/backend && uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ tests/test_model_training/test_problem_detector.py tests/test_model_training/test_feature_engineer.py -v`

#### Frontend Requirements
- **Testing Framework**: Jest for unit tests
- **E2E Testing**: Playwright with multiple browser engines
- **Test Command**: `cd apps/frontend && npm test`
- **E2E Variants**:
  - Smoke tests: `npm test:e2e:smoke`
  - Full suite: `npm test:e2e:full`
  - Multi-browser: `npm test:e2e:all` (chromium, firefox, webkit)
  - Debug mode: `npm test:e2e:debug`

#### MCP Server Requirements
- **Framework**: Python pytest
- **Command**: `cd apps/mcp && uv run pytest`

### Code Quality Gates (PRE-MERGE CHECKLIST)

```
MANDATORY (Must Pass):
✅ All tests pass (100% pass rate, zero flakes)
✅ Test coverage >85%
✅ Linting passes (ruff + eslint)
✅ Type checking passes (mypy + tsc)
✅ No TODO/FIXME/NotImplementedError markers
✅ Security scan clears OWASP patterns
✅ Documentation synchronized with code

OPTIONAL (CodeRabbit Auto-Fix):
- Code style and formatting
- Type errors
- Simple logic bugs
- Documentation improvements

BLOCKER TRIGGERS (Human Review Required):
- Iteration 3 still has failing tests
- Architecture change suggestions
- Security vulnerabilities requiring decision
```

### Documentation Synchronization

All implementation must update corresponding documentation:

1. **API Documentation** (`apps/backend/docs/API.md`)
   - Request/response schemas
   - Example requests and responses
   - Error responses and status codes

2. **Code Documentation**
   - Python: Docstrings for all public functions/classes
   - TypeScript: JSDoc for complex functions/components
   - Remove outdated comments immediately

3. **Implementation Docs** (`apps/backend/docs/`)
   - Update CLAUDE.md with new patterns
   - Keep architecture diagrams current
   - Document breaking changes

4. **README Updates**
   - Feature lists
   - Setup instructions
   - Accurate command examples
   - Version compatibility

---

## 4. Agent Specialization Requirements

### Agent Type 1: TypeScript/React Expert (Frontend)
**Needed**: YES - High Priority

#### Responsibilities
- Page and component creation using Next.js App Router
- State management with React hooks
- Form handling with validation
- Authentication integration (NextAuth v5)
- Styling with Tailwind CSS
- Chart/visualization integration (Chart.js, Recharts)
- File upload/processing UI
- Jest unit testing
- Playwright E2E testing

#### Required Skills
- Next.js 15+ framework patterns
- React 19+ hooks and composition
- TypeScript strict mode
- Tailwind CSS (responsive, animations)
- Testing: Jest + Playwright
- Form libraries (if applicable)

#### Testing Requirements
- Write and maintain Jest tests alongside components
- E2E test coverage for critical user flows
- Must pass all frontend tests before PR merge
- Coverage target: >85%

#### Key Dependencies
- React 19.2
- Next.js 15.5
- TypeScript 5.9
- Tailwind CSS 3.4
- Chart.js 4.4
- @playwright/test 1.56

---

### Agent Type 2: Python/FastAPI Expert (Backend)
**Needed**: YES - High Priority

#### Responsibilities
- FastAPI route handler creation
- Pydantic schema design and validation
- MongoDB/Beanie ODM queries and migrations
- Data processing and transformation pipeline
- ML model training and evaluation
- S3 integration and file management
- Service layer logic
- Unit and integration testing
- Performance optimization

#### Required Skills
- FastAPI async/await patterns
- Pydantic v2 data validation
- Beanie ODM for MongoDB
- Pandas/NumPy data processing
- Scikit-learn/XGBoost/LightGBM training
- Pytest with async test support
- Database design and optimization
- AWS S3 operations

#### Testing Requirements
- TDD approach: Write tests first
- Unit tests covering all service logic
- Integration tests for workflows
- Async test patterns with pytest-asyncio
- Real MongoDB/Redis in integration tests (no mocks)
- Performance benchmarks for data operations
- Must achieve 100% test pass rate

#### Key Dependencies
- FastAPI 0.115
- Pydantic 2.11
- Beanie 1.30 (MongoDB ODM)
- Motor 3.7 (Async MongoDB)
- Scikit-learn 1.7
- XGBoost 3.0
- LightGBM 4.6
- Pytest 8.4 + pytest-asyncio
- Redis 6.2

---

### Agent Type 3: Python/FastMCP Expert (MCP Server)
**Needed**: YES - Medium Priority

#### Responsibilities
- FastMCP tool development
- Custom tool definitions and handlers
- Data processing algorithms
- Integration with backend services
- Unit testing for MCP tools

#### Required Skills
- FastMCP framework
- Python async patterns
- Tool definition semantics (MCP protocol)
- Integration with backend APIs
- Pytest for MCP tool testing

#### Testing Requirements
- Pytest unit tests for all tools
- Tool execution validation
- Integration with backend services

#### Key Dependencies
- FastMCP framework
- Python 3.13+
- Pytest

---

### Agent Type 4: DevOps/Infrastructure (Optional)
**Needed**: NICE-TO-HAVE - Lower Priority

#### Responsibilities
- GitHub Actions CI/CD pipeline maintenance
- Environment setup and configuration
- Deployment orchestration
- Performance monitoring
- Security scanning

#### Required Skills
- GitHub Actions workflow syntax
- Deployment process understanding
- Environment variable management
- CI/CD best practices

---

## 5. Workflow & Coordination Patterns

### Feature Development Workflow

```
DISCOVERY & PLANNING
├─ Requirements analysis (human-led)
├─ Acceptance criteria definition
└─ Task breakdown into Backend + Frontend work

IMPLEMENTATION (Parallel Tracks)
├─ Backend Track (Python/FastAPI Expert)
│  ├─ Write test first (TDD approach)
│  ├─ Implement API route/schema
│  ├─ Service layer logic
│  ├─ Database schema updates
│  └─ All tests passing
├─ Frontend Track (TypeScript/React Expert)
│  ├─ Component design/structure
│  ├─ Jest unit tests
│  ├─ Playwright E2E tests
│  └─ Styling with Tailwind
└─ MCP Track (if needed - Python/FastMCP Expert)
   ├─ Tool development
   └─ Tool integration tests

QUALITY GATES
├─ Backend: 100% tests passing, >85% coverage, mypy clean
├─ Frontend: All tests passing, tsc clean, eslint clean
├─ MCP: Tests passing
├─ Documentation synchronized
└─ Security scan clear

REVIEW & MERGE
├─ Code review (CodeRabbit + human)
├─ Address feedback
└─ Merge to main with PR
```

### Task Handoff Protocol

**Between Agents**:
- Backend completes API contract (schema + routes)
- Frontend consumes API and creates UI
- MCP bridges advanced operations as needed
- Documentation shared across all agents

**Quality Validation**:
- Each agent runs full test suite before merge
- Cross-team integration verification
- Documentation audit

---

## 6. Project-Specific Patterns & Conventions

### Data Model Architecture (Key Pattern)

The project uses **domain-driven design** with split models:
- `DatasetMetadata`: Dataset configuration and provenance
- `TransformationConfig`: Transformation recipe definition
- `ModelConfig`: ML model configuration

**Service Layer**: Coordinating logic between models
- `DatasetService`: Dataset operations
- `TransformationService`: Data transformation workflows
- `ModelService`: Model training and predictions

**Importance**: Agents must understand this layering when implementing new features.

### Data Versioning & Lineage

Critical pattern for Sprint 12+ features:
- Version parent-child relationships
- Transformation lineage tracking
- Recipe management for reusable transformations
- Version comparison capabilities

**Impact**: All data operations must track version history.

### Transformation History System (Recent Addition)

Comprehensive undo/redo system with:
- Step-by-step transformation history
- Checkpoint management
- History comparison
- Security: Ownership validation (prevent cross-tenant data access)

**Impact**: Frontend must integrate history UI, backend must track all changes.

### Performance Requirements

From Sprint 12 optimization:
- P50 <200ms
- P95 <500ms
- P99 <1s
- Redis caching for query optimization
- Connection pooling for MongoDB/Redis

**Testing**: Performance regression tests required for data operations.

### Security Patterns

Critical patterns agents must follow:
1. **PII Detection**: Automatic detection in data columns
2. **Cross-Tenant Isolation**: Strict ownership validation
3. **API Key Management**: Production deployment security
4. **Rate Limiting**: Production API endpoints

**Testing**: Security-focused unit tests required.

---

## 7. Recent Sprint Context (Sprints 11-12)

### Sprint 11 Status: COMPLETE ✅
- Data model refactoring complete
- Service layer integration done
- 214 tests passing (100%)
- Performance benchmarks established

### Sprint 12 Status: 87% COMPLETE (33/38 points)

**Completed**:
- Story 12.1: API Integration for New Models (10 pts) ✅
- Story 12.2: Data Versioning API (8 pts) ✅
- Story 12.3: Production Deployment Features (10 pts) ✅
- Story 12.4: Performance Optimization (5 pts) ✅
- Critical bug fixes: 11 runtime bugs + 1 security vulnerability fixed (PR #48)

**Pending**:
- Story 12.5: E2E Integration Testing (5 pts)
  - Fix test fixture dependencies
  - Update mocking for new domain models
  - Add missing workflow coverage
  - Implement error recovery scenarios
  - Estimated: 6-8 hours

### Recent Critical Fixes (PR #48 - 2025-11-11)
- **Impact**: CRITICAL - 11 runtime bugs + security fix
- **Files**: 8 files affected, 13 specific fixes
- **Security Fix**: Cross-tenant data leak in visualization endpoints
- **Patterns**: Timezone handling, S3 URL parsing, file type detection
- **Learning**: These patterns inform future implementations

---

## 8. Tooling & Environment

### Development Environment

**Backend**:
- Python: 3.13+
- Package Manager: `uv` (preferred over pip)
- Virtual Env: `uv venv`
- Dependencies: `uv sync`
- Testing: `uv run pytest`

**Frontend**:
- Node.js: via `nvm`
- Package Manager: `npm`
- Build: `npm run build`
- Testing: `npm test`
- Dev Server: `next dev`

**MCP**:
- Python 3.13+
- `uv` for dependency management
- Pytest for testing

### Recommended MCP Servers for Agent Use

**Context7** (Library Documentation):
- Tailwind CSS: Class names and responsive patterns
- Pydantic: Data validation patterns
- FastAPI: Async patterns, middleware
- Playwright: E2E testing patterns

**Tavily Web Search**:
- Research library updates
- Find documentation
- Security advisories

**morph-mcp (Semantic Code Search)**:
- Find authentication logic
- Locate error sources
- Understand code patterns
- NOT for exact string matches (use Grep for that)

### CI/CD Infrastructure

- **GitHub Actions**: Automated testing on PR and merge
- **Staging**: dev.briaanalytics.com (Nginx + SSL)
- **Service Management**: PM2 on staging
- **Test Execution**: Automated on every PR

---

## 9. Swarm Orchestration Strategy

### Recommended Configuration

**Primary Agents** (Always Active):
1. **TypeScript/React Expert**: Frontend development, testing, UI
2. **Python/FastAPI Expert**: Backend development, testing, APIs
3. **Python/FastMCP Expert**: MCP tool development (on-demand for relevant features)

**Supporting Capabilities**:
- Use `searching-code` skill for codebase exploration
- Use `reviewing-code` skill for PR reviews
- Use `managing-gitops-ci` for deployment issues
- Use sequential-thinking for complex architectural decisions

### Task Distribution Model

```
INCOMING FEATURE REQUEST
    ↓
[Requirements Analysis]
    ↓
┌─────────────────────────────────────────┐
│ FRONTEND TRACK                          │ BACKEND TRACK           │ MCP TRACK (if needed)
│ (TypeScript/React Expert)               │ (Python/FastAPI Expert) │ (Python/FastMCP)
├─────────────────────────────────────────┤
│ • Create pages/components                │ • Design API schema     │ • Create tools
│ • Write Jest tests                       │ • Implement routes      │ • Test tool logic
│ • Playwright E2E tests                   │ • Service layer logic   │
│ • Tailwind styling                       │ • Write unit tests      │
│ • Type safety (TypeScript)               │ • Integration tests     │
│                                          │ • DB schema updates     │
└─────────────────────────────────────────┘
                    ↓
         [Quality Gate Validation]
         ✅ Tests pass
         ✅ Coverage >85%
         ✅ Linting clean
         ✅ Type checking clean
         ✅ Docs synchronized
         ✅ Security scan clear
                    ↓
         [Coordinated PR Merge]
         All agents contribute documentation
         Human review coordinates timing
```

### Coordination Points

1. **API Contract Definition**
   - Backend defines schema first
   - Frontend consumes with type generation (if using openapi-generator)

2. **Shared Documentation**
   - All agents update API docs
   - All agents update CLAUDE.md with patterns
   - All agents maintain README accuracy

3. **Timing Coordination**
   - Backend routes complete before frontend consumption
   - Frontend and backend can develop in parallel once contract defined
   - MCP tools optional but should integrate before final merge

---

## 10. Success Metrics for Swarm

### Quality Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Test Pass Rate | 100% | 100% ✅ |
| Test Coverage | >85% | >85% ✅ |
| Type Safety (Errors) | 0 | 0 ✅ |
| Linting Issues | 0 | 0 ✅ |
| Documentation Sync | 100% | 95% |
| Security Scan Clear | Yes | Yes ✅ |

### Productivity Metrics

| Item | Target | Notes |
|------|--------|-------|
| Features per Sprint | 3-4 | Currently delivering |
| Bug Fix Time | <2 hours | Recent PR #48 met this |
| Documentation Lag | 0 days | Update immediately with code |
| PR Merge Time | <1 day | CodeRabbit + human review |

---

## 11. Known Challenges & Mitigation

### Challenge 1: TypeScript/Python Integration
**Issue**: Type contract between frontend and backend can drift
**Mitigation**:
- Backend provides OpenAPI spec
- Frontend generates types from spec (optional)
- Integration tests verify contract

### Challenge 2: Async Complexity
**Issue**: Python async/await and frontend promise chains can be error-prone
**Mitigation**:
- Use TDD approach (tests first)
- Backend: pytest-asyncio for async test patterns
- Frontend: Playwright handles async automatically

### Challenge 3: Database Dependency
**Issue**: Integration tests require MongoDB running
**Mitigation**:
- Unit tests (203 tests) run without database
- Integration tests (11 tests) documented to require MongoDB
- CI/CD includes database setup
- Developers must `docker-compose up` locally

### Challenge 4: Performance Regression
**Issue**: Data operations can degrade with scale
**Mitigation**:
- Benchmark suite in backend
- Performance targets: P50 <200ms, P95 <500ms, P99 <1s
- Agents must run benchmarks before PR
- Redis caching layer active

### Challenge 5: Security Patterns
**Issue**: PII detection and cross-tenant isolation require careful implementation
**Mitigation**:
- Dedicated security test suite
- Pattern documentation in DEVELOPER_GUIDE_DATA_ISSUES.md
- Code review focus on security
- Recent PR #48 fixed critical cross-tenant leak

---

## 12. Key Resources & Documentation

### Essential Documentation Files

**Backend Documentation**:
- `apps/backend/docs/SPRINTS.md` - Sprint history and current status
- `apps/backend/docs/TDD_GUIDE.md` - Test-driven development patterns
- `apps/backend/docs/TEST_INFRASTRUCTURE.md` - Test setup and organization
- `apps/backend/docs/TEST_STANDARDS.md` - Quality requirements
- `apps/backend/docs/API.md` - API endpoint documentation
- `apps/backend/docs/CRITICAL_BUG_FIXES_PR48.md` - Recent critical fixes
- `apps/backend/docs/DEVELOPER_GUIDE_DATA_ISSUES.md` - Data issue patterns
- `apps/backend/docs/RECIPE_SYSTEM.md` - Transformation recipe system
- `apps/backend/docs/TRANSFORMATIONS.md` - Transformation patterns
- `apps/backend/docs/VERSIONING.md` - Data versioning system

**Project Configuration**:
- `CLAUDE.md` - Global conventions and stack preferences
- `/home/frankbria/projects/narrative-modeling-app/CLAUDE.md` - Project-specific patterns
- `pyproject.toml` - Backend dependencies
- `package.json` - Frontend dependencies

**Code Locations**:
- Backend API: `apps/backend/app/api/`
- Backend Services: `apps/backend/app/services/`
- Backend Models: `apps/backend/app/models/`
- Backend Tests: `apps/backend/tests/`
- Frontend Pages: `apps/frontend/app/` (21 feature modules)
- Frontend Tests: `apps/frontend/__tests__/`
- MCP Tools: `apps/mcp/tools/`
- MCP Tests: `apps/mcp/tests/`

---

## 13. Next Steps for Swarm Activation

### Phase 1: Prepare Infrastructure
- [ ] Configure TypeScript/React expert agent
- [ ] Configure Python/FastAPI expert agent
- [ ] Configure Python/FastMCP expert agent (on-demand)
- [ ] Set up MCP server context (Context7, Tavily, morph-mcp)
- [ ] Initialize claude-flow orchestration

### Phase 2: Warm-Up Cycle
- [ ] Verify frontend agent can run tests successfully
- [ ] Verify backend agent can run full test suite
- [ ] Confirm integration test environment (MongoDB)
- [ ] Validate code review workflow with CodeRabbit

### Phase 3: Feature Delivery
- [ ] Activate swarm for Sprint 12.5 (E2E Integration Testing)
- [ ] Monitor coordination between agents
- [ ] Validate quality gates (100% tests, coverage, docs)
- [ ] Iterate on handoff processes

---

## Conclusion

The Narrative Modeling App requires a **3-agent swarm** (TypeScript, Python/FastAPI, Python/FastMCP) operating in **parallel tracks** with strong **quality gates** (100% test pass rate, >85% coverage, security scanning, documentation sync). Success depends on:

1. **Specialized expertise** in each domain (React, FastAPI, MCP)
2. **TDD-first approach** for reliability
3. **Real integration testing** (no mocks)
4. **Coordinated API contracts** between frontend/backend
5. **Comprehensive documentation** synchronized with code
6. **Performance awareness** (benchmarks required)
7. **Security focus** (PII detection, cross-tenant isolation)

The swarm model enables **3-4 features per sprint** while maintaining **zero technical debt** accumulation through immediate testing and documentation updates.

---

**Document Version**: 1.0
**Last Updated**: 2025-12-26
**Next Review**: After first swarm activation cycle
