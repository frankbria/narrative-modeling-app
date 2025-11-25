# Sprint 12 Implementation Plan

**Created**: 2025-11-25
**Last Updated**: 2025-11-25
**Sprint**: 12 - API Integration & Production Readiness
**Total Story Points**: 38
**Estimated Remaining Work**: 8-12 hours

---

## Progress Summary

| Phase | Status | Completed |
|-------|--------|-----------|
| Phase 0: Critical Fix | **COMPLETE** | 2025-11-25 |
| Phase 1: API Integration | Ready to Start | - |
| Phase 2: Service Refactoring | Ready to Start | - |
| Phase 3: E2E Testing | Ready to Start | - |
| Phase 4: Validation | Pending | - |

---

## Phase 0: Critical Fix - COMPLETED

### What Was Done

**Commit**: `bc1a354` - fix(backend): resolve transformation service import cycle blocking test suite

**Problem Solved**: Namespace conflict between `transformation_service.py` (file) and `transformation_service/` (directory) was causing Python to resolve imports to the wrong module.

**Solution Applied**:
1. **Deleted duplicate directory** `apps/backend/app/services/transformation_service/` (was identical copy of `transformation_engine/`)
2. **Cleaned up imports** in `transformation_engine/__init__.py` - removed hacky sys.path manipulation
3. **Synchronized TransformationType enum** between `schemas/transformation.py` and `transformation_engine/transformation_engine.py`
4. **Fixed response schemas** - `TransformationPreviewResponse` and `TransformationApplyResponse` now match route outputs
5. **Fixed request schema** - `TransformationApplyRequest` uses flat fields for single transformation

### Test Results After Fix

| Metric | Before | After |
|--------|--------|-------|
| Test collection errors | 16 | **0** |
| Tests collected | 834 | **1032** |
| Unit tests (security, processing, utils) | blocked | **179 passed** |
| Dataset API tests | blocked | **19 passed** |
| Transformation API tests | blocked | 4 passed, 6 failed* |

*Transformation test failures are due to S3 mocking issues, not import problems. These are addressed in Phase 1.

### Verification Commands

```bash
cd apps/backend

# Verify no import errors
uv run pytest --collect-only 2>&1 | grep -E "collected|error"
# Expected: "1032 tests collected"

# Run unit tests (no database required)
uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ -v
# Expected: 179 passed

# Run dataset API tests
uv run pytest tests/test_api/test_datasets.py -v
# Expected: 19 passed
```

---

## Current State Analysis

### Story Completion Status

| Story | Status | Evidence |
|-------|--------|----------|
| 12.1 API Integration | **85%** | Routes exist, schemas fixed, 6 tests need S3 mock fixes |
| 12.2 Data Versioning | **95%** | versioning_service.py complete, routes working |
| 12.3 Service Refactoring | **70%** | Services exist, need standardization |
| 12.4 Performance | **90%** | Benchmarks complete, caching implemented |
| 12.5 E2E Testing | **60%** | 2,800 lines Playwright tests, gaps remain |

---

## Phase 1: Story 12.1 Completion - API Integration

**Status**: READY TO START
**Time Estimate**: 2-3 hours
**Priority**: HIGH

### Task 1.1: Fix Transformation API Test Mocking

**Files**:
- `tests/test_api/test_transformations.py`

**Current Issue**: Tests fail with empty error because S3 mocking isn't properly configured for the service layer.

**Actions**:
1. Update S3 mock patches to target correct import paths
2. Ensure mock returns proper DataFrame for transformation operations
3. Add proper async mock setup for service methods

**Example Fix Pattern**:
```python
# Current (failing):
with patch('app.services.transformation_engine.data_utils.get_dataframe_from_s3',
           return_value=mock_df):

# May need to also patch:
with patch('app.services.transformation_service.TransformationService.preview_transformation',
           return_value=expected_result):
```

### Task 1.2: Fix Model Training API Tests

**Files**:
- `tests/test_api/test_model_training.py`
- `tests/test_api/test_models.py`

**Issues**:
- S3 NoSuchKey errors
- Async/await patterns in mocks
- ModelCandidate initialization

### Task 1.3: Verify All API Endpoints

```bash
cd apps/backend
uv run pytest tests/test_api/ -v --tb=short
```

**Success Criteria**:
- [ ] All transformation API tests passing
- [ ] All model API tests passing
- [ ] All dataset API tests passing (currently 19/19)
- [ ] All version API tests passing

---

## Phase 2: Story 12.3 - Service Layer Refactoring

**Status**: READY TO START (can run parallel with Phase 1)
**Time Estimate**: 3-4 hours
**Priority**: MEDIUM

### Task 2.1: Extract Base Service Class

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

    async def list_for_user(self, user_id: str, skip: int = 0, limit: int = 20, **filters) -> List[T]:
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

### Task 2.2: Standardize Error Handling

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

### Task 2.3: Refactor Existing Services

**Files to Update**:
- `app/services/dataset_service.py`
- `app/services/model_service.py`
- `app/services/transformation_service.py`
- `app/services/versioning_service.py`

### Task 2.4: Update Service Tests

**Success Criteria**:
- [ ] BaseService class implemented and tested
- [ ] All services use standardized exceptions
- [ ] Service tests passing with >90% coverage

---

## Phase 3: Story 12.5 - E2E Integration Testing

**Status**: READY TO START (after Phase 1)
**Time Estimate**: 3-4 hours
**Priority**: HIGH

### Existing E2E Infrastructure

The frontend already has comprehensive E2E testing:
- **Playwright config**: `apps/frontend/playwright.config.ts`
- **Test files**: ~2,800 lines in `apps/frontend/e2e/workflows/`
- **Page objects**: `apps/frontend/e2e/pages/`
- **Fixtures**: `apps/frontend/e2e/fixtures/`

### Task 3.1: Backend Integration Tests

**New File**: `tests/integration/test_complete_workflow.py`

Test the complete ML workflow: Upload → Transform → Train → Predict

### Task 3.2: Frontend E2E Gaps

**New Files**:
- `e2e/workflows/complete-ai-workflow.spec.ts`
- `e2e/workflows/data-versioning.spec.ts`
- `e2e/workflows/production-deployment.spec.ts`

### Task 3.3: Run Full E2E Suite

```bash
cd apps/frontend
npm run test:e2e:smoke  # Quick validation
npm run test:e2e        # Full suite
```

**Success Criteria**:
- [ ] Backend integration tests passing
- [ ] Complete workflow E2E test passing
- [ ] All existing E2E tests still passing

---

## Phase 4: Validation & Documentation

**Status**: PENDING (after Phases 1-3)
**Time Estimate**: 1-2 hours
**Priority**: MEDIUM

### Task 4.1: Run Full Test Suite

```bash
# Backend
cd apps/backend
uv run pytest -v --cov=app --cov-report=term-missing

# Frontend
cd apps/frontend
npm test -- --coverage
npm run test:e2e
```

### Task 4.2: Verify Sprint Completion Criteria

From SPRINT_12.md:
- [ ] All API endpoints use new models
- [ ] Backward compatibility maintained
- [ ] All unit tests passing (>85% coverage)
- [ ] All backend integration tests passing
- [ ] All frontend E2E tests passing
- [ ] Performance within 10% of baseline
- [ ] API documentation updated

### Task 4.3: Update Documentation

- `SPRINT_12.md` - Mark stories complete
- `CLAUDE.md` - Update current stage

---

## Quick Start for Next Agent

```bash
cd /home/frankbria/projects/narrative-modeling-app/apps/backend

# 1. Verify current state
uv run pytest --collect-only 2>&1 | tail -5
# Should see: "1032 tests collected"

# 2. Run passing tests to confirm
uv run pytest tests/test_api/test_datasets.py -v --tb=short
# Should see: 19 passed

# 3. See failing transformation tests
uv run pytest tests/test_api/test_transformations.py -v --tb=short
# Should see: 4 passed, 6 failed

# 4. Start with Phase 1, Task 1.1 - Fix the S3 mocking in transformation tests
```

---

## File Reference

### Files Modified in Phase 0

```
apps/backend/
├── app/
│   ├── schemas/
│   │   └── transformation.py (MODIFIED - enum sync, response schemas)
│   └── services/
│       ├── transformation_engine/
│       │   └── __init__.py (MODIFIED - clean imports)
│       └── transformation_service/ (DELETED - was duplicate)
```

### Files to Create/Modify in Remaining Phases

```
apps/backend/
├── app/services/
│   ├── base_service.py (NEW - Phase 2)
│   ├── exceptions.py (NEW - Phase 2)
│   └── *.py (MODIFY - Phase 2)
└── tests/
    ├── test_api/
    │   └── test_transformations.py (FIX - Phase 1)
    └── integration/
        └── test_complete_workflow.py (NEW - Phase 3)

apps/frontend/
└── e2e/workflows/
    ├── complete-ai-workflow.spec.ts (NEW - Phase 3)
    ├── data-versioning.spec.ts (NEW - Phase 3)
    └── production-deployment.spec.ts (NEW - Phase 3)
```

---

## Risk Notes

| Risk | Mitigation |
|------|------------|
| S3 mock patches target wrong module | Check actual import paths in service code |
| Service refactoring breaks existing code | Run full test suite after each change |
| E2E tests flaky | Use Playwright auto-waiting, increase timeouts |

---

**Document Version**: 2.0
**Last Editor**: Claude Code
**Status**: Phase 0 Complete, Phases 1-4 Ready
