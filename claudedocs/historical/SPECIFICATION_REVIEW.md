# Specification Review - Narrative Modeling App

**Review Date**: 2025-10-07
**Review Type**: Multi-Domain Expert Panel Analysis
**Current Phase**: Sprint 6+ (Production Readiness)
**Test Coverage**: 87.4% (132/151 backend tests passing)

---

## Executive Summary

The Narrative Modeling App demonstrates solid architectural foundations with a clean three-tier design (Next.js frontend, FastAPI backend, MCP server) and well-structured workflow system. However, **the application is not production-ready** due to critical gaps in authentication, health monitoring, error handling, and test coverage.

### Key Metrics
- **Architecture Health**: 7/10 - Good separation of concerns, missing resilience patterns
- **Requirements Clarity**: 5/10 - Workflow defined, acceptance criteria missing
- **Test Quality**: 6/10 - Good unit coverage, critical E2E/integration gaps
- **Production Readiness**: 3/10 - Critical infrastructure gaps blocking deployment
- **Data Model Quality**: 6/10 - Functional but needs refactoring

### Critical Blockers (Must Fix Before Production)
1. Authentication system using mock implementation (`deps.py:8-9`)
2. Health checks return placeholders without real service validation
3. 19 failing backend tests (12.6% failure rate)
4. No circuit breakers for external services (S3, OpenAI, MongoDB)
5. Missing API versioning strategy

### Recommended Actions
- **Immediate** (1-2 sprints): Fix critical blockers, implement real auth, complete health checks
- **Short-term** (3-4 sprints): E2E test suite, monitoring infrastructure, API versioning
- **Medium-term** (5-6 sprints): Data model refactoring, performance optimization, observability

---

## Detailed Findings by Domain

### 1. Architecture & Design
**Reviewers**: Martin Fowler (Architectural Patterns), Sam Newman (Microservices)

#### Strengths
- **Clean Separation**: Frontend (`apps/frontend/`), Backend (`apps/backend/`), MCP (`apps/mcp/`)
- **API Design**: RESTful routing with proper HTTP semantics
- **Data Persistence**: MongoDB with Beanie ODM, proper indexing strategy
- **File Storage**: AWS S3 integration with presigned URLs
- **Background Processing**: Async task handling for AI jobs

#### Critical Issues

**1.1 Missing Service Resilience** 🔴
```
Location: apps/backend/app/services/
Issue: No circuit breaker patterns for external dependencies
Impact: S3/OpenAI failures cascade to user requests
```
- S3 operations in `data_processor.py` have no fallback strategy
- OpenAI calls in `model_training/explainer.py` lack timeout/retry logic
- MongoDB operations assume 100% availability

**Recommendation**: Implement circuit breaker pattern using `tenacity` or `circuitbreaker` library
```python
# Example for s3_utils.py
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def upload_file_to_s3(file_path: str, bucket: str, key: str):
    # Existing implementation with automatic retry
```

**1.2 No API Versioning Strategy** 🟡
```
Location: apps/backend/app/api/
Issue: Routes lack version prefixes
Impact: Breaking changes will impact all clients
```

**Recommendation**: Implement versioned routing
```python
# apps/backend/app/main.py
app.include_router(api_router, prefix="/api/v1")
```

**1.3 Tight Coupling in Transformation Service** 🟡
```
Location: apps/backend/app/api/routes/transformations.py
Issue: Business logic embedded in route handlers (lines 150-300)
Impact: Difficult to test, reuse, or modify transformation logic
```

**Recommendation**: Extract to `TransformationOrchestrator` service class

**1.4 Missing Service Boundaries Documentation** 🟢
```
Issue: No architectural decision records (ADRs)
Impact: Team lacks context for design choices
```

**Recommendation**: Create `docs/architecture/ADR/` with decisions on:
- Why FastAPI over Flask/Django
- MongoDB vs PostgreSQL choice
- S3 vs local storage rationale

### 2. Requirements & Specifications
**Reviewers**: Karl Wiegers (Requirements Engineering), Gojko Adzic (Specification by Example)

#### Strengths
- **Clear Workflow**: 8-stage system well-documented
- **TODO Tracking**: `TODO.md` with prioritized backlog
- **User Stories**: Implicit in workflow stages

#### Critical Gaps

**2.1 Missing Acceptance Criteria** 🔴
```
Location: Documentation gap
Issue: No Given/When/Then scenarios for workflow stages
Impact: Unclear success conditions for features
```

**Example Missing Specification**:
```gherkin
# Should exist in: tests/acceptance/transformation.feature

Scenario: Apply normalization transformation
  Given a dataset with column "age" containing values [25, 30, 35]
  When user applies normalization with method "standard"
  Then column "age" should contain standardized values
  And transformation should be reversible
  And original data should remain unchanged
```

**Recommendation**: Create acceptance test specifications for:
- Each transformation type (normalize, encode, drop, scale)
- Workflow stage transitions (upload → clean → transform → train)
- Error scenarios (invalid file, missing columns, API failures)

**2.2 Authentication Requirements Unclear** 🔴
```
Location: apps/backend/app/api/deps.py:8-9
Current: get_current_user = Annotated[str, Depends(lambda: "test_user")]
Issue: Mock authentication in dependencies
```

**Required Specification**:
```markdown
## Authentication Requirements
- **Providers**: Google OAuth 2.0, GitHub OAuth
- **Session Management**: JWT tokens, 24-hour expiry
- **Refresh Strategy**: Sliding window, 7-day max
- **Authorization**: Role-based (analyst, admin)
- **Security**: HTTPS only, secure cookie flags
```

**2.3 No SLAs for AI Processing** 🟡
```
Location: Background jobs (batch_prediction.py, hyperparameter_tuner.py)
Issue: No performance targets defined
Impact: Cannot validate production readiness
```

**Required Specifications**:
- **Preview Generation**: < 2 seconds (95th percentile)
- **Transformation Apply**: < 30 seconds for 10MB datasets
- **Model Training**: < 5 minutes for basic models
- **Batch Prediction**: < 1 minute per 1000 rows

**2.4 Missing Non-Functional Requirements** 🟡
```markdown
Required NFRs:
- **Scalability**: Support 100 concurrent users, 1000 datasets
- **Availability**: 99.5% uptime (excluding maintenance)
- **Data Retention**: Raw files 90 days, processed 1 year
- **Browser Support**: Chrome 90+, Firefox 88+, Safari 14+
- **File Size Limits**: 100MB upload, 500MB processed
```

### 3. Quality Assurance & Testing
**Reviewers**: Lisa Crispin (Agile Testing), Janet Gregory (Test Automation)

#### Strengths
- **Unit Test Coverage**: 56 backend test files, 87.4% passing
- **Transformation Tests**: 7/7 passing (`test_transformation_engine.py`)
- **Frontend Tests**: 31 test files with Jest/React Testing Library

#### Critical Issues

**3.1 Failing Backend Tests** 🔴
```
Status: 19/151 tests failing (12.6%)
Primary Failures:
- test_threshold_tuner.py: 8 failures (threshold edge cases)
- test_model_trainer.py: 6 failures (async handling)
- test_batch_prediction.py: 3 failures (file cleanup)
- test_hyperparameter_tuner.py: 2 failures (timeout issues)

Location: apps/backend/tests/
```

**Immediate Actions**:
1. Fix threshold edge cases in `model_training/threshold_tuner.py:45-67`
2. Add proper async context managers in `model_trainer.py:120-150`
3. Implement cleanup in `batch_prediction.py:275` (TODO comment exists)

**3.2 Missing E2E Test Suite** 🔴
```
Location: Playwright mentioned but not implemented
Impact: No validation of complete user workflows
```

**Required E2E Test Scenarios**:
```typescript
// tests/e2e/workflow.spec.ts (to be created)

test('Complete 8-stage workflow', async ({ page }) => {
  // Stage 1: Upload
  await page.goto('/datasets/upload');
  await page.setInputFiles('input[type=file]', 'test-data.csv');
  await expect(page.locator('.success-message')).toBeVisible();

  // Stage 2-8: Transform, Clean, Train, Evaluate, Deploy, Monitor, Interpret
  // Each stage should validate state transitions
});

test('Handle transformation errors gracefully', async ({ page }) => {
  // Test error scenarios with proper user feedback
});
```

**3.3 Integration Tests Disabled** 🔴
```
Location: apps/backend/tests/integration/
Issue: Tests require MongoDB fixtures not configured
Current: Tests skipped in CI/CD
```

**Recommendation**: Use `mongomock` or Docker Compose for test dependencies
```yaml
# docker-compose.test.yml
services:
  mongodb-test:
    image: mongo:7.0
    environment:
      MONGO_INITDB_DATABASE: narrate_test

  redis-test:
    image: redis:7-alpine
```

**3.4 No Visual Regression Testing** 🟡
```
Issue: Workflow UI changes undetected
Impact: Risk of visual bugs in production
```

**Recommendation**: Add Playwright visual comparison tests
```typescript
// tests/visual/workflow-stages.spec.ts
test('Stage 3 transformation UI matches baseline', async ({ page }) => {
  await page.goto('/datasets/123/transform');
  await expect(page).toHaveScreenshot('stage-3-transform.png');
});
```

**3.5 Missing Error Scenario Coverage** 🟡
```
Gaps:
- S3 upload failures
- MongoDB connection loss during transformation
- OpenAI API rate limiting
- Invalid CSV formats (malformed quotes, encoding issues)
- Concurrent transformation attempts
```

**Required Test Cases**:
```python
# tests/test_error_scenarios.py (to be created)

async def test_s3_upload_failure_handling():
    """Verify graceful degradation when S3 is unavailable"""
    with mock.patch('app.services.s3_utils.upload_file') as mock_upload:
        mock_upload.side_effect = ClientError(...)
        response = await client.post('/datasets/upload', files=...)
        assert response.status_code == 503  # Service Unavailable
        assert 'retry' in response.json()['message'].lower()
```

### 4. Production Readiness & Operations
**Reviewers**: Michael Nygard (Release It!), Kelsey Hightower (Cloud Native)

#### Critical Gaps

**4.1 Inadequate Health Checks** 🔴
```
Location: apps/backend/app/api/routes/health.py
Current Implementation:
  - MongoDB: Returns "healthy" without connection test
  - S3: Returns "healthy" without bucket access test
  - OpenAI: Not checked at all

Lines 15-30: Placeholder checks
```

**Required Implementation**:
```python
# apps/backend/app/api/routes/health.py

@router.get("/health/live")
async def liveness():
    """Basic process health - always returns 200 if app running"""
    return {"status": "alive"}

@router.get("/health/ready")
async def readiness():
    """Service dependency health - returns 503 if dependencies unavailable"""
    checks = {
        "mongodb": await check_mongodb_connection(),
        "s3": await check_s3_access(),
        "openai": await check_openai_api(),
    }

    all_healthy = all(c["status"] == "healthy" for c in checks.values())
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if all_healthy else "degraded", "checks": checks}
    )

async def check_mongodb_connection() -> dict:
    try:
        await database.client.admin.command('ping')
        return {"status": "healthy", "latency_ms": ...}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

**4.2 No Monitoring/Alerting Specifications** 🔴
```
Missing:
- Application metrics (request rate, error rate, latency)
- Business metrics (transformations applied, models trained)
- Infrastructure metrics (CPU, memory, disk usage)
- Alert definitions (thresholds, escalation paths)
```

**Required Monitoring Specifications**:
```yaml
# docs/operations/monitoring.yml (to be created)

metrics:
  application:
    - name: http_requests_total
      type: counter
      labels: [method, endpoint, status]

    - name: transformation_duration_seconds
      type: histogram
      labels: [operation_type]
      buckets: [0.1, 0.5, 1.0, 5.0, 10.0, 30.0]

    - name: model_training_duration_seconds
      type: histogram
      labels: [algorithm]

  alerts:
    - name: HighErrorRate
      condition: error_rate > 0.05 for 5m
      severity: critical
      notification: pagerduty

    - name: TransformationSlow
      condition: p95_latency > 30s for 10m
      severity: warning
      notification: slack
```

**4.3 Missing Circuit Breaker Implementation** 🔴
```
Services Without Protection:
- S3 operations (upload, download, delete)
- OpenAI API calls (explanations, suggestions)
- MongoDB queries (large aggregations)

Location: All services in apps/backend/app/services/
```

**Recommendation**: Implement with `circuitbreaker` library
```python
# apps/backend/app/utils/resilience.py (to be created)

from circuitbreaker import circuit
from tenacity import retry, stop_after_attempt, wait_exponential

@circuit(failure_threshold=5, recovery_timeout=60)
@retry(stop=stop_after_attempt(3), wait=wait_exponential())
async def resilient_s3_operation(operation_func, *args, **kwargs):
    """Wrap S3 operations with circuit breaker and retry"""
    try:
        return await operation_func(*args, **kwargs)
    except Exception as e:
        logger.error(f"S3 operation failed: {e}")
        raise
```

**4.4 No Retry Policies Documented** 🔴
```
Issue: Inconsistent retry behavior across services
Impact: User-facing errors for transient failures
```

**Required Specifications**:
```markdown
## Retry Policy Standards

### Idempotent Operations (GET, PUT, DELETE)
- Max Attempts: 3
- Backoff: Exponential (2s, 4s, 8s)
- Jitter: ±20% to prevent thundering herd

### Non-Idempotent Operations (POST)
- Max Attempts: 1 (no auto-retry)
- User-Initiated Retry: Supported with idempotency key

### Timeout Configuration
- S3 Operations: 30s connect, 300s read
- OpenAI API: 60s connect, 180s read
- MongoDB: 10s connect, 30s query
```

**4.5 Background Job Cleanup Missing** 🔴
```
Location: apps/backend/app/services/batch_prediction.py:275
Current: # TODO: Implement cleanup logic
Impact: Temporary files accumulate, disk space exhaustion
```

**Required Implementation**:
```python
# apps/backend/app/services/batch_prediction.py:275

async def cleanup_batch_job(job_id: str):
    """Remove temporary files after batch prediction completes"""
    try:
        temp_dir = f"/tmp/batch_{job_id}"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up batch job {job_id}")
    except Exception as e:
        logger.error(f"Cleanup failed for {job_id}: {e}")
        # Schedule retry via background task
```

**4.6 Missing Deployment Procedures** 🟡
```
Missing Documentation:
- Rollback procedures for failed deployments
- Database migration strategy
- Zero-downtime deployment approach
- Canary/blue-green deployment specs
```

**Required Documentation** (`docs/operations/deployment.md`):
```markdown
## Deployment Procedures

### Pre-Deployment Checklist
- [ ] All tests passing (unit, integration, E2E)
- [ ] Database migrations tested on staging
- [ ] Feature flags configured
- [ ] Rollback plan documented

### Deployment Steps
1. Enable maintenance mode (optional)
2. Run database migrations with --dry-run
3. Apply migrations
4. Deploy application (blue-green strategy)
5. Run smoke tests
6. Monitor error rates for 15 minutes
7. Complete deployment or rollback

### Rollback Procedures
- **Application Rollback**: Revert to previous container image
- **Database Rollback**: Apply down-migrations (if safe)
- **Data Rollback**: Restore from backup (last resort)
```

### 5. Data Models & Schema Design
**Reviewers**: Gojko Adzic (Domain Modeling), Alistair Cockburn (Use Cases)

#### Critical Issues

**5.1 UserData Model Violation of SRP** 🟡
```
Location: apps/backend/app/models/user_data.py
Issue: Single class with 20+ fields spanning multiple concerns

Current Structure (lines 15-80):
- File metadata (filename, file_path, s3_url)
- Processing state (status, stage)
- Data characteristics (columns, dtypes, shape)
- Transformation history (transformations_applied)
- PII tracking (identified_pii_columns)
- Relationship references (trained_model_ids)
```

**Recommendation**: Split into domain-bounded models
```python
# apps/backend/app/models/dataset.py (to be created)

class DatasetMetadata(Document):
    """Core dataset information"""
    user_id: str
    filename: str
    s3_url: str
    created_at: datetime

class DatasetSchema(Document):
    """Data structure information"""
    dataset_id: PydanticObjectId
    columns: List[ColumnInfo]
    dtypes: Dict[str, str]
    shape: Tuple[int, int]

class TransformationHistory(Document):
    """Applied transformations log"""
    dataset_id: PydanticObjectId
    transformations: List[Transformation]
    version: int  # Enable schema versioning

class DatasetPrivacy(Document):
    """PII and compliance tracking"""
    dataset_id: PydanticObjectId
    pii_columns: List[str]
    anonymization_applied: bool
    compliance_flags: Dict[str, bool]
```

**5.2 No Schema Versioning Strategy** 🔴
```
Issue: Data transformations lack versioning
Impact: Cannot reproduce historical results, rollback impossible
```

**Required Implementation**:
```python
# apps/backend/app/models/transformation.py

class TransformationVersion(BaseModel):
    version: str  # Semantic versioning (e.g., "1.0.0")
    transformation_type: str
    parameters: Dict[str, Any]
    applied_at: datetime
    reversible: bool
    rollback_params: Optional[Dict[str, Any]]

class DatasetVersion(Document):
    dataset_id: PydanticObjectId
    version: int
    parent_version: Optional[int]
    transformations: List[TransformationVersion]
    s3_snapshot_url: str  # Immutable snapshot
```

**5.3 Missing Relationship Documentation** 🟡
```
Issue: Implicit relationships not documented
Current: UserData.trained_model_ids references TrainedModel
Missing: Formal relationship constraints and cascade rules
```

**Required Documentation**:
```markdown
## Data Model Relationships

### UserData → TrainedModel (One-to-Many)
- Cardinality: 1 dataset can have 0..* trained models
- Cascade Delete: Soft delete (mark models inactive)
- Referential Integrity: Enforced via application logic

### UserData → TransformationHistory (One-to-Many)
- Cardinality: 1 dataset has 1..* transformation versions
- Cascade Delete: Hard delete (orphan cleanup)
- Versioning: Immutable history, append-only

### TrainedModel → Predictions (One-to-Many)
- Cardinality: 1 model has 0..* prediction batches
- Cascade Delete: Configurable (retain vs purge)
- Retention: 90 days default, configurable per model
```

**5.4 No Schema Evolution Strategy** 🟡
```
Issue: Adding fields to UserData requires manual migration
Risk: Breaking changes in production
```

**Recommendation**: Implement schema migration framework
```python
# apps/backend/app/migrations/versions/001_add_dataset_privacy.py

from beanie import Document
from app.models.user_data import UserData

async def upgrade():
    """Add privacy tracking fields"""
    await UserData.find_all().update(
        {"$set": {
            "privacy_reviewed": False,
            "pii_detection_version": "1.0.0"
        }}
    )

async def downgrade():
    """Remove privacy tracking fields"""
    await UserData.find_all().update(
        {"$unset": {
            "privacy_reviewed": "",
            "pii_detection_version": ""
        }}
    )
```

**5.5 No Data Retention Policies** 🟢
```
Issue: No defined lifecycle for datasets and models
Impact: Storage costs increase indefinitely
```

**Required Policy Documentation**:
```markdown
## Data Retention Policies

### Raw Uploaded Files
- Retention: 90 days from upload
- Storage: AWS S3 with lifecycle policy
- Cleanup: Automated via S3 lifecycle rules

### Processed Datasets
- Retention: 1 year from last access
- Storage: MongoDB + S3 snapshots
- Cleanup: Weekly background job

### Trained Models
- Retention: Indefinite (user-controlled)
- Archival: Move to Glacier after 180 days inactive
- Cleanup: User-initiated deletion only

### Predictions & Results
- Retention: 90 days from generation
- Storage: MongoDB (compressed)
- Cleanup: Monthly background job
```

---

## Prioritized Recommendations

### 🔴 CRITICAL - Production Blockers (Sprint 1-2)

#### 1. Implement Real Authentication
```
Files: apps/backend/app/api/deps.py:8-9
Action: Replace mock with NextAuth integration
Success Criteria:
  - JWT validation functional
  - Google/GitHub OAuth working
  - Session management implemented
  - Authorization middleware active
Effort: 3 days
```

#### 2. Complete Health Check Implementation
```
Files: apps/backend/app/api/routes/health.py:15-30
Action: Add real service connectivity tests
Success Criteria:
  - MongoDB ping successful
  - S3 bucket accessible
  - OpenAI API responsive
  - /health/ready returns accurate status
Effort: 2 days
```

#### 3. Fix Failing Backend Tests
```
Files:
  - apps/backend/tests/test_threshold_tuner.py (8 failures)
  - apps/backend/tests/test_model_trainer.py (6 failures)
  - apps/backend/tests/test_batch_prediction.py (3 failures)
Action: Debug and resolve all test failures
Success Criteria: 100% test pass rate (151/151)
Effort: 5 days
```

#### 4. Add Circuit Breakers for External Services
```
Files:
  - apps/backend/app/services/s3_utils.py
  - apps/backend/app/services/model_training/explainer.py
  - All MongoDB query operations
Action: Implement circuit breaker pattern with tenacity/circuitbreaker
Success Criteria:
  - S3 operations fail gracefully
  - OpenAI timeouts don't crash app
  - MongoDB unavailability returns 503
Effort: 4 days
```

#### 5. Document API Contracts
```
Files: apps/backend/app/api/ (all routes)
Action: Create OpenAPI specs with examples
Success Criteria:
  - Swagger UI complete
  - Request/response examples for all endpoints
  - Error response schemas documented
Effort: 3 days
```

**Total Critical Path Effort**: 17 days (~3.5 sprints)

### 🟡 HIGH - Quality Gates (Sprint 3-4)

#### 6. Build E2E Test Suite
```
Files: tests/e2e/ (to be created)
Action: Implement Playwright tests for 8-stage workflow
Success Criteria:
  - Complete workflow tested (upload → interpret)
  - Error scenarios covered
  - Cross-browser validation (Chrome, Firefox, Safari)
Effort: 8 days
```

#### 7. Implement Monitoring Infrastructure
```
Files:
  - apps/backend/app/middleware/metrics.py (to be created)
  - docs/operations/monitoring.yml (to be created)
Action: Add Prometheus metrics, Grafana dashboards, alerts
Success Criteria:
  - Request rate/latency tracked
  - Error rate alerts functional
  - Business metrics dashboards live
Effort: 5 days
```

#### 8. Complete Transformation Validations
```
Files: apps/backend/app/api/routes/transformations.py:250-280
Action: Implement missing drop_missing logic, edge case handling
Success Criteria:
  - All transformation types validated
  - Edge cases handled (empty columns, all-null, single-value)
  - Validation errors user-friendly
Effort: 3 days
```

#### 9. Implement API Versioning
```
Files:
  - apps/backend/app/main.py
  - apps/backend/app/api/ (all routes)
Action: Add /api/v1/ prefix, version negotiation
Success Criteria:
  - /api/v1/ routes functional
  - Version deprecation strategy documented
  - Client migration guide created
Effort: 2 days
```

#### 10. Define Acceptance Criteria
```
Files:
  - tests/acceptance/ (to be created)
  - docs/specifications/acceptance_criteria.md (to be created)
Action: Create Given/When/Then scenarios for all features
Success Criteria:
  - Workflow stage criteria defined
  - Transformation scenarios documented
  - Error handling criteria specified
Effort: 4 days
```

**Total High Priority Effort**: 22 days (~4.5 sprints)

### 🟢 MEDIUM - Technical Debt (Sprint 5-6)

#### 11. Refactor UserData Model
```
Files: apps/backend/app/models/user_data.py
Action: Split into DatasetMetadata, DatasetSchema, TransformationHistory, DatasetPrivacy
Success Criteria:
  - Single Responsibility Principle followed
  - Backward compatibility maintained
  - Migration script provided
Effort: 6 days
```

#### 12. Add Data Versioning
```
Files: apps/backend/app/models/transformation.py (to be created)
Action: Implement transformation lineage tracking
Success Criteria:
  - Version history for all transformations
  - Rollback capability functional
  - Reproducible results verified
Effort: 5 days
```

#### 13. Create Integration Test Fixtures
```
Files:
  - docker-compose.test.yml (to be created)
  - apps/backend/tests/integration/ (enable existing tests)
Action: Setup MongoDB/Redis test containers
Success Criteria:
  - Integration tests run in CI/CD
  - Fixtures automated
  - Test isolation verified
Effort: 3 days
```

#### 14. Add Performance Benchmarks
```
Files: apps/backend/tests/performance/ (to be created)
Action: Define and validate performance targets
Success Criteria:
  - Preview generation < 2s (p95)
  - Transformation apply < 30s for 10MB
  - Model training < 5min for basic models
Effort: 4 days
```

#### 15. Implement Background Job Cleanup
```
Files: apps/backend/app/services/batch_prediction.py:275
Action: Complete TODO for temporary file cleanup
Success Criteria:
  - Temp files removed after job completion
  - Disk usage monitored
  - Cleanup failures logged and retried
Effort: 2 days
```

**Total Medium Priority Effort**: 20 days (~4 sprints)

---

## Implementation Roadmap

### Phase 1: Production Readiness (Sprint 1-2) - 4 weeks
**Goal**: Eliminate critical blockers, achieve deployable state

**Week 1-2**:
- ✅ Fix 19 failing backend tests
- ✅ Implement real authentication (replace mock in deps.py)
- ✅ Complete health check implementation

**Week 3-4**:
- ✅ Add circuit breakers for S3, OpenAI, MongoDB
- ✅ Document API contracts with OpenAPI specs
- ✅ Create deployment runbooks

**Exit Criteria**:
- [ ] 100% test pass rate (151/151)
- [ ] Authentication functional with Google/GitHub
- [ ] Health checks validate all dependencies
- [ ] Circuit breakers prevent cascading failures
- [ ] API documentation complete

### Phase 2: Quality & Observability (Sprint 3-4) - 4 weeks
**Goal**: Establish quality gates and production visibility

**Week 5-6**:
- ✅ Build E2E test suite with Playwright
- ✅ Implement monitoring (Prometheus + Grafana)
- ✅ Complete transformation validations

**Week 7-8**:
- ✅ Add API versioning (/api/v1/)
- ✅ Define acceptance criteria for all features
- ✅ Setup alerting infrastructure

**Exit Criteria**:
- [ ] E2E tests cover 8-stage workflow
- [ ] Monitoring dashboards operational
- [ ] API versioning implemented
- [ ] All transformations validated
- [ ] Alerts functional with defined thresholds

### Phase 3: Technical Excellence (Sprint 5-6) - 4 weeks
**Goal**: Address technical debt, optimize performance

**Week 9-10**:
- ✅ Refactor UserData model (SRP compliance)
- ✅ Implement data versioning system
- ✅ Create integration test fixtures

**Week 11-12**:
- ✅ Add performance benchmarks
- ✅ Implement background job cleanup
- ✅ Visual regression testing

**Exit Criteria**:
- [ ] Data models follow single responsibility
- [ ] Transformation versioning functional
- [ ] Performance targets validated
- [ ] Integration tests automated
- [ ] Visual regression suite active

### Phase 4: Advanced Features (Sprint 7+) - Ongoing
**Goal**: Enhanced ML capabilities, advanced workflows

**Future Enhancements**:
- AutoML integration for model selection
- Real-time model monitoring
- Collaborative dataset sharing
- Advanced explainability features
- Custom transformation plugins

---

## Quality Metrics & Success Criteria

### Code Quality Standards

#### Test Coverage Targets
```yaml
backend_unit_tests:
  current: 87.4% (132/151 passing)
  target: 95% (all tests passing)
  critical_paths: 100% coverage

frontend_tests:
  current: 31 test files
  target: 80% coverage
  component_coverage: 90%

e2e_tests:
  current: 0 tests
  target: Full workflow coverage
  success_rate: 100%

integration_tests:
  current: Disabled
  target: All services tested
  isolation: Docker containers
```

#### Performance Benchmarks
```yaml
api_response_times:
  preview_generation:
    target: < 2s (p95)
    current: Not measured

  transformation_apply:
    target: < 30s for 10MB datasets
    current: Not measured

  model_training:
    target: < 5min (basic models)
    current: Not measured

health_check_latency:
  target: < 100ms
  current: Placeholder (instant)
```

#### Reliability Metrics
```yaml
error_rates:
  api_errors:
    target: < 1% of requests
    alert_threshold: > 5% for 5min

  background_job_failures:
    target: < 2% of jobs
    retry_policy: 3 attempts with backoff

availability:
  uptime_target: 99.5%
  maintenance_window: Sunday 02:00-04:00 UTC

circuit_breaker_metrics:
  open_threshold: 50% errors in 10s window
  half_open_timeout: 60s
  closed_threshold: 3 consecutive successes
```

### Security Standards

#### Authentication & Authorization
```yaml
authentication:
  - OAuth 2.0 with Google/GitHub ✅
  - JWT token validation ❌ (mock current)
  - Session timeout: 24 hours
  - Refresh token: 7 days max

authorization:
  - Role-based access control (analyst, admin)
  - Resource-level permissions
  - API key rotation: 90 days

security_headers:
  - HTTPS only (HSTS enabled)
  - Content Security Policy
  - X-Frame-Options: DENY
  - X-Content-Type-Options: nosniff
```

#### Data Protection
```yaml
data_at_rest:
  - S3 server-side encryption (SSE-S3)
  - MongoDB field-level encryption for PII
  - Secrets in AWS Secrets Manager

data_in_transit:
  - TLS 1.2+ for all connections
  - Certificate pinning for external APIs

pii_handling:
  - Automatic detection in datasets
  - Anonymization options
  - Audit logging for PII access
```

### Operational Readiness

#### Monitoring & Alerting
```yaml
required_dashboards:
  - Application Performance (latency, throughput, errors)
  - Business Metrics (datasets, transformations, models)
  - Infrastructure (CPU, memory, disk, network)
  - User Activity (active users, sessions, workflows)

alert_definitions:
  critical:
    - Error rate > 5% for 5min
    - Health check failures > 3 consecutive
    - Disk usage > 90%

  warning:
    - Response time p95 > 5s for 10min
    - Background job queue > 100 items
    - Memory usage > 80%
```

#### Deployment Procedures
```yaml
deployment_strategy:
  type: Blue-Green
  rollback_time: < 5 minutes
  smoke_tests: Automated

database_migrations:
  dry_run: Required in staging
  rollback_plan: Documented per migration
  max_downtime: 60 seconds

feature_flags:
  new_features: Disabled by default
  gradual_rollout: 10% → 50% → 100%
  kill_switch: All features
```

---

## Appendix: Reference Materials

### A. Testing Strategy Summary

#### Test Pyramid Distribution
```
         /\
        /E2\      E2E Tests (10%): Complete workflows
       /____\
      /      \    Integration Tests (30%): Service interactions
     /________\
    /          \  Unit Tests (60%): Individual components
   /____________\
```

**Current State**: Inverted pyramid (87% unit, 0% E2E, 13% integration disabled)
**Target State**: Balanced pyramid (60% unit, 30% integration, 10% E2E)

#### Test Type Specifications

**Unit Tests** (`apps/backend/tests/test_*`)
- Scope: Individual functions, classes
- Dependencies: Mocked
- Execution: < 5 seconds total
- Coverage: 95% target

**Integration Tests** (`apps/backend/tests/integration/`)
- Scope: Service interactions (API → MongoDB → S3)
- Dependencies: Docker containers (MongoDB, Redis, LocalStack)
- Execution: < 2 minutes total
- Coverage: All critical paths

**E2E Tests** (`tests/e2e/`)
- Scope: Complete user workflows
- Dependencies: Staging environment
- Execution: < 10 minutes total
- Coverage: Happy path + error scenarios

### B. Architecture Decision Records (Template)

```markdown
# ADR-001: Choice of FastAPI over Flask/Django

## Status
Accepted

## Context
Need high-performance async API for ML workloads with background processing.

## Decision
Use FastAPI for backend framework.

## Consequences
**Positive**:
- Native async/await support
- Automatic OpenAPI generation
- Type safety with Pydantic
- High performance (comparable to Node.js)

**Negative**:
- Smaller ecosystem than Django
- Team learning curve for async patterns
- Fewer batteries-included features

## Alternatives Considered
- Flask: Synchronous, slower for I/O-heavy ML tasks
- Django: Monolithic, overkill for API-only backend
- Node.js: JavaScript ecosystem mismatch with ML libraries
```

### C. Monitoring Metrics Catalog

#### Application Metrics
```python
# apps/backend/app/middleware/metrics.py (to be created)

from prometheus_client import Counter, Histogram, Gauge

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# Business metrics
transformations_applied = Counter(
    'transformations_applied_total',
    'Total transformations applied',
    ['transformation_type']
)

models_trained = Counter(
    'models_trained_total',
    'Total models trained',
    ['algorithm']
)

# Infrastructure metrics
active_background_jobs = Gauge(
    'active_background_jobs',
    'Number of active background jobs',
    ['job_type']
)
```

### D. Security Checklist

#### Pre-Production Security Validation
- [ ] Authentication enabled (no mock users)
- [ ] HTTPS enforced (redirect HTTP → HTTPS)
- [ ] Security headers configured (CSP, HSTS, X-Frame-Options)
- [ ] Input validation on all endpoints (Pydantic models)
- [ ] SQL/NoSQL injection prevention (parameterized queries)
- [ ] Rate limiting configured (per user, per IP)
- [ ] CORS policy restrictive (whitelist origins only)
- [ ] Secrets in environment variables (no hardcoded keys)
- [ ] PII data encrypted at rest (field-level encryption)
- [ ] Audit logging enabled (authentication, data access)
- [ ] Dependency vulnerabilities scanned (Snyk/Dependabot)
- [ ] Container images scanned (Trivy/Clair)

### E. Deployment Runbook

#### Pre-Deployment Checklist
```bash
# 1. Verify all tests pass
cd apps/backend && uv run pytest -v
cd apps/frontend && npm test

# 2. Run database migrations (dry-run first)
uv run alembic upgrade head --sql  # Review SQL
uv run alembic upgrade head        # Apply

# 3. Validate health checks
curl https://api.staging.narrate.app/health/ready
# Expect: {"status": "ready", "checks": {...}}

# 4. Run smoke tests on staging
cd tests/e2e && npx playwright test --grep @smoke

# 5. Review monitoring dashboards
# Check: Error rate, latency, active users

# 6. Prepare rollback plan
git tag release-$(date +%Y%m%d-%H%M)
```

#### Deployment Steps (Blue-Green)
```bash
# 1. Deploy to green environment
kubectl apply -f k8s/deployment-green.yml

# 2. Wait for healthy pods
kubectl wait --for=condition=ready pod -l app=narrate,slot=green --timeout=300s

# 3. Run health checks
kubectl exec -it deploy/narrate-green -- curl localhost:8000/health/ready

# 4. Switch traffic (10% → 50% → 100%)
kubectl patch svc narrate -p '{"spec":{"selector":{"slot":"green"}}}'

# 5. Monitor for 15 minutes
watch 'kubectl top pods && kubectl logs -l app=narrate,slot=green --tail=20'

# 6. Decommission blue environment (if successful)
kubectl delete -f k8s/deployment-blue.yml
```

#### Rollback Procedure
```bash
# If error rate > 5% OR critical bug detected:

# 1. Immediate traffic switch
kubectl patch svc narrate -p '{"spec":{"selector":{"slot":"blue"}}}'

# 2. Verify rollback successful
curl https://api.narrate.app/health/ready

# 3. Investigate issue
kubectl logs -l app=narrate,slot=green > /tmp/failed-deployment.log

# 4. Rollback database (if necessary)
uv run alembic downgrade -1  # Use with caution!
```

---

## Document Control

**Version**: 1.0
**Last Updated**: 2025-10-07
**Next Review**: 2025-11-07 (Monthly)
**Owner**: Engineering Team
**Reviewers**: Product, DevOps, QA

**Change Log**:
- 2025-10-07: Initial specification review based on expert panel analysis
- Future: Track implementation progress and update recommendations

**Related Documents**:
- `TODO.md` - Development backlog
- `apps/backend/TEST_STATUS.md` - Test suite status
- `CLAUDE.md` - Project conventions
- `.env.example` - Configuration reference

---

**End of Specification Review**
