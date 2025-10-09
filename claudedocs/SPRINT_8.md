# Sprint 8: Resilience & API Versioning

**Sprint Duration**: Weeks 3-4 (2025-10-21 to 2025-11-04)
**Sprint Goal**: Implement production-grade resilience patterns with circuit breakers and establish API versioning strategy
**Velocity Target**: 28 story points
**Risk Level**: High (breaking changes with API versioning)

---

## Sprint Overview

Building on Sprint 7's production readiness achievements (JWT authentication and comprehensive health checks), Sprint 8 focuses on:

1. **Resilience Patterns** - Circuit breakers for external service failures
2. **API Versioning** - Establish versioned API endpoints for safe evolution
3. **Test Infrastructure** - Fix test suite issues discovered in Sprint 7
4. **Integration Documentation** - Document resilience and versioning patterns

### Prerequisites from Sprint 7
- ✅ JWT authentication validated and working
- ✅ Comprehensive health checks with parallel execution
- ✅ Production-ready monitoring infrastructure

### Known Technical Debt
- Test suite requires MongoDB connection (integration test infrastructure)
- Some async test fixtures have event loop issues
- Test coverage at 87.4% (target: >95%)

---

## User Stories

### Story 8.1: Circuit Breakers for External Services
**Priority**: 🔴 Critical
**Points**: 13
**Status**: Not Started

**Objective**: Implement circuit breakers on all external service calls so failures cascade gracefully and systems can recover automatically.

#### Acceptance Criteria
- [ ] S3 down → circuit opens, fallback to error response without retry storms
- [ ] OpenAI API fails 5 times → circuit breaker triggers, fail fast for 60s
- [ ] MongoDB recovers → circuit closes, normal operations resume
- [ ] Circuit breaker metrics exposed for monitoring
- [ ] Exponential backoff with jitter prevents thundering herd

#### Technical Implementation

**1. Circuit Breaker Library Setup (2h)**
- Add `tenacity==8.2.3` to requirements.txt
- Create `app/utils/circuit_breaker.py` with base CircuitBreaker class
- Implement state management (CLOSED, OPEN, HALF_OPEN)
- Configure exponential backoff: base 2s, max 60s with jitter

**2. S3 Circuit Breaker (3h)**
- File: `app/services/s3_service.py:15-180`
- Wrap upload, download, delete operations with @retry decorator
- Config: max_attempts=5, stop_after_delay=120s
- Fallback: return cached metadata or structured error
- Emit circuit breaker metrics (open/close events)

**3. OpenAI Circuit Breaker (3h)**
- File: `app/services/openai_service.py:20-150`
- Wrap analyze_data, generate_insights with circuit breaker
- Config: max_attempts=3, circuit_open_duration=60s
- Fallback: return generic insights or queue for retry
- Handle rate limiting separately from circuit breaker

**4. MongoDB Circuit Breaker (3h)**
- File: `app/storage/mongodb_storage.py:30-200`
- Wrap find, insert, update, delete operations
- Config: max_attempts=5, exponential backoff
- Fallback: return stale cache or error with retry guidance
- Implement connection pool health checks

**5. Circuit Breaker Metrics (2h)**
- File: `app/middleware/circuit_metrics.py` (new)
- Expose circuit state (open/closed/half_open) as metrics
- Track failure rates, recovery times, fallback usage
- Integrate with /health endpoint
- Add Prometheus metrics endpoint

#### Dependencies
- Sprint 7.2: Health checks (to detect failures)

#### Risks
- Circuit breaker tuning requires production load testing
- Fallback strategies may not handle all edge cases
- Metrics overhead could impact performance

---

### Story 8.2: API Versioning Implementation
**Priority**: 🔴 Critical
**Points**: 8
**Status**: Not Started

**Objective**: Version all API endpoints with `/api/v1/` prefix and establish backward compatibility strategy.

#### Acceptance Criteria
- [ ] All endpoints accessible via `/api/v1/` prefix
- [ ] Version negotiation via Accept header: `application/vnd.narrativeml.v1+json`
- [ ] Legacy endpoints redirect to v1 with deprecation warning
- [ ] API version documented in OpenAPI spec
- [ ] Frontend updated to use v1 endpoints

#### Technical Implementation

**1. V1 API Router Structure (2h)**
- File: `app/api/v1/__init__.py` (new)
- Create versioned router with `/api/v1` prefix
- Move all existing routes to v1 namespace
- Maintain backward compatibility (temporary)

**2. Update Route Files (3h)**
- Files: All in `app/api/routes/`
- Update: `@router.get("/datasets")` → `@router.get("/api/v1/datasets")`
- Update internal route references
- Update CORS configuration for new paths

**3. Version Negotiation Middleware (2h)**
- File: `app/middleware/api_version.py` (new)
- Parse Accept header for version preference
- Default to v1 if no version specified
- Return 406 Not Acceptable for unsupported versions
- Add deprecation warnings for legacy endpoints

**4. Frontend API Client Update (1h)**
- File: `apps/frontend/lib/api-client.ts`
- Update base URL to `/api/v1`
- Add version header to all requests
- Handle version mismatch errors gracefully

#### Dependencies
- Sprint 7 complete (stable baseline for versioning)

#### Risks
- Breaking changes require coordinated frontend deployment
- Legacy endpoint deprecation timeline needs communication
- Version negotiation adds latency

---

### Story 8.3: Test Infrastructure Fixes
**Priority**: 🔴 Critical
**Points**: 5
**Status**: Not Started

**Objective**: Fix test infrastructure issues discovered in Sprint 7 to enable reliable CI/CD.

#### Acceptance Criteria
- [ ] Unit tests run without MongoDB dependency
- [ ] Integration tests properly configure test database
- [ ] Async test fixtures resolve event loop conflicts
- [ ] Test suite completes in <5 minutes
- [ ] All 151 tests passing

#### Technical Implementation

**1. Separate Unit and Integration Tests (1.5h)**
- Create pytest markers: `@pytest.mark.unit` and `@pytest.mark.integration`
- Configure `pytest.ini` for test categories
- Update CI to run unit tests without database
- Document test infrastructure requirements

**2. Fix MongoDB Test Configuration (1.5h)**
- File: `tests/conftest.py`
- Implement proper test database setup/teardown
- Use MongoDB in-memory or Docker container
- Fix async context manager issues
- Add connection pooling for tests

**3. Resolve Async Fixture Issues (1h)**
- Fix event loop conflicts in async fixtures
- Use `pytest-asyncio` properly
- Ensure fixtures cleanup correctly
- Add async context validation

**4. Test Performance Optimization (1h)**
- Parallelize test execution where possible
- Cache expensive setup operations
- Optimize slow tests
- Add test execution monitoring

#### Dependencies
- None (can start immediately)

#### Risks
- MongoDB test instance may slow CI pipeline
- Async issues may require significant refactoring

---

### Story 8.4: Integration Documentation
**Priority**: 🟡 Important
**Points**: 2
**Status**: Not Started

**Objective**: Document circuit breaker patterns and API versioning strategy for team knowledge sharing.

#### Acceptance Criteria
- [ ] Circuit breaker patterns documented with examples
- [ ] API versioning strategy documented
- [ ] Migration guide for v1 API created
- [ ] Runbook for circuit breaker incidents

#### Technical Implementation

**1. Circuit Breaker Documentation (1h)**
- File: `docs/architecture/circuit-breakers.md` (new)
- Explain circuit breaker states and transitions
- Provide configuration examples
- Document fallback strategies
- Add troubleshooting guide

**2. API Versioning Guide (1h)**
- File: `docs/api/versioning-guide.md` (new)
- Document version negotiation
- Provide migration examples (v0 → v1)
- Explain deprecation timeline
- Add client integration examples

#### Dependencies
- Stories 8.1 and 8.2 complete

#### Risks
- None

---

## Sprint Validation Gates

### Completion Criteria
- [ ] All 151 tests passing (100% test suite success)
- [ ] Circuit breakers tested under failure conditions
- [ ] API v1 endpoints fully functional
- [ ] Frontend successfully communicates with v1 API
- [ ] Performance impact of circuit breakers <5ms per request
- [ ] Documentation complete and reviewed

### Performance Targets
- API latency increase: <5ms with circuit breakers
- Circuit breaker decision time: <1ms
- Health check latency: <200ms (maintained from Sprint 7)
- Test suite execution: <5 minutes

### Quality Metrics
- Test coverage: >90% (up from 87.4%)
- No critical bugs introduced
- All breaking changes documented
- API documentation complete

---

## Sprint Metrics Tracking

### Velocity Tracking
- Target: 28 story points
- Capacity: Solo developer
- Buffer: 2 points for unknown issues

### Daily Progress
Track daily in comments or separate progress log.

### Blockers
Log any blockers here as they arise.

---

## Sprint Retrospective (Complete at Sprint End)

### What Went Well
- TBD

### What Could Be Improved
- TBD

### Action Items for Sprint 9
- TBD

### Lessons Learned
- TBD

---

## References

- [Sprint Implementation Plan](SPRINT_IMPLEMENTATION_PLAN.md) - Full 8-sprint roadmap
- [Product Requirements](PRODUCT_REQUIREMENTS.md) - Overall product vision
- [Sprint 7 Summary](SPRINT_IMPLEMENTATION_PLAN.md#sprint-7-production-readiness---authentication--health-week-1-2--complete) - Previous sprint context
