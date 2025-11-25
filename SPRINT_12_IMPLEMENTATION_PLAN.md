# Sprint 12 Implementation Plan

**Created**: 2025-11-25
**Sprint**: 12 - API Integration & Production Readiness
**Total Story Points**: 38
**Estimated Remaining Work**: 12-16 hours

---

## Executive Summary

Sprint 12 has significant implementation already in place, but a **critical import cycle issue** is blocking the test suite. Once resolved, the remaining work focuses on:

1. **Fixing critical blockers** (2-3 hours)
2. **Completing Story 12.1** - API integration fixes (3-4 hours)
3. **Story 12.3** - Service layer refactoring (4-5 hours)
4. **Story 12.5** - E2E integration testing (3-4 hours)

Stories 12.2 (Data Versioning) and 12.4 (Performance Optimization) appear complete based on codebase analysis.

---

## Current State Analysis

### What's Already Implemented

| Story | Status | Evidence |
|-------|--------|----------|
| 12.1 API Integration | ~80% | Routes exist: datasets.py (550 lines), models.py (400 lines), transformations.py (756 lines), versions.py (200 lines) |
| 12.2 Data Versioning | ~95% | versioning_service.py (500 lines), versions.py routes, DatasetVersion model |
| 12.3 Service Refactoring | ~70% | Services exist but need cleanup and standardization |
| 12.4 Performance | ~90% | Benchmarks complete, indexes added, caching implemented |
| 12.5 E2E Testing | ~60% | 2,800 lines of Playwright tests exist, infrastructure ready |

### Critical Blocker

**ISSUE**: Namespace conflict between:
- `apps/backend/app/services/transformation_service.py` (file)
- `apps/backend/app/services/transformation_service/` (directory with transformation_engine)

**IMPACT**:
- 16 test collection errors
- All transformation-related imports fail
- Test suite cannot execute (834 tests blocked)
- Application may fail to start

---

## Implementation Plan

### Phase 0: Critical Fix (MUST DO FIRST)

**Time Estimate**: 1-2 hours
**Priority**: BLOCKING

#### Task 0.1: Resolve Import Cycle

**Problem**: Python's module system resolves `transformation_service` to the directory instead of the `.py` file.

**Solution Options**:

1. **Option A (Recommended)**: Rename the file
   ```
   transformation_service.py → transformation_config_service.py
   ```
   - Update all imports across codebase
   - Clear separation: config management vs. execution engine

2. **Option B**: Move file into package
   ```
   transformation_service/ (rename to transformation/)
   └── __init__.py (re-export everything)
   └── config_service.py (moved from transformation_service.py)
   └── engine/ (moved from transformation_engine/)
   ```

3. **Option C**: Rename the directory
   ```
   transformation_service/ → transformation_engine/
   ```
   - Simplest change, keeps service file name

**Files to Update**:
- `app/services/__init__.py`
- `app/api/routes/transformations.py`
- `app/services/transformation_engine/__init__.py`
- All test files importing transformation service

#### Task 0.2: Verify Test Suite Runs

```bash
cd apps/backend
uv run pytest --collect-only 2>&1 | grep -E "(collected|error)"
uv run pytest tests/test_api/ -v --tb=short 2>&1 | head -50
```

**Success Criteria**:
- [ ] No collection errors
- [ ] `pytest --collect-only` shows 834+ tests
- [ ] Basic API tests run without import errors

---

### Phase 1: Story 12.1 Completion - API Integration

**Time Estimate**: 3-4 hours
**Priority**: HIGH
**Points**: 10 (currently ~80% complete)

#### Task 1.1: Fix Transformation API Tests

**Files**:
- `tests/test_api/test_transformations.py`
- `tests/test_api/test_transformations_integration.py`

**Issues to Fix**:
- Schema import errors (`TransformationType` not exported)
- 422 validation errors in tests
- Missing mock configurations

**Actions**:
1. Add `TransformationType` to schema exports
2. Fix request body schemas to match API expectations
3. Update test fixtures for new models

#### Task 1.2: Fix Model Training API Tests

**Files**:
- `tests/test_api/test_model_training.py`
- `tests/test_api/test_models.py`

**Issues to Fix**:
- S3 NoSuchKey errors (mocking issues)
- Coroutine unpacking errors
- ModelCandidate initialization errors

**Actions**:
1. Update S3 mocks to return proper responses
2. Fix async/await patterns in tests
3. Update ModelCandidate to match new schema

#### Task 1.3: Verify All API Endpoints

Run full API test suite:
```bash
cd apps/backend
uv run pytest tests/test_api/ -v --tb=short
```

**Success Criteria**:
- [ ] All 8 dataset endpoints tested and passing
- [ ] All transformation endpoints passing
- [ ] All model endpoints passing
- [ ] All version endpoints passing
- [ ] >95% API test coverage

---

### Phase 2: Story 12.3 - Service Layer Refactoring

**Time Estimate**: 4-5 hours
**Priority**: MEDIUM
**Points**: 8

#### Task 2.1: Extract Base Service Class

**New File**: `app/services/base_service.py`

```python
from typing import TypeVar, Generic, Optional, List
from beanie import Document
from pydantic import BaseModel

T = TypeVar('T', bound=Document)

class BaseService(Generic[T]):
    """Base service with common CRUD patterns"""

    model_class: type[T]

    async def get_by_id(self, id: str, user_id: str) -> Optional[T]:
        """Get document by ID with user ownership check"""
        pass

    async def list_for_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        **filters
    ) -> List[T]:
        """List documents for user with pagination"""
        pass

    async def create(self, user_id: str, data: BaseModel) -> T:
        """Create new document"""
        pass

    async def update(self, id: str, user_id: str, data: BaseModel) -> Optional[T]:
        """Update existing document"""
        pass

    async def delete(self, id: str, user_id: str) -> bool:
        """Soft or hard delete document"""
        pass
```

#### Task 2.2: Standardize Error Handling

**New File**: `app/services/exceptions.py`

```python
class ServiceError(Exception):
    """Base service exception"""
    pass

class NotFoundError(ServiceError):
    """Resource not found"""
    pass

class PermissionError(ServiceError):
    """User doesn't have permission"""
    pass

class ValidationError(ServiceError):
    """Data validation failed"""
    pass

class ConflictError(ServiceError):
    """Resource conflict (duplicate, version mismatch)"""
    pass
```

#### Task 2.3: Refactor Existing Services

**Files to Update**:
- `app/services/dataset_service.py` - Extend BaseService
- `app/services/model_service.py` - Extend BaseService
- `app/services/transformation_config_service.py` - Extend BaseService (after rename)
- `app/services/versioning_service.py` - Extend BaseService

**Changes**:
1. Inherit from BaseService
2. Use standardized exceptions
3. Add consistent logging
4. Ensure all methods are async

#### Task 2.4: Add Deprecation Warnings

**File**: `app/services/dataset_service.py`

```python
import warnings

def get_user_data(self, user_id: str):
    """DEPRECATED: Use get_dataset instead"""
    warnings.warn(
        "get_user_data is deprecated, use get_dataset",
        DeprecationWarning,
        stacklevel=2
    )
    # Legacy implementation
```

#### Task 2.5: Update Service Tests

**Files**:
- `tests/test_services/test_dataset_service.py`
- `tests/test_services/test_model_service.py`
- `tests/test_services/test_transformation_service.py`
- `tests/test_services/test_versioning_service.py`

**Actions**:
1. Test new BaseService methods
2. Test exception handling
3. Test deprecation warnings
4. Achieve >95% service layer coverage

**Success Criteria**:
- [ ] BaseService class implemented and tested
- [ ] All services use standardized exceptions
- [ ] Deprecation warnings in place for legacy methods
- [ ] Service tests passing with >95% coverage

---

### Phase 3: Story 12.5 - E2E Integration Testing

**Time Estimate**: 3-4 hours
**Priority**: HIGH
**Points**: 8

The frontend already has ~2,800 lines of E2E tests. Focus on gaps and integration.

#### Task 3.1: Backend Integration Tests

**New Files**:
- `tests/integration/test_complete_workflow.py`
- `tests/integration/test_api_contracts.py`

**Test Scenarios**:
1. **Complete Workflow**: Upload → Profile → Transform → Train → Predict
2. **Versioning Flow**: Create version → Apply transforms → Compare versions
3. **Model Lifecycle**: Train → Evaluate → Deploy → Monitor

```python
# tests/integration/test_complete_workflow.py
import pytest
from httpx import AsyncClient

@pytest.mark.integration
async def test_complete_ml_workflow(client: AsyncClient, test_user):
    """Test full workflow: upload → transform → train → predict"""

    # 1. Upload dataset
    upload_response = await client.post(
        "/api/v1/datasets/upload",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )
    assert upload_response.status_code == 201
    dataset_id = upload_response.json()["dataset_id"]

    # 2. Apply transformations
    transform_response = await client.post(
        "/api/v1/transformations/apply",
        json={
            "dataset_id": dataset_id,
            "transformation_type": "scale",
            "parameters": {"method": "standard", "columns": ["age", "income"]}
        }
    )
    assert transform_response.status_code == 200

    # 3. Train model
    train_response = await client.post(
        "/api/v1/models/train",
        json={
            "dataset_id": dataset_id,
            "target_column": "purchased",
            "algorithm": "random_forest"
        }
    )
    assert train_response.status_code == 202
    model_id = train_response.json()["model_id"]

    # 4. Wait for training (poll status)
    # ...

    # 5. Make prediction
    predict_response = await client.post(
        f"/api/v1/models/{model_id}/predict",
        json={"features": {"age": 35, "income": 50000}}
    )
    assert predict_response.status_code == 200
    assert "prediction" in predict_response.json()
```

#### Task 3.2: Frontend E2E Gaps

**New/Updated Files**:
- `e2e/workflows/complete-ai-workflow.spec.ts`
- `e2e/workflows/data-versioning.spec.ts`
- `e2e/workflows/production-deployment.spec.ts`

**Test Scenarios**:

1. **Complete AI Workflow** (new):
   ```typescript
   // e2e/workflows/complete-ai-workflow.spec.ts
   test('complete workflow from upload to prediction', async ({ page }) => {
     // Upload
     await page.goto('/upload');
     await page.setInputFiles('input[type="file"]', 'test-data/sample.csv');
     await expect(page.locator('[data-testid="upload-success"]')).toBeVisible();

     // Transform
     await page.click('[data-testid="nav-prepare"]');
     await page.click('[data-testid="transform-scale"]');
     await page.click('[data-testid="apply-transform"]');

     // Train
     await page.click('[data-testid="nav-train"]');
     await page.selectOption('[data-testid="target-column"]', 'purchased');
     await page.click('[data-testid="start-training"]');
     await expect(page.locator('[data-testid="training-complete"]')).toBeVisible({ timeout: 60000 });

     // Predict
     await page.click('[data-testid="nav-predict"]');
     await page.fill('[data-testid="input-age"]', '35');
     await page.fill('[data-testid="input-income"]', '50000');
     await page.click('[data-testid="predict-button"]');
     await expect(page.locator('[data-testid="prediction-result"]')).toBeVisible();
   });
   ```

2. **Data Versioning** (new):
   ```typescript
   // e2e/workflows/data-versioning.spec.ts
   test('create and compare dataset versions', async ({ page }) => {
     // Upload initial dataset
     // Create version after transform
     // Compare versions
     // Verify lineage display
   });
   ```

3. **Production Deployment** (new):
   ```typescript
   // e2e/workflows/production-deployment.spec.ts
   test('deploy model to production and test API', async ({ page }) => {
     // Navigate to trained model
     // Click deploy
     // Verify API key generation
     // Test production endpoint
   });
   ```

#### Task 3.3: Performance Validation

**File**: `e2e/workflows/performance.spec.ts`

```typescript
test('performance targets met', async ({ page }) => {
  // Page load times
  const startTime = Date.now();
  await page.goto('/upload');
  const loadTime = Date.now() - startTime;
  expect(loadTime).toBeLessThan(5000); // <5s

  // Prediction latency
  const predictStart = Date.now();
  await page.click('[data-testid="predict-button"]');
  await page.waitForSelector('[data-testid="prediction-result"]');
  const predictTime = Date.now() - predictStart;
  expect(predictTime).toBeLessThan(1000); // <1s including UI
});
```

#### Task 3.4: Run Full E2E Suite

```bash
cd apps/frontend
npm run test:e2e:smoke  # Quick validation
npm run test:e2e        # Full suite
```

**Success Criteria**:
- [ ] Backend integration tests passing
- [ ] Complete workflow E2E test passing
- [ ] Data versioning E2E test passing
- [ ] Performance targets validated
- [ ] No console errors in production readiness tests

---

### Phase 4: Validation & Documentation

**Time Estimate**: 1-2 hours
**Priority**: MEDIUM

#### Task 4.1: Run Full Test Suite

```bash
# Backend
cd apps/backend
uv run pytest -v --cov=app --cov-report=term-missing

# Frontend
cd apps/frontend
npm test -- --coverage
npm run test:e2e
```

#### Task 4.2: Verify Sprint Completion Criteria

From SPRINT_12.md:
- [ ] All API endpoints use new models
- [ ] Backward compatibility maintained
- [ ] All unit tests passing (>95% coverage)
- [ ] All backend integration tests passing
- [ ] All frontend E2E tests passing
- [ ] Complete AI-guided workflows validated
- [ ] Performance within 10% of baseline
- [ ] API documentation updated
- [ ] No regressions in existing functionality
- [ ] Production readiness validated

#### Task 4.3: Update Documentation

**Files to Update**:
- `SPRINT_12.md` - Mark stories complete, update progress
- `apps/backend/docs/API_REFERENCE.md` - Update if endpoints changed
- `CLAUDE.md` - Update current stage if needed

---

## Implementation Order

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 0: Critical Fix (BLOCKER)                             │
│ ├─ Task 0.1: Resolve import cycle                           │
│ └─ Task 0.2: Verify tests run                               │
│                           ↓                                 │
├─────────────────────────────────────────────────────────────┤
│ Phase 1: Story 12.1 - API Integration         ║ Parallel    │
│ ├─ Task 1.1: Fix transformation tests         ║             │
│ ├─ Task 1.2: Fix model training tests         ║             │
│ └─ Task 1.3: Verify all endpoints             ║             │
│                           ↓                   ║             │
├─────────────────────────────────────────────────────────────┤
│ Phase 2: Story 12.3 - Service Refactoring     ║ Can start   │
│ ├─ Task 2.1: Base service class               ║ after 0.2   │
│ ├─ Task 2.2: Standardize exceptions           ║             │
│ ├─ Task 2.3: Refactor services                ║             │
│ ├─ Task 2.4: Add deprecation warnings         ║             │
│ └─ Task 2.5: Update service tests             ║             │
│                           ↓                                 │
├─────────────────────────────────────────────────────────────┤
│ Phase 3: Story 12.5 - E2E Testing                           │
│ ├─ Task 3.1: Backend integration tests                      │
│ ├─ Task 3.2: Frontend E2E gaps                              │
│ ├─ Task 3.3: Performance validation                         │
│ └─ Task 3.4: Run full suite                                 │
│                           ↓                                 │
├─────────────────────────────────────────────────────────────┤
│ Phase 4: Validation & Documentation                         │
│ ├─ Task 4.1: Full test suite                                │
│ ├─ Task 4.2: Verify completion criteria                     │
│ └─ Task 4.3: Update documentation                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Import fix breaks more code | Medium | High | Run full test suite after each change |
| Service refactoring introduces bugs | Medium | Medium | TDD approach, extensive testing |
| E2E tests flaky | Medium | Low | Use Playwright auto-waiting, increase timeouts |
| Performance targets not met | Low | Medium | Already benchmarked in Story 12.4 |

---

## Appendix: File Reference

### Backend Files to Modify

```
apps/backend/
├── app/
│   ├── services/
│   │   ├── __init__.py (update imports)
│   │   ├── base_service.py (NEW)
│   │   ├── exceptions.py (NEW)
│   │   ├── transformation_service.py → transformation_config_service.py (RENAME)
│   │   ├── dataset_service.py (refactor)
│   │   ├── model_service.py (refactor)
│   │   └── versioning_service.py (refactor)
│   ├── api/routes/
│   │   └── transformations.py (update imports)
│   └── schemas/
│       └── transformation.py (add exports)
└── tests/
    ├── test_api/
    │   ├── test_transformations.py (fix)
    │   ├── test_models.py (fix)
    │   └── test_model_training.py (fix)
    ├── test_services/
    │   └── *.py (update for new patterns)
    └── integration/
        ├── test_complete_workflow.py (NEW)
        └── test_api_contracts.py (NEW)
```

### Frontend Files to Create/Modify

```
apps/frontend/
└── e2e/
    └── workflows/
        ├── complete-ai-workflow.spec.ts (NEW)
        ├── data-versioning.spec.ts (NEW)
        ├── production-deployment.spec.ts (NEW)
        └── performance.spec.ts (NEW)
```

---

## Quick Start Commands

```bash
# 1. Fix critical blocker first
cd apps/backend
# Rename file or restructure (see Task 0.1)

# 2. Verify tests run
uv run pytest --collect-only

# 3. Run API tests
uv run pytest tests/test_api/ -v

# 4. Run service tests
uv run pytest tests/test_services/ -v

# 5. Run E2E tests
cd ../frontend
npm run test:e2e:smoke
```

---

**Document Version**: 1.0
**Author**: Claude Code
**Review Status**: Ready for implementation
