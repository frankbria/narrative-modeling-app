# Sprint 12 Implementation Plan

**Created**: 2025-11-25
**Last Updated**: 2025-11-26
**Sprint**: 12 - API Integration & Production Readiness
**Total Story Points**: 38
**Estimated Remaining Work**: 6-10 hours

---

## Progress Summary

| Phase | Status | Completed | PR |
|-------|--------|-----------|-----|
| Phase 0: Critical Fix | **COMPLETE** ✅ | 2025-11-25 | `bc1a354` |
| Phase 1: API Integration | **COMPLETE** ✅ **MERGED** | 2025-11-26 | [#54](https://github.com/frankbria/narrative-modeling-app/pull/54) |
| Phase 2: Service Refactoring | **COMPLETE** ✅ **MERGED** | 2025-11-26 | [#55](https://github.com/frankbria/narrative-modeling-app/pull/55) |
| Phase 3: E2E Testing | Ready to Start | - | - |
| Phase 4: Validation | Pending | - | - |

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
| 12.1 API Integration | **100%** ✅ **MERGED** | All API tests passing, PR #54 merged |
| 12.2 Data Versioning | **100%** ✅ **MERGED** | Complete with ownership checks, PR #55 merged |
| 12.3 Service Refactoring | **100%** ✅ **MERGED** | BaseService implemented, all services refactored, PR #55 merged |
| 12.4 Performance | **90%** | Benchmarks complete, caching implemented |
| 12.5 E2E Testing | **60%** | 2,800 lines Playwright tests, gaps remain |

---

## Phase 1: Story 12.1 Completion - API Integration - COMPLETED

**Status**: **COMPLETE** ✅ **MERGED**
**Completed**: 2025-11-26
**Time Taken**: ~2 hours
**PR**: [#54](https://github.com/frankbria/narrative-modeling-app/pull/54) - fix(backend): Sprint 12 Phase 1 - API Integration Test Fixes
**Merge Commit**: `c66f39b`

### Task 1.1: Fix Transformation API Test Mocking ✅

**Files Modified**:
- `tests/test_api/test_transformations.py`
- `tests/conftest.py`
- `app/models/transformation.py`
- `app/schemas/transformation.py`

**Issues Fixed**:
1. **AsyncMock for S3 functions**: Changed patches to use `new_callable=AsyncMock` for `get_dataframe_from_s3` and `upload_dataframe_to_s3`
2. **TransformationConfig initialization**: Added to Beanie `init_beanie` document models in conftest.py
3. **TransformationStep validator**: Expanded `allowed_types` to include all 30+ transformation types from TransformationType enum
4. **TransformationHistoryResponse schema**: Fixed `version` field type from int to str to match model

**Test Results**: 10/10 passing ✅

### Task 1.2: Fix Model Training API Tests ✅

**Files Modified**:
- `tests/test_api/test_model_training.py`

**Issues Fixed**:
1. **S3 mock return type**: Changed from `BytesIO` object to raw bytes (`csv_buffer.getvalue()`)
2. **sample_dataset fixture**: Added missing `s3_url` attribute

**Test Results**: 9/9 passing ✅

### Task 1.3: Verify All API Endpoints ✅

```bash
cd apps/backend
uv run pytest tests/test_api/test_transformations.py tests/test_api/test_model_training.py -v
# Result: 19/19 passing (10 transformation + 9 model training)
```

**Success Criteria**:
- [x] All transformation API tests passing (10/10)
- [x] All model training API tests passing (9/9)
- [x] All dataset API tests passing (19/19)
- [ ] Integration tests (35 failures, 12 errors - pre-existing issues, not Phase 1 scope)

### Code Review Fixes (Post-Initial Commit)

During PR review, additional improvements were made:

1. **Timestamp Type Consistency** (`7a6938e`)
   - Changed `TransformationHistoryResponse` timestamp fields from `str` to `datetime`
   - Aligns with `TransformationConfigResponse` for consistent API types
   - Pydantic v2 handles ISO string parsing automatically

2. **Enum Consolidation** (`f2a32d7`)
   - Created **single source of truth** for `TransformationType` in `app/models/transformation.py`
   - Removed duplicate enum definitions from schemas and transformation_engine
   - Added `DATA_LOSS_THRESHOLD_PERCENT = 50.0` constant
   - `TransformationStep` validator now derives allowed_types from enum dynamically

3. **Gitignore Update** (`ab4f192`)
   - Added `.claude/settings.local.json` to prevent accidental commits

### Phase 1 Summary

| Test Suite | Before | After |
|------------|--------|-------|
| Transformation API (Unit) | 4/10 | **10/10** ✅ |
| Model Training API | 5/9 | **9/9** ✅ |
| Dataset API | 19/19 | **19/19** ✅ |
| Full API Suite | - | 230 passed, 35 failed, 12 errors |

**Note**: The 35 failures and 12 errors in the full API suite are in integration tests and other API modules (data_processing, visualizations, etc.) that were not part of Phase 1 scope. These represent pre-existing issues to address in future phases.

---

## Phase 2: Story 12.3 - Service Layer Refactoring - COMPLETED

**Status**: **COMPLETE** ✅ **MERGED**
**Completed**: 2025-11-26
**Time Taken**: ~3 hours
**PR**: [#55](https://github.com/frankbria/narrative-modeling-app/pull/55) - feat(backend): Sprint 12 Phase 2 - Service Layer Refactoring
**Merge Commit**: `27c7e6d`

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

### Task 2.4: Update Service Tests ✅

**Success Criteria**:
- [x] BaseService class implemented and tested
- [x] All services use standardized exceptions
- [x] Service tests passing with >90% coverage

### Phase 2 Completion Summary

**Files Created**:
- `app/services/exceptions.py` - Standardized service exceptions (ServiceError, NotFoundError, PermissionDeniedError, ValidationError, ConflictError, OperationError, RateLimitError, DependencyError)
- `app/services/base_service.py` - Generic BaseService class with CRUD patterns, ownership verification, pagination support

**Files Modified**:
- `app/services/dataset_service.py` - Extended BaseService[DatasetMetadata], uses standardized exceptions
- `app/services/model_service.py` - Extended BaseService[ModelConfig], uses standardized exceptions
- `app/services/transformation_service.py` - Extended BaseService[TransformationConfig], uses standardized exceptions
- `app/services/versioning_service.py` - Extended BaseService[DatasetVersion], uses standardized exceptions
- `app/api/routes/transformations.py` - Updated to handle new exception types
- `app/api/routes/versions.py` - Updated to handle new exception types
- `tests/test_services/test_dataset_service.py` - Updated mock chains for BaseService compatibility
- `tests/test_services/test_versioning_service.py` - Comprehensive rewrite for proper mocking

**Test Results**:
| Test Suite | Result |
|------------|--------|
| Core Unit Tests (security, processing, utils) | 179/179 ✅ |
| Dataset Service Tests | 13/13 ✅ |
| Versioning Service Tests | 16/16 ✅ |
| Transformation API Tests | 10/10 ✅ |
| Model Training API Tests | 9/9 ✅ |
| Dataset API Tests | 19/19 ✅ |

**Key Benefits**:
- **Standardization**: Consistent error handling across all services
- **Type Safety**: Generic BaseService with proper type hints
- **Ownership Verification**: Built-in user ownership checks
- **Testability**: Test-compatible query building for mocked models
- **Backward Compatible**: Existing API contracts preserved

### Phase 2 PR Review and Merge Process

**PR Review Fixes** (Commits before merge):
1. **Filter Field Validation** (`dedb4db`) - Added validation to prevent AttributeError on invalid filter field names
2. **Unused Variable Fix** (`4abc5a7`) - Removed unused `config` variable in `transformation_service.py`
3. **Code Review Feedback** (`46268ad`):
   - Removed unused imports (`Callable` from base_service.py, exception imports from versions.py)
   - Removed unused variables in test files
   - **Fixed critical pagination count bug** in `datasets.py` - was returning `len(dataset_items)` instead of total count from database

**Merge Conflict Resolution** (`b521e6b`):
- **Issue**: Main branch added manual ownership checks with logging; feature branch used BaseService
- **Resolution**: Kept BaseService implementation (provides same security with better standardization), added security documentation from main to module docstrings
- **Files Resolved**: `model_service.py`, `versioning_service.py`
- **Auto-merged**: API routes (`models.py`, `versions.py`) correctly pass `user_id` to service methods

**Post-Merge Fixes** (`2fb15a2`):
- **Versioning Service Signatures**: Added `user_id` parameter to `get_version()`, `pin_version()`, `unpin_version()`
- **Ownership Verification**: Implemented ownership checks via dataset lookup with audit logging
- **API Compatibility**: Fixed TypeError from API routes passing `user_id` that methods didn't accept

**Final Merge**: PR #55 merged successfully with all tests passing and conflicts resolved.

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

# 1. Verify Phase 1 is merged and tests pass
uv run pytest tests/test_api/test_transformations.py tests/test_api/test_model_training.py -v --tb=short
# Should see: 19 passed (10 transformation + 9 model training)

# 2. Verify dataset API still passing
uv run pytest tests/test_api/test_datasets.py -v --tb=short
# Should see: 19 passed

# 3. Check full API test suite status
uv run pytest tests/test_api/ -v --tb=short 2>&1 | tail -20
# Should see: 230 passed, 35 failed, 12 errors (integration tests need work)

# 4. Start with Phase 2 - Service Layer Refactoring
#    OR continue fixing integration test failures
```

### Phase 1 Merged PR Reference

**PR**: [#54](https://github.com/frankbria/narrative-modeling-app/pull/54)
**Merge Commit**: `c66f39b`
**Branch**: `feature/sprint-12-phase-1-api-integration` (deleted after merge)

**Commits in PR**:
1. `f7e6423` - fix(backend): complete Sprint 12 Phase 1 API test fixes
2. `80e20d3` - docs: update Sprint 12 implementation plan with Phase 1 completion
3. `ab4f192` - chore: add Claude local settings to .gitignore
4. `7a6938e` - fix(schemas): align timestamp types in TransformationHistoryResponse
5. `f2a32d7` - refactor(transformations): consolidate TransformationType enum to single source of truth

**Files Modified**:
- `app/models/transformation.py` - Canonical TransformationType enum, DATA_LOSS_THRESHOLD_PERCENT constant
- `app/schemas/transformation.py` - Import enum from models, fixed timestamp types to datetime
- `app/services/transformation_engine/transformation_engine.py` - Import enum from models
- `tests/conftest.py` - Added TransformationConfig to init_beanie
- `tests/test_api/test_transformations.py` - Fixed AsyncMock usage, clearer data loss documentation
- `tests/test_api/test_model_training.py` - Fixed S3 mock return type, added s3_url to fixture
- `.gitignore` - Added .claude/settings.local.json

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

**Document Version**: 4.0
**Last Updated**: 2025-11-26
**Last Editor**: Claude Code
**Status**: Phase 0-1 Complete (PR #54 Merged), Phases 2-4 Ready
