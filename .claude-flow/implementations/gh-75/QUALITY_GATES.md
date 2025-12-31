# Quality Gates: AI-Guided AutoML Training Interface
## GitHub Issue #75

**Version:** 1.0
**Created:** 2025-12-26
**Purpose:** Formalize acceptance criteria and testing requirements for production readiness

---

## Overview

Quality gates are mandatory checkpoints that must pass before:
1. **Phase Completion:** Moving from one phase to the next
2. **Pull Request Creation:** Merging code to main branch
3. **Production Deployment:** Releasing to users

**Enforcement:** All gates automated via pre-commit hooks, CI/CD pipelines, and manual validation checklists.

---

## Phase 1 Quality Gates: Backend AutoML Engine

### Gate 1.1: Unit Test Coverage

**Criteria:**
- ✅ All 45+ new unit tests passing
- ✅ Coverage >90% for new services:
  - `algorithm_selector.py`: >90%
  - `explanation_service.py`: >85%
  - `time_series_models.py`: >85%
- ✅ Coverage >85% for modified services:
  - `automl_engine.py`: >85%
  - `feature_engineer.py`: >90%

**Measurement:**
```bash
cd apps/backend
uv run pytest tests/test_model_training/ --cov=app/services/model_training --cov-report=term --cov-report=html
```

**Acceptance Threshold:**
- Line coverage: >85%
- Branch coverage: >80%
- No untested code in critical paths (algorithm selection, parallel training)

**Failure Action:**
- Add tests for uncovered lines
- Remove dead code if unreachable
- Document why code is excluded (if intentional, e.g., error handling that can't be triggered in tests)

---

### Gate 1.2: Type Safety

**Criteria:**
- ✅ mypy passes with `--strict` mode
- ✅ Zero type errors in new/modified files
- ✅ All function signatures annotated
- ✅ All dataclasses fully typed

**Measurement:**
```bash
cd apps/backend
uv run mypy app/services/model_training/ --strict
```

**Acceptance Threshold:**
- 0 errors
- 0 warnings (except intentional `type: ignore` with comment)

**Failure Action:**
- Add type annotations
- Fix type mismatches
- Use `typing.cast()` with explanation if unavoidable

---

### Gate 1.3: Code Quality

**Criteria:**
- ✅ ruff check passes (linting)
- ✅ ruff format passes (formatting)
- ✅ No complex functions (cyclomatic complexity >10)
- ✅ No duplicate code blocks (>10 lines)

**Measurement:**
```bash
cd apps/backend
uv run ruff check app/services/model_training/
uv run ruff format --check app/services/model_training/
```

**Acceptance Threshold:**
- 0 linting errors
- 0 formatting diffs
- Max cyclomatic complexity: 10 (measured by radon or similar)

**Failure Action:**
- Auto-fix: `ruff format app/services/model_training/`
- Refactor complex functions (extract helper methods)
- Eliminate duplication (extract common code)

---

### Gate 1.4: Functional Validation

**Criteria:**
- ✅ Manual test: Parallel training works
  - Script: `scripts/test_parallel_training.py`
  - Trains 5 models concurrently on 10k row dataset
  - Progress callbacks invoked in correct order
  - All models complete within 5 minutes (QUICK mode)
  - Results stored in Redis with correct keys
- ✅ Algorithm selection produces expected recommendations:
  - Small dataset (<5000 rows): No SVM/KNN recommended
  - Class imbalance (ratio >5:1): Prioritizes tree-based models, includes SMOTE recommendation
  - High interpretability: Logistic/Linear Regression in top 3

**Measurement:**
- Manual execution + visual inspection of outputs
- Automated assertion script (optional)

**Acceptance Threshold:**
- Script runs without exceptions
- Outputs match expected behavior (documented in script comments)

**Failure Action:**
- Debug functional issue
- Add unit test to prevent regression
- Document unexpected behavior for review

---

### Gate 1.5: Documentation

**Criteria:**
- ✅ `AUTOML_ENGINE.md` created with all sections
- ✅ All new functions have docstrings (Google style)
- ✅ Code examples in docs run successfully
- ✅ Architecture diagram matches implementation

**Measurement:**
- Manual review of `apps/backend/docs/AUTOML_ENGINE.md`
- Run code examples from docs
- Visual inspection of architecture diagram

**Acceptance Threshold:**
- All sections present and complete
- Code examples execute without errors
- Diagram accurately represents component relationships

**Failure Action:**
- Complete missing sections
- Fix broken code examples
- Update diagram to match implementation

---

## Phase 2 Quality Gates: Backend API & WebSocket

### Gate 2.1: Integration Test Coverage

**Criteria:**
- ✅ All 30+ integration tests passing
- ✅ Coverage >80% for API routes and WebSocket
- ✅ All 5 API endpoints tested with:
  - Success cases (200/202)
  - Error cases (404, 400, 409, 422)
  - Authentication (401)
- ✅ WebSocket tested with:
  - Connection lifecycle
  - All message types
  - Reconnection scenarios
  - Concurrent connections

**Measurement:**
```bash
cd apps/backend
uv run pytest tests/test_api/ tests/integration/ --cov=app/api --cov=app/services/training_progress_service --cov-report=term
```

**Acceptance Threshold:**
- All tests passing
- Coverage >80% for API routes
- All API contract scenarios covered

**Failure Action:**
- Add missing test cases
- Fix failing tests
- Document why test is skipped (if intentional)

---

### Gate 2.2: API Contract Compliance

**Criteria:**
- ✅ All endpoint responses match `API_CONTRACTS.md` schemas exactly
- ✅ Request validation rejects invalid inputs with correct error codes
- ✅ WebSocket messages match protocol specification
- ✅ OpenAPI spec auto-generated and accurate

**Measurement:**
- Contract test suite (Pydantic schema validation)
- Manual comparison: Postman responses vs contract schemas
- OpenAPI spec review

**Acceptance Threshold:**
- Zero schema validation errors
- All required fields present in responses
- Error codes match contract

**Failure Action:**
- Fix response schema mismatches
- Update Pydantic models
- Add request validators

---

### Gate 2.3: Backend Test Suite

**Criteria:**
- ✅ Total tests: 289 (214 baseline + 75 new)
- ✅ 100% pass rate
- ✅ Overall backend coverage >85%
- ✅ No flaky tests (run suite 3 times, all pass)

**Measurement:**
```bash
cd apps/backend
uv run pytest --cov=app --cov-report=html
# Run 3 times to check for flakiness
for i in {1..3}; do uv run pytest || exit 1; done
```

**Acceptance Threshold:**
- 289/289 tests passing
- Coverage HTML report shows >85% overall
- All 3 runs pass without failures

**Failure Action:**
- Fix failing tests
- Stabilize flaky tests (add waits, remove race conditions)
- Add tests to reach coverage threshold

---

### Gate 2.4: Performance Validation

**Criteria:**
- ✅ API response times within SLA:
  - POST /detect-problem-type: <2s
  - POST /recommend-algorithms: <3s (including OpenAI call)
  - POST /train-automl: <500ms (queues task, returns immediately)
  - GET /training-jobs/{id}/status: <200ms
  - GET /training-jobs/{id}/results: <1s
- ✅ WebSocket message latency <500ms (from Redis update to client receipt)
- ✅ Parallel training memory usage <4GB for 4 concurrent models

**Measurement:**
- Use `time` command or FastAPI middleware logging
- WebSocket latency: Timestamp comparison (server log vs browser console)
- Memory: `psutil` monitoring during training

**Acceptance Threshold:**
- 95th percentile response times below SLA
- WebSocket latency p95 <500ms
- Peak memory <4GB (configurable via max_parallel_jobs)

**Failure Action:**
- Optimize slow endpoints (caching, query optimization)
- Reduce WebSocket latency (Redis pub/sub tuning)
- Memory optimization (reduce batch sizes, garbage collection)

---

### Gate 2.5: Security Validation

**Criteria:**
- ✅ All endpoints require JWT authentication
- ✅ User cannot access other users' datasets/jobs
- ✅ WebSocket validates token on connection
- ✅ No secrets in logs (API keys, tokens masked)
- ✅ No SQL/NoSQL injection vulnerabilities (Beanie ORM protects)
- ✅ Rate limiting configured and tested

**Measurement:**
- Security test suite: Attempt unauthorized access
- Log review: No sensitive data exposed
- Penetration testing (basic): Try common injection attacks

**Acceptance Threshold:**
- All unauthorized access attempts return 401/403
- Zero secrets in logs
- Rate limiting returns 429 after threshold

**Failure Action:**
- Add authentication to unprotected endpoints
- Mask secrets in logs
- Fix authorization bugs

---

## Phase 3 Quality Gates: Frontend Training Interface

### Gate 3.1: Component Test Coverage

**Criteria:**
- ✅ All 35+ Jest tests passing
- ✅ Coverage >80% for components and hooks
- ✅ All 7 training components tested:
  - `ProblemTypeDetector`: Rendering, API calls, state
  - `AlgorithmSelector`: Selection, filtering, time calculation
  - `TrainingConfig`: Form validation, defaults
  - `TrainingProgress`: WebSocket updates, log display
  - `ModelComparison`: Table, sorting, charts
  - `BestModelCard`: Rendering, actions
- ✅ `useTrainingProgress` hook tested:
  - Connection, message parsing, reconnection, cleanup

**Measurement:**
```bash
cd apps/frontend
npm test -- --coverage --watchAll=false
```

**Acceptance Threshold:**
- All tests passing
- Coverage >80% for components, hooks, services
- No untested user interactions (clicks, form submissions)

**Failure Action:**
- Add missing tests
- Fix failing tests
- Remove dead code

---

### Gate 3.2: Type Safety

**Criteria:**
- ✅ TypeScript compilation passes in strict mode
- ✅ Zero type errors
- ✅ All API responses typed (from `lib/types/training.ts`)
- ✅ All component props typed
- ✅ No `any` types (except unavoidable, documented)

**Measurement:**
```bash
cd apps/frontend
npm run type-check  # or: tsc --noEmit
```

**Acceptance Threshold:**
- 0 errors
- 0 warnings (except intentional)

**Failure Action:**
- Add type annotations
- Fix type mismatches
- Use discriminated unions for WebSocket messages

---

### Gate 3.3: Code Quality

**Criteria:**
- ✅ eslint passes with no errors
- ✅ No console.log in production code (use proper logging)
- ✅ No unused imports or variables
- ✅ Consistent code style (Prettier formatted)

**Measurement:**
```bash
cd apps/frontend
npm run lint
npm run format:check
```

**Acceptance Threshold:**
- 0 eslint errors
- 0 warnings (except documented)
- No formatting diffs

**Failure Action:**
- Auto-fix: `npm run lint:fix`, `npm run format`
- Remove console.log (replace with logger if needed)
- Remove unused code

---

### Gate 3.4: Visual & Accessibility QA

**Criteria:**
- ✅ Visual consistency:
  - Nova theme applied (gray palette, not zinc)
  - Hugeicons used (not Lucide)
  - Nunito Sans font loaded
  - Responsive design (mobile, tablet, desktop tested)
- ✅ Accessibility (WCAG 2.1 AA):
  - Keyboard navigation works (Tab through all interactive elements)
  - Focus indicators visible
  - ARIA labels on custom components
  - Screen reader compatible (heading hierarchy, button labels)
  - Color contrast ratios >4.5:1

**Measurement:**
- Manual visual inspection (3 screen sizes)
- Keyboard-only navigation test
- axe DevTools accessibility scan
- Screen reader test (NVDA/VoiceOver basic check)

**Acceptance Threshold:**
- All visual elements match Nova theme
- All interactive elements keyboard-accessible
- Zero critical accessibility issues (axe DevTools)
- Screen reader announces component purpose

**Failure Action:**
- Fix theme inconsistencies
- Add missing ARIA labels
- Improve focus indicators
- Fix contrast issues

---

### Gate 3.5: Integration with Backend

**Criteria:**
- ✅ Frontend connects to real backend API (Phase 2 complete)
- ✅ All API responses parse correctly (no type errors)
- ✅ WebSocket connection stable over 5-minute training session
- ✅ Error handling displays user-friendly messages
- ✅ No CORS issues in development or production

**Measurement:**
- Manual workflow test: Complete training flow
- Browser DevTools: Network tab shows successful API calls
- WebSocket frames captured and validated

**Acceptance Threshold:**
- Zero network errors during happy path
- WebSocket stays connected (no reconnections)
- Error messages displayed for 404, 500 errors

**Failure Action:**
- Fix API integration bugs
- Improve error message UX
- Fix CORS configuration

---

## Phase 4 Quality Gates: E2E Testing & Documentation

### Gate 4.1: E2E Test Coverage

**Criteria:**
- ✅ All 5+ Playwright scenarios passing
- ✅ Scenarios covered:
  - Happy path: Upload → Configure → Train → Compare → Deploy
  - WebSocket reconnection
  - Training cancellation
  - Error handling (invalid dataset, all models failed)
- ✅ Tests run on clean environment (no cached data)
- ✅ Tests stable (no flakiness, run 3 times successfully)

**Measurement:**
```bash
cd apps/frontend
npm run test:e2e -- --workers=1  # Run sequentially for stability
# Run 3 times to check flakiness
for i in {1..3}; do npm run test:e2e || exit 1; done
```

**Acceptance Threshold:**
- All scenarios green
- All 3 runs pass
- Test duration <10 minutes total

**Failure Action:**
- Fix failing tests
- Stabilize flaky tests (proper waits, idempotent setup)
- Optimize slow tests (mock external services if appropriate)

---

### Gate 4.2: System-Wide Test Metrics

**Criteria:**
- ✅ Total test count: 359+
  - Backend: 299 tests
  - Frontend: 55+ tests
  - E2E: 5+ scenarios
- ✅ Overall pass rate: 100%
- ✅ Coverage:
  - Backend: >85%
  - Frontend: >80%
- ✅ No skipped tests (unless documented and approved)

**Measurement:**
- Run all test suites:
  ```bash
  cd apps/backend && uv run pytest
  cd apps/frontend && npm test -- --watchAll=false
  cd apps/frontend && npm run test:e2e
  ```

**Acceptance Threshold:**
- All tests green
- Coverage reports meet thresholds

**Failure Action:**
- Fix failures
- Add tests to meet coverage
- Document skipped tests with justification

---

### Gate 4.3: Documentation Completeness

**Criteria:**
- ✅ `AUTOML_ENGINE.md`: Complete with all sections
- ✅ `README.md`: Stage 5 section added
- ✅ `CLAUDE.md`: Synchronized (current stage, test commands, architecture)
- ✅ `SPRINTS.md`: Sprint 12 documented
- ✅ API documentation: OpenAPI spec accurate
- ✅ Code examples: All runnable and tested
- ✅ Troubleshooting guides: Common issues documented

**Measurement:**
- Manual review of each document
- Run code examples
- Validate links (no 404s)

**Acceptance Threshold:**
- All documents complete
- Code examples execute successfully
- Links valid

**Failure Action:**
- Complete missing sections
- Fix broken examples
- Update outdated documentation

---

### Gate 4.4: Performance Validation

**Criteria:**
- ✅ Training workflow performance:
  - QUICK mode (3-5 models, 10k rows): <5 minutes
  - BALANCED mode (5-7 models, 10k rows): <10 minutes
  - COMPREHENSIVE mode (8-10 models, 10k rows): <30 minutes
- ✅ WebSocket message latency: p95 <500ms
- ✅ API response times: All within SLA (see Gate 2.4)
- ✅ Frontend bundle size: <1MB gzipped (main bundle)

**Measurement:**
- Run training jobs with timer
- WebSocket latency: Browser DevTools timeline
- API: Server logs
- Bundle size: `npm run build` output

**Acceptance Threshold:**
- Training times within limits
- Latency <500ms
- API SLAs met
- Bundle size <1MB

**Failure Action:**
- Optimize slow models (reduce hyperparameter search)
- Optimize bundle (code splitting, lazy loading)
- Cache API responses

---

### Gate 4.5: Security & Compliance

**Criteria:**
- ✅ All authentication/authorization tests passing
- ✅ OWASP Top 10 vulnerabilities addressed:
  - No SQL/NoSQL injection (Beanie ORM)
  - No XSS (React escapes by default)
  - No CSRF (JWT tokens, not cookies)
  - No sensitive data exposure (logs reviewed)
- ✅ Dependency vulnerabilities: 0 high/critical (run `npm audit`, `uv pip check`)
- ✅ Secrets management: No hardcoded secrets (.env files, environment variables)

**Measurement:**
- Security test suite
- `npm audit` (frontend)
- `uv pip check` (backend)
- Manual code review (search for hardcoded API keys)

**Acceptance Threshold:**
- Zero high/critical vulnerabilities
- All secrets in environment variables
- OWASP checks pass

**Failure Action:**
- Update vulnerable dependencies
- Move secrets to .env
- Fix security issues

---

## Pre-Merge Quality Gate: Pull Request Checklist

**Required before PR approval:**

### Code Quality
- [ ] All Phase 1-4 quality gates passed
- [ ] Total tests: 359+ at 100% pass rate
- [ ] Coverage: Backend >85%, Frontend >80%
- [ ] Type checking: mypy + tsc passing
- [ ] Linting: ruff + eslint passing
- [ ] No merge conflicts with main branch

### Testing
- [ ] Unit tests added for all new functions/components
- [ ] Integration tests added for all API endpoints
- [ ] E2E test covers full workflow
- [ ] Manual testing completed on 3 browsers (Chrome, Firefox, Safari)
- [ ] Performance tests run and documented

### Documentation
- [ ] All code has docstrings/JSDoc
- [ ] `AUTOML_ENGINE.md` complete
- [ ] `README.md` updated
- [ ] `CLAUDE.md` synchronized
- [ ] `SPRINTS.md` Sprint 12 entry added
- [ ] API contract validated

### Security
- [ ] Authentication on all endpoints
- [ ] Authorization tested (user isolation)
- [ ] No secrets in code
- [ ] Dependencies scanned (no critical vulnerabilities)

### Review
- [ ] Code review by peer (Backend Specialist reviews Phase 1-2, Frontend Specialist reviews Phase 3)
- [ ] Integration Coordinator approval
- [ ] All PR comments addressed

---

## Pre-Deployment Quality Gate: Production Readiness

**Required before deploying to production:**

### Infrastructure
- [ ] MongoDB: Indexes created for TrainingJob collection
- [ ] Redis: Memory limit configured (4GB+)
- [ ] S3: Bucket permissions validated
- [ ] Environment variables: All set in production
- [ ] Secrets: Stored securely (not in code)

### Configuration
- [ ] Feature flags: Set to OFF initially
- [ ] Rate limits: Configured per API contract
- [ ] CORS: Origins whitelisted
- [ ] Logging: Levels configured (INFO in production)
- [ ] Monitoring: Alerts configured (response time, error rate)

### Testing
- [ ] Smoke tests: Run on production-like environment
- [ ] Load test: 10 concurrent training jobs (verify no crashes)
- [ ] Failover test: Redis/MongoDB restart during training (verify recovery)

### Documentation
- [ ] Deployment runbook created
- [ ] Rollback plan documented
- [ ] Monitoring dashboard configured
- [ ] On-call runbook updated

### Stakeholder Approval
- [ ] Product owner demo completed
- [ ] Technical lead sign-off
- [ ] Security review approved (if required)

---

## Continuous Quality Monitoring

**Post-deployment monitoring:**

### Metrics Dashboard
- Training job success rate: >95%
- Average training time (BALANCED mode): <10 minutes
- API p95 response time: <3s
- WebSocket connection stability: >99%
- Error rate: <1%

### Alerts
- Training job failure rate >5%: Alert on-call
- API response time >5s: Alert on-call
- WebSocket disconnection rate >5%: Investigate
- Memory usage >90%: Scale horizontally

### Weekly Review
- Test coverage trends (should not decrease)
- Performance regression (compare to baseline)
- User-reported issues
- Dependency updates available

---

## Quality Gate Failure Escalation

### Severity Levels

**Critical (Blocker):**
- Test suite failure >50%
- Security vulnerability (high/critical)
- Production outage
- Data loss risk

**Action:** Stop development, fix immediately, notify Integration Coordinator.

**High:**
- Test suite failure 10-50%
- Coverage drop >5%
- Performance degradation >20%

**Action:** Fix within 1 day, delay phase completion if needed.

**Medium:**
- Test suite failure <10%
- Documentation incomplete
- Minor performance regression

**Action:** Fix within 2 days, can proceed to next phase with plan to fix.

**Low:**
- Flaky tests (<3%)
- Minor linting issues
- Non-critical documentation gaps

**Action:** Track in backlog, fix in next sprint.

---

## Appendix: Automated Quality Gate Script

**Script:** `scripts/run_quality_gates.sh`

```bash
#!/bin/bash
set -e

echo "=== Running Quality Gates ==="

# Backend Tests
echo "=== Backend: Unit Tests ==="
cd apps/backend
uv run pytest tests/test_model_training/ --cov=app/services/model_training --cov-report=term

echo "=== Backend: Integration Tests ==="
uv run pytest tests/integration/ --cov=app/api --cov-report=term

echo "=== Backend: Type Checking ==="
uv run mypy app/services/model_training/ --strict

echo "=== Backend: Linting ==="
uv run ruff check app/services/model_training/
uv run ruff format --check app/services/model_training/

# Frontend Tests
echo "=== Frontend: Unit Tests ==="
cd ../frontend
npm test -- --watchAll=false --coverage

echo "=== Frontend: Type Checking ==="
npm run type-check

echo "=== Frontend: Linting ==="
npm run lint

# E2E Tests
echo "=== E2E: Playwright ==="
npm run test:e2e

echo "=== All Quality Gates Passed ==="
```

**Usage:**
```bash
./scripts/run_quality_gates.sh
```

**CI/CD Integration:**
- Run on every PR commit
- Block merge if any gate fails
- Post coverage reports as PR comment

---

**Document Status:** APPROVED
**Enforcement:** Automated (pre-commit hooks, CI/CD) + Manual (peer review)
**Last Updated:** 2025-12-26
