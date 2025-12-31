# Agent Specialization Specifications

**Purpose**: Define exact agent capabilities, responsibilities, and success criteria
**Created**: 2025-12-26
**Status**: Ready for implementation

---

## Agent 1: TypeScript/React Expert (Frontend)

### Identity
- **Name**: Frontend Developer Agent
- **Specialization**: Next.js 15, React 19, TypeScript 5.9, Tailwind CSS
- **Primary Domain**: `apps/frontend/`
- **Model Recommendation**: claude-opus-4-5 (production quality code required)

### Core Responsibilities

#### 1. Page & Component Development
**What**: Build new Next.js pages and React components
- Create pages in `apps/frontend/app/` using App Router
- Build reusable components with TypeScript strict mode
- Implement proper React composition patterns
- Use Radix UI for primitive components when needed
- Integrate Shadcn UI components for complex patterns
- Follow Nova template design system (gray color palette, Hugeicons icons)

**How to Know Success**:
- Page/component created at correct path
- TypeScript types strictly enforced (tsc --noEmit passes)
- ESLint rules pass without errors
- Matches design system standards (Tailwind + Hugeicons)
- Documentation explains component purpose and usage

#### 2. Testing (Jest)
**What**: Write Jest unit tests for components and logic
- Test component rendering and props
- Test user interactions and state changes
- Test hook logic with testing-library
- Achieve >85% coverage on code written

**How to Know Success**:
```bash
cd apps/frontend && npm test
# All tests pass
# Coverage >85%
```

#### 3. Testing (Playwright E2E)
**What**: Write end-to-end tests for user workflows
- Create .spec.ts files in `apps/frontend/__tests__/e2e/`
- Test complete user journeys (upload, transform, train, predict)
- Use Playwright best practices (no hardcoded waits)
- Support multiple browser engines

**How to Know Success**:
```bash
# Smoke tests pass
npm test:e2e:smoke

# Full suite passes
npm test:e2e:full

# Multi-browser passes
npm test:e2e:all
```

#### 4. Styling & Responsive Design
**What**: Style components with Tailwind CSS
- Use gray color palette (not zinc)
- Implement responsive layouts (mobile-first)
- Add animations with Tailwind animation utilities
- Use transition-all for smooth interactions
- Enhanced focus states (ring-[3px]) for accessibility

**How to Know Success**:
- Component looks polished and professional
- Responsive on mobile, tablet, desktop
- Accessible (focus states, ARIA labels)
- Animations smooth and purposeful
- Matches design system (gray, Hugeicons, Nunito Sans)

#### 5. API Integration
**What**: Connect components to backend APIs
- Use axios for HTTP requests
- Handle async loading states
- Implement proper error handling and user feedback
- Type API responses with TypeScript
- Support authentication flow (NextAuth v5)

**How to Know Success**:
- API calls working correctly
- Loading/error states displayed to user
- Types match backend schemas
- Auth flow integrated properly

#### 6. Form Handling
**What**: Build and manage form components
- Create forms with validation
- Handle form submission to backend
- Display validation errors clearly
- Support complex multi-step forms
- Implement proper file upload handling

**How to Know Success**:
- Form validates client-side before submit
- Error messages helpful and clear
- Submission works with backend
- UX is smooth (no unexpected refreshes)

#### 7. Documentation
**What**: Update README and component documentation
- Add JSDoc comments to complex components
- Document component props and usage
- Keep README with accurate feature list
- Update setup instructions if needed

**How to Know Success**:
- JSDoc comments complete and accurate
- README reflects implemented features
- Setup instructions work for new developers

### Quality Gates

#### MANDATORY (Every Submission)
```
✅ npm test passes (100% of tests)
✅ npm run lint passes (ESLint clean)
✅ tsc --noEmit passes (No type errors)
✅ Coverage >85%
✅ E2E smoke tests pass: npm test:e2e:smoke
✅ All JSDoc comments present for public components
```

#### VALIDATION COMMANDS
```bash
# Type checking
tsc --noEmit

# Linting
npm run lint

# Unit tests
npm test

# E2E smoke tests
npm test:e2e:smoke

# Check coverage
npm test:coverage
```

### Dependencies & Versions

| Dependency | Version | Purpose |
|------------|---------|---------|
| next | 15.5.9 | Framework |
| react | 19.2.0 | UI library |
| typescript | 5.9.2 | Type safety |
| tailwindcss | 3.4.1 | Styling |
| @hugeicons/react | Latest | Icons |
| recharts | 2.12.0 | Charts |
| chart.js | 4.4.8 | Charts |
| @playwright/test | 1.56.1 | E2E testing |
| jest | 30.2.0 | Unit testing |

### Key Files & Paths

**Component Locations**:
- Pages: `apps/frontend/app/[feature]/page.tsx`
- Features: 21 modules in `apps/frontend/app/` (upload, datasets, transform, model, predict, etc.)
- Components: `apps/frontend/app/components/` (if shared)
- Tests: `apps/frontend/__tests__/`

**Configuration**:
- `.env.local` - Frontend environment variables
- `tailwind.config.ts` - Tailwind configuration
- `eslint.config.js` - Linting rules
- `jest.config.js` - Test configuration

**Key Patterns**:
- Use React hooks for state management
- Implement proper error boundaries
- Support loading states and optimistic updates
- Validate form input client-side before submit
- Use TypeScript for all code (no implicit `any`)

### Success Metrics

**Quality**:
- Zero test failures
- Zero type errors
- Zero linting errors
- >85% coverage

**Features**:
- Pages created and working
- Components reusable and well-documented
- E2E workflows validated
- Styling matches design system

**Delivery**:
- Features completed per sprint
- Tests written alongside code (not after)
- Documentation updated immediately
- Code review feedback addressed promptly

### Common Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| Async operations hard to test | Use Playwright for E2E, testing-library for units |
| Type mismatches with backend | Use OpenAPI generator or manual type definitions |
| E2E tests flaky | Use Playwright best practices (no hard waits) |
| CSS conflicts | Use Tailwind's scoping, avoid global CSS |
| Performance issues | Profile with Chrome DevTools, optimize with memo/useMemo |

---

## Agent 2: Python/FastAPI Expert (Backend)

### Identity
- **Name**: Backend Developer Agent
- **Specialization**: FastAPI 0.115, Python 3.13, Pydantic 2.11, MongoDB
- **Primary Domain**: `apps/backend/`
- **Model Recommendation**: claude-opus-4-5 (complex business logic required)

### Core Responsibilities

#### 1. API Route Development
**What**: Create FastAPI routes for new features
- Define route in `apps/backend/app/api/`
- Create Pydantic request/response schemas
- Implement async route handler
- Add docstring with description and examples
- Add proper error handling and status codes
- Include authentication/authorization checks

**How to Know Success**:
- Route accessible and documented in OpenAPI spec
- Request validation working
- Response types correct
- Authentication enforced
- Error handling comprehensive

#### 2. Service Layer Logic
**What**: Implement business logic in service classes
- Create service class in `apps/backend/app/services/`
- Use dependency injection
- Implement async methods
- Write comprehensive docstrings
- Handle all error cases

**How to Know Success**:
- Logic separated from routes
- Testable in isolation
- Proper exception handling
- Clear, documented API

#### 3. Data Models & Schemas
**What**: Define data models and validation schemas
- Create Pydantic v2 models in `apps/backend/app/schemas/`
- Create MongoDB document models in `apps/backend/app/models/`
- Include validation rules
- Add docstrings
- Update OpenAPI spec

**How to Know Success**:
- Models properly validated
- MongoDB operations work
- Types correct across codebase
- Documentation complete

#### 4. Database Operations
**What**: Implement MongoDB operations
- Create Beanie ODM models
- Write efficient queries
- Add proper indexing
- Handle versioning and lineage
- Validate cross-tenant isolation

**How to Know Success**:
- Queries efficient (benchmarks show <200ms P50)
- Data integrity maintained
- Cross-tenant data isolated
- Version history tracked

#### 5. Test-Driven Development (CRITICAL)
**What**: Write tests BEFORE implementing features
- Write unit test first (RED)
- Implement feature (GREEN)
- Refactor if needed (REFACTOR)
- Achieve >85% coverage

**Testing Approach**:
```python
# 1. Write failing test
def test_new_feature():
    """Test that new feature works"""
    result = service.new_feature(data)
    assert result.status == "success"

# 2. Implement feature
class Service:
    async def new_feature(self, data):
        # Implementation
        return result

# 3. Run and verify
# pytest tests/test_services/test_new_feature.py -v
```

**How to Know Success**:
```bash
# All tests pass
cd apps/backend && uv run pytest

# Coverage >85%
cd apps/backend && uv run pytest --cov=app --cov-report=term-missing
```

#### 6. Integration Testing
**What**: Test complete workflows with real services
- Test upload → transform → train → predict flows
- Use real MongoDB (not mocks)
- Use real S3 mocking (moto)
- Test error scenarios
- Add performance regression tests

**How to Know Success**:
```bash
# Integration tests passing
cd apps/backend && uv run pytest tests/integration/

# All workflows validated
# Performance targets met (P50 <200ms, P95 <500ms, P99 <1s)
```

#### 7. Security Implementation
**What**: Implement security patterns
- Validate cross-tenant isolation
- Check user ownership of resources
- Implement rate limiting
- Validate PII detection
- Add security test cases

**How to Know Success**:
- No cross-tenant data leaks
- Ownership validation on all operations
- Security tests passing
- Security patterns documented

#### 8. Performance Optimization
**What**: Optimize data operations
- Add Redis caching where appropriate
- Optimize MongoDB queries
- Add connection pooling
- Run benchmarks
- Meet performance targets

**How to Know Success**:
```bash
# Performance targets met
cd apps/backend && uv run pytest tests/benchmarks/ --benchmark-only

# P50 <200ms, P95 <500ms, P99 <1s
```

#### 9. Documentation
**What**: Update API and code documentation
- Add docstrings to all functions
- Update `apps/backend/docs/API.md`
- Document schemas and examples
- Update error codes
- Update CLAUDE.md with patterns

**How to Know Success**:
- API.md includes new endpoints
- Docstrings comprehensive
- Examples provided
- CLAUDE.md updated with patterns

### Quality Gates

#### MANDATORY (Every Submission)
```
✅ cd apps/backend && uv run pytest (100% pass, 214/214 tests)
✅ Coverage >85%
✅ cd apps/backend && uv run mypy app/ (No type errors)
✅ cd apps/backend && uv run ruff check app/ (No linting errors)
✅ All docstrings present for public functions
✅ apps/backend/docs/API.md updated
✅ Security patterns validated (ownership, cross-tenant)
```

#### VALIDATION COMMANDS
```bash
# Run all tests (required: MongoDB running)
cd apps/backend && uv run pytest

# Type checking
cd apps/backend && uv run mypy app/

# Linting
cd apps/backend && uv run ruff check app/

# Coverage report
cd apps/backend && uv run pytest --cov=app --cov-report=html

# Performance benchmarks
cd apps/backend && uv run pytest tests/benchmarks/ --benchmark-only

# Unit tests only (no DB)
cd apps/backend && uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ tests/test_model_training/test_problem_detector.py tests/test_model_training/test_feature_engineer.py -v
```

### Dependencies & Versions

| Dependency | Version | Purpose |
|------------|---------|---------|
| fastapi | 0.115.12 | Framework |
| pydantic | 2.11.5 | Validation |
| beanie | 1.30.0 | MongoDB ODM |
| motor | 3.7.1 | Async MongoDB |
| pandas | 2.3.0 | Data processing |
| scikit-learn | 1.7.0 | ML algorithms |
| xgboost | 3.0.2 | Gradient boosting |
| lightgbm | 4.6.0 | Gradient boosting |
| pytest | 8.4.0 | Testing |
| pytest-asyncio | 0.23.0 | Async tests |
| redis | 6.2.0 | Caching |
| boto3 | 1.38.34 | AWS S3 |

### Key Files & Paths

**Route Locations**:
- API routes: `apps/backend/app/api/`
- Endpoints for: versions, transformations, models, training, predictions

**Service Locations**:
- Services: `apps/backend/app/services/`
- DatasetService, TransformationService, ModelService

**Model Locations**:
- MongoDB models: `apps/backend/app/models/`
- Pydantic schemas: `apps/backend/app/schemas/`

**Test Locations**:
- Unit tests: `apps/backend/tests/test_services/`, `tests/test_security/`, `tests/test_processing/`
- Integration tests: `apps/backend/tests/integration/`
- Benchmarks: `apps/backend/tests/benchmarks/`
- Fixtures: `apps/backend/tests/conftest.py`

**Configuration**:
- `.env` - Environment variables
- `pyproject.toml` - Dependencies
- `pytest.ini` - Test configuration

### Key Patterns

**TDD Approach**:
1. Write failing test first
2. Implement feature to pass test
3. Refactor for clarity
4. Ensure >85% coverage

**Data Model Architecture**:
```
DatasetMetadata ──> TransformationConfig ──> ModelConfig
         │                  │                      │
         └──────────────────┴──────────────────────┘
                      ↓
                Service Layer
         (DatasetService, TransformationService, ModelService)
```

**Async Patterns**:
- Use `async def` for all route handlers
- Use `await` for async operations
- Proper async error handling with try/except
- pytest-asyncio for testing async code

**Database Patterns**:
- Beanie for ODM
- Proper indexing for performance
- Cross-tenant isolation checks
- Version tracking and lineage

**Error Handling**:
- Use appropriate HTTP status codes
- Return error details in response
- Log errors for debugging
- Test error scenarios

### Success Metrics

**Quality**:
- 100% test pass rate (214/214)
- >85% coverage
- Zero type errors (mypy)
- Zero linting errors (ruff)
- All docstrings present

**Performance**:
- P50 <200ms
- P95 <500ms
- P99 <1s

**Security**:
- No cross-tenant leaks
- Ownership validation on all operations
- PII detection working
- Security tests passing

**Delivery**:
- Features completed per sprint
- Tests written first (TDD)
- Documentation updated immediately
- Code review feedback addressed

### Common Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| Async complexity | Use pytest-asyncio, write tests first |
| DB not running | `docker-compose up mongo` to start MongoDB |
| Integration test failures | Ensure MongoDB/Redis running, check fixtures |
| Type errors | Run mypy early, use strict mode |
| Performance regression | Run benchmarks, use Redis caching |
| Cross-tenant bugs | Add ownership validation tests |

---

## Agent 3: Python/FastMCP Expert (MCP Server)

### Identity
- **Name**: MCP Tool Developer Agent
- **Specialization**: FastMCP, Python 3.13, Tool Development
- **Primary Domain**: `apps/mcp/`
- **Model Recommendation**: claude-opus-4-5
- **Activation**: On-demand (activate when MCP tools needed)

### Core Responsibilities

#### 1. Tool Development
**What**: Create MCP tools for advanced operations
- Define tool in FastMCP format
- Implement tool function
- Add proper input validation
- Write comprehensive docstrings
- Add tool tests

**How to Know Success**:
- Tool callable through MCP protocol
- Input validation working
- Output correct and useful
- Documentation complete

#### 2. Integration with Backend
**What**: Integrate MCP tools with backend services
- Access backend APIs where needed
- Coordinate with FastAPI services
- Maintain async patterns
- Handle errors properly

**How to Know Success**:
- Tool communicates with backend correctly
- Data flows properly
- Errors handled gracefully
- Performance acceptable

#### 3. Testing
**What**: Write tests for MCP tools
- Unit tests for tool logic
- Integration tests with backend
- Test error scenarios
- Achieve good coverage

**How to Know Success**:
```bash
cd apps/mcp && uv run pytest
# All tests pass
```

### Quality Gates

#### MANDATORY
```
✅ cd apps/mcp && uv run pytest (100% pass)
✅ Tool properly documented
✅ Integration with backend validated
```

### Dependencies & Versions

| Dependency | Version | Purpose |
|------------|---------|---------|
| fastmcp | Latest | MCP framework |
| pytest | 8.4+ | Testing |

### Key Files & Paths

**Tool Locations**:
- Tools: `apps/mcp/tools/`
- Utilities: `apps/mcp/utils/`
- Tests: `apps/mcp/tests/`

### Success Metrics

**Functionality**:
- Tools work correctly
- Integration seamless
- Performance acceptable

**Quality**:
- 100% test pass rate
- Tests cover main scenarios

---

## Cross-Agent Coordination

### API Contract Flow

```
1. Backend Expert: Designs and implements API
   - Creates routes in FastAPI
   - Defines request/response schemas
   - Adds docstrings

2. Frontend Expert: Consumes API
   - Uses API in components
   - Type-checks responses
   - Implements error handling

3. Both: Coordinate
   - Verify contract matches
   - Test integration
   - Update documentation together
```

### Documentation Handoff

**Backend Responsibilities**:
- Create/update `apps/backend/docs/API.md`
- Add docstrings to routes and schemas
- Document error codes
- Provide example requests/responses

**Frontend Responsibilities**:
- Document component usage
- Add JSDoc comments
- Update README with features
- Document form validation

**Shared Responsibilities**:
- Update main `CLAUDE.md` with patterns
- Keep README accurate
- Maintain API.md synchronization

### Timing Coordination

**Ideal Sequence**:
1. Backend: API contract designed (routes + schemas)
2. Backend: Routes implemented with tests
3. Frontend: Components created consuming API
4. Frontend: E2E tests validate workflows
5. All: Documentation synchronized
6. All: PR review and merge

**Parallel Work**:
- Backend and Frontend can work in parallel after contract definition
- MCP tools developed independently if needed

### Quality Validation

**Backend Then Frontend**:
```bash
# Backend validates locally
cd apps/backend && uv run pytest

# Frontend validates locally
cd apps/frontend && npm test

# Integration test
npm test:e2e:smoke
```

**Before Merge**:
```
□ Backend: All 214 tests pass
□ Frontend: All tests pass
□ Coverage: >85% both
□ Types: mypy + tsc clean
□ Linting: ruff + eslint clean
□ Docs: API.md, docstrings, CLAUDE.md updated
```

---

## Summary Table

| Aspect | Frontend | Backend | MCP |
|--------|----------|---------|-----|
| **Language** | TypeScript | Python | Python |
| **Framework** | Next.js 15 | FastAPI 0.115 | FastMCP |
| **Domain** | apps/frontend/ | apps/backend/ | apps/mcp/ |
| **Test Command** | npm test | uv run pytest | uv run pytest |
| **E2E Testing** | Playwright | Integration | Pytest |
| **Coverage Target** | >85% | >85% | >85% |
| **Quality Gates** | tsc/eslint clean | mypy/ruff clean | Tests pass |
| **Deploy Target** | dev.briaanalytics.com | dev.briaanalytics.com | N/A |

---

**Document Version**: 1.0
**Last Updated**: 2025-12-26
**Next Review**: After first agent deployment
