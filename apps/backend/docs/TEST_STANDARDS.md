# Testing Standards

**CRITICAL**: All new features MUST meet these mandatory requirements before being considered complete.

## Coverage Requirements

- **Minimum Coverage**: 85% code coverage ratio for all new code
- **Test Pass Rate**: 100% - all tests must pass, no exceptions
- **Test Types Required**:
  - Unit tests for all business logic and services
  - Integration tests for API endpoints
  - End-to-end tests for critical user workflows

## Running Tests

### Backend
```bash
# All tests
cd apps/backend && uv run pytest

# Unit tests only (no database required)
cd apps/backend && uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ tests/test_model_training/test_problem_detector.py tests/test_model_training/test_feature_engineer.py -v

# With coverage
cd apps/backend && uv run pytest --cov=app tests/ --cov-report=term-missing
```

### Frontend
```bash
cd apps/frontend && npm test

# With coverage
cd apps/frontend && npm run test:coverage
```

### MCP
```bash
cd apps/mcp && uv run pytest

# With coverage
cd apps/mcp && uv run pytest --cov=app tests/ --cov-report=term-missing
```

## Test Quality Standards

- **Behavior Validation**: Tests must validate behavior, not just achieve coverage metrics
- **Test Documentation**: Complex test scenarios must include comments explaining the test strategy
- **Test Isolation**: Tests must be independent and not rely on execution order
- **Fast Feedback**: Unit tests should run quickly (<5s per test suite)

## Current Test Status

**Backend**: 214/214 tests passing (100%) ✅
- Unit tests: 203 passing (no database required)
  - Service layer tests: 13 tests (DatasetService)
- Integration tests: 11 passing (require MongoDB)

**Frontend**: Jest tests configured

**MCP**: Pytest suite available

## Testing Documentation

- **Test Infrastructure**: `apps/backend/docs/TEST_INFRASTRUCTURE.md`
- **TDD Methodology**: `apps/backend/docs/TDD_GUIDE.md`
- **Sprint Details**: `apps/backend/docs/SPRINTS.md`

## Feature Completion Checklist

Before marking ANY feature as complete, verify:

- [ ] All tests pass (backend, frontend, MCP)
- [ ] Code coverage meets 85% minimum threshold
- [ ] Coverage report reviewed for meaningful test quality
- [ ] Code formatted and linted (ruff, ESLint)
- [ ] Type checking passes (mypy for Python, tsc for TypeScript)

## Rationale

These standards ensure:
- **Quality**: High test coverage and pass rates prevent regressions
- **Reliability**: Consistent quality gates maintain production stability
- **Maintainability**: Well-tested code is easier to refactor and extend
- **Confidence**: Comprehensive tests enable safe deployments
