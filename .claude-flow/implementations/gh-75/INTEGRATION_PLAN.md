# Integration Plan: AI-Guided AutoML Training Interface
## GitHub Issue #75

**Version:** 1.0
**Created:** 2025-12-26
**Integration Coordinator:** System Architect Agent
**Estimated Timeline:** 6-9 weeks

---

## Executive Summary

This implementation enhances the existing AutoML foundation with AI-guided algorithm selection, parallel training, real-time progress tracking via WebSockets, and a comprehensive training UI. The integration spans three major layers (backend, API, frontend) and requires careful coordination to maintain 100% test pass rate and >85% coverage.

**Key Success Factors:**
- API-first design with contracts defined before implementation
- Parallel specialist execution for backend and frontend phases
- Continuous integration testing at layer boundaries
- Synchronized documentation updates throughout development

---

## Architecture Overview

### Current Foundation (Existing)
- **AutoML Engine:** `/apps/backend/app/services/model_training/automl_engine.py`
- **Problem Detection:** `/apps/backend/app/services/model_training/problem_detector.py`
- **Feature Engineering:** `/apps/backend/app/services/model_training/feature_engineer.py`
- **Model Storage:** S3 via `/apps/backend/app/services/model_storage.py`
- **Batch Jobs:** `/apps/backend/app/models/batch_job.py` (pattern for async tasks)
- **Redis Caching:** `/apps/backend/app/services/redis_cache.py`
- **Basic Training API:** `/apps/backend/app/api/routes/model_training.py`
- **Frontend Button:** `/apps/frontend/components/ModelTrainingButton.tsx`

### New Components (To Build)

#### Backend Services Layer
1. **Algorithm Selector** (`algorithm_selector.py`)
   - Rule-based algorithm recommendation
   - Data profiling and analysis
   - OpenAI-powered explanations

2. **Explanation Service** (`explanation_service.py`)
   - AI-generated selection rationale
   - Model comparison explanations
   - Trade-off analysis

3. **Time Series Models** (`time_series_models.py`)
   - ARIMA wrapper
   - Prophet wrapper
   - Time series preprocessing

4. **Enhanced AutoML Engine** (modifications)
   - Parallel training with asyncio + ProcessPoolExecutor
   - Training modes (Quick/Balanced/Comprehensive)
   - Progress callback mechanism
   - Class balancing support

#### API & Infrastructure Layer
1. **Training Job Model** (`training_job.py`)
   - Extends BatchJob pattern
   - Progress tracking fields
   - Multiple model storage

2. **WebSocket Infrastructure** (`websocket.py`)
   - Connection management
   - Real-time progress broadcasting
   - JWT authentication

3. **Training Progress Service** (`training_progress_service.py`)
   - Redis-backed progress storage
   - WebSocket integration
   - TTL-based cleanup

4. **Enhanced Training API** (modifications to `model_training.py`)
   - 5 new endpoints (see API Contracts)
   - Async task coordination
   - Progress callback wiring

#### Frontend Layer
1. **Training Page** (`/datasets/[id]/train/page.tsx`)
   - Multi-step workflow state machine
   - Service integration
   - Error boundary handling

2. **UI Components** (7 new components)
   - `ProblemTypeDetector.tsx`
   - `AlgorithmSelector.tsx`
   - `TrainingConfig.tsx`
   - `TrainingProgress.tsx`
   - `ModelComparison.tsx`
   - `BestModelCard.tsx`
   - Custom hook: `useTrainingProgress.ts`

3. **Service Enhancements** (`model.ts`)
   - 6 new API client methods
   - Type-safe request/response handling

---

## Phase Breakdown & Dependencies

### Phase 1: Backend AutoML Engine (Weeks 1-3)
**Goal:** Enhance core AutoML capabilities with AI guidance, parallel training, and new algorithms.

**Specialist:** Backend Specialist (Python/FastAPI)
**Model:** Claude Sonnet 4.5
**Dependencies:** None (can start immediately)

#### Phase 1.1: Algorithm Selection Infrastructure
- Create `algorithm_selector.py` with DataProfile, AlgorithmRecommendation schemas
- Implement rule-based selection logic (dataset size, class balance, cardinality)
- Create `explanation_service.py` with OpenAI integration
- Add Redis caching for explanations
- **Tests:** 15+ unit tests for selection rules, mocked OpenAI calls
- **Coverage Target:** >90% for new services
- **Deliverable:** Algorithm recommendations with AI explanations

#### Phase 1.2: Parallel Training Infrastructure
- Enhance `automl_engine.py` with `ParallelTrainingConfig`
- Implement `_train_models_parallel()` using asyncio.gather + ProcessPoolExecutor
- Add progress callback mechanism (on_model_started, on_model_completed, on_model_failed)
- Implement timeout handling with graceful degradation
- **Tests:** 10+ unit tests with mocked models, timeout scenarios
- **Coverage Target:** >85% for parallel training code
- **Deliverable:** Concurrent model training with progress callbacks

#### Phase 1.3: Class Balancing & Time Series
- Add `imbalanced-learn` dependency to `pyproject.toml`
- Enhance `feature_engineer.py` with class balancing methods (SMOTE, RandomUnderSampler, SMOTE+Tomek)
- Create `time_series_models.py` with ARIMA/Prophet wrappers
- Add time series cross-validation
- **Tests:** 12+ unit tests for balancing, time series models
- **Coverage Target:** >90% for new functionality
- **Deliverable:** Class balancing and time series algorithm support

#### Phase 1.4: Training Modes & Model Comparison
- Add `TrainingMode` enum (QUICK/BALANCED/COMPREHENSIVE)
- Implement mode-specific configurations (algorithms, CV folds, timeouts)
- Create `ModelComparison` dataclass and comparison logic
- Add statistical significance testing (paired t-test)
- **Tests:** 8+ unit tests for modes, comparison logic
- **Coverage Target:** >85%
- **Deliverable:** Configurable training modes with model comparison

**Phase 1 Exit Criteria:**
- ✅ All 45+ backend unit tests passing
- ✅ Coverage >85% for modified/new code
- ✅ mypy/ruff checks passing
- ✅ Manual testing: Run AutoML with parallel training, verify progress callbacks work
- ✅ Documentation: AUTOML_ENGINE.md created

---

### Phase 2: Backend API & WebSocket (Weeks 4-5)
**Goal:** Expose AutoML capabilities via REST API and enable real-time progress tracking.

**Specialist:** Backend Specialist (Python/FastAPI)
**Model:** Claude Sonnet 4.5
**Dependencies:** Phase 1 complete (API depends on enhanced AutoML engine)

#### Phase 2.1: Training Job Management
- Create `training_job.py` extending BatchJob pattern
- Add TrainingProgress schema with percentage calculation
- Implement job state management methods
- **Tests:** 8+ unit tests for job lifecycle
- **Coverage Target:** >90%
- **Deliverable:** Persistent training job tracking

#### Phase 2.2: WebSocket Infrastructure
- Create `websocket.py` with ConnectionManager class
- Implement `/ws/training/{job_id}` endpoint
- Add JWT authentication to WebSocket connection
- Create `training_progress_service.py` for Redis + WebSocket integration
- **Tests:** 10+ integration tests for WebSocket broadcast, Redis storage
- **Coverage Target:** >80% (WebSocket testing has inherent complexity)
- **Deliverable:** Real-time progress broadcasting system

#### Phase 2.3: Enhanced Training API
- Add 5 new endpoints to `model_training.py`:
  - POST `/api/v1/ml/datasets/{id}/detect-problem-type`
  - POST `/api/v1/ml/datasets/{id}/recommend-algorithms`
  - POST `/api/v1/ml/datasets/{id}/train-automl`
  - GET `/api/v1/ml/training-jobs/{id}/status`
  - GET `/api/v1/ml/training-jobs/{id}/results`
- Refactor `train_model_task()` to use TrainingJob and progress callbacks
- Wire progress callbacks to TrainingProgressService
- **Tests:** 12+ integration tests for each endpoint
- **Coverage Target:** >85%
- **Deliverable:** Complete training API with progress tracking

**Phase 2 Exit Criteria:**
- ✅ All 30+ API/integration tests passing
- ✅ Total backend tests: 214 baseline + 75 new = 289 tests at 100% pass rate
- ✅ Coverage >85% overall backend
- ✅ Manual testing: WebSocket connection, progress updates, job persistence
- ✅ API documentation: OpenAPI spec updated
- ✅ Documentation: API_CONTRACTS.md validated against implementation

---

### Phase 3: Frontend Training Interface (Weeks 6-8)
**Goal:** Build comprehensive training UI with real-time progress and model comparison.

**Specialist:** Frontend Specialist (TypeScript/React)
**Model:** Claude Sonnet 4.5
**Dependencies:** Phase 2 complete (UI depends on API endpoints)

**Can Run in Parallel With:** Phase 2 (after API contracts are finalized)
**Coordination Point:** Week 4 - API contracts locked, frontend can begin with mock data

#### Phase 3.1: Service Layer & WebSocket Hook
- Enhance `lib/services/model.ts` with 6 new methods
- Create `hooks/useTrainingProgress.ts` for WebSocket connection
- Implement reconnection logic with exponential backoff
- Add TypeScript types for all API responses
- **Tests:** 8+ Jest tests for service methods, WebSocket hook
- **Coverage Target:** >80%
- **Deliverable:** Type-safe API client with WebSocket support

#### Phase 3.2: Training Page Structure
- Create `app/datasets/[id]/train/page.tsx` with workflow state machine
- Implement states: CONFIGURE → DETECTING → RECOMMENDING → TRAINING → COMPLETED
- Add loading states, error boundaries
- Fetch dataset metadata and columns
- **Tests:** 5+ Jest tests for state transitions
- **Coverage Target:** >75%
- **Deliverable:** Main training page scaffold

#### Phase 3.3: Configuration Components (Steps 1-3)
- Create `ProblemTypeDetector.tsx` with target column selector
- Create `AlgorithmSelector.tsx` with mode/optimize_for selectors
- Create `TrainingConfig.tsx` with advanced options
- Integrate with shadcn/ui components (Nova theme, gray palette, Hugeicons)
- **Tests:** 10+ Jest tests for component rendering, user interactions
- **Coverage Target:** >80%
- **Deliverable:** Training configuration workflow

#### Phase 3.4: Progress & Results Components (Steps 4-5)
- Create `TrainingProgress.tsx` with WebSocket integration
- Display algorithm status, CV fold progress, real-time metrics
- Create `ModelComparison.tsx` with comparison table, charts (Recharts)
- Create `BestModelCard.tsx` with AI explanation, action buttons
- **Tests:** 12+ Jest tests for progress updates, comparison rendering
- **Coverage Target:** >80%
- **Deliverable:** Training monitoring and results display

**Phase 3 Exit Criteria:**
- ✅ All 35+ frontend Jest tests passing
- ✅ Component tests cover user interactions, state management
- ✅ TypeScript compilation passes with strict mode
- ✅ eslint checks passing
- ✅ Manual testing: Complete training workflow end-to-end
- ✅ Visual QA: Nova theme consistency, responsive design
- ✅ Accessibility: Keyboard navigation, screen reader support

---

### Phase 4: Testing & Documentation (Week 9)
**Goal:** Comprehensive E2E testing, documentation, and deployment readiness.

**Specialist:** Test Engineer (pytest + Jest + Playwright)
**Model:** Claude Haiku (cost-effective for test generation)
**Dependencies:** Phases 1-3 complete

#### Phase 4.1: Backend Test Hardening
- Review all backend tests for edge cases
- Add integration tests for complete training workflow
- Test error scenarios: OpenAI API failure, S3 failure, MongoDB timeout
- Test concurrent training jobs (resource contention)
- **Tests:** 10+ additional integration/error tests
- **Deliverable:** Production-ready backend test suite

#### Phase 4.2: E2E Testing
- Create `e2e/workflows/train.spec.ts` in Playwright
- Test complete workflow: upload dataset → configure → train → compare → deploy
- Test WebSocket reconnection scenarios
- Test training cancellation
- Test concurrent user sessions
- **Tests:** 5+ E2E scenarios covering happy path + errors
- **Deliverable:** Automated E2E test suite

#### Phase 4.3: Documentation & Knowledge Transfer
- Create `apps/backend/docs/AUTOML_ENGINE.md`:
  - Architecture diagrams
  - Algorithm selection rules
  - Training modes explanation
  - WebSocket protocol documentation
- Update `README.md`:
  - Stage 5: Model Training section
  - API endpoint documentation
  - Training workflow examples
  - Troubleshooting guide
- Update `CLAUDE.md`:
  - New testing commands
  - Current stage (Sprint 12 → Sprint 13)
  - Architecture updates
- **Deliverable:** Complete documentation package

**Phase 4 Exit Criteria:**
- ✅ All tests passing: Backend (289), Frontend (35+), E2E (5) = 329+ total tests
- ✅ Coverage: Backend >85%, Frontend >80%
- ✅ All quality gates passing (mypy, ruff, eslint, tsc)
- ✅ E2E tests green on clean environment
- ✅ Documentation reviewed and validated
- ✅ CLAUDE.md synchronized with implementation

---

## Specialist Coordination Strategy

### Sequential Execution (Phases 1-2-3-4)
**Rationale:** API contracts must be stable before frontend development. Backend complexity requires focused attention.

**Timeline:**
- **Weeks 1-3:** Backend Specialist (Phase 1 - AutoML Engine)
- **Weeks 4-5:** Backend Specialist (Phase 2 - API & WebSocket)
- **Weeks 6-8:** Frontend Specialist (Phase 3 - UI) **CAN START WEEK 4** with API contracts
- **Week 9:** Test Engineer (Phase 4 - E2E & Docs)

### Early Parallel Opportunity (Week 4+)
Once API contracts are finalized (end of Week 3), Frontend Specialist can begin Phase 3 in parallel with Phase 2 backend work by:
- Using API contracts from `API_CONTRACTS.md`
- Implementing UI with mock API responses
- Developing WebSocket hook with mock connection

**Coordination Checkpoint (Week 5):**
- Integration Coordinator validates API implementation matches contracts
- Frontend switches from mocks to real API
- Joint testing session to verify WebSocket integration

---

## Risk Management

### Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| WebSocket connection stability issues | High | Medium | Implement exponential backoff, heartbeat mechanism, Redis fallback for progress |
| Parallel training memory exhaustion | High | Medium | Add memory monitoring, configurable max_parallel_jobs, graceful degradation |
| OpenAI API rate limits/failures | Medium | Medium | Redis caching, fallback to rule-based explanations, retry logic |
| Time series libraries (Prophet) installation issues | Medium | Low | Document dependencies clearly, test on clean environment, provide alternative (ARIMA only) |
| Frontend WebSocket hook complexity | Medium | Medium | Thorough unit tests, use established WebSocket libraries, prototype early |
| Test coverage degradation | High | Low | Pre-commit hooks, continuous coverage monitoring, Phase 4 dedicated testing |

### Schedule Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Backend Phase 1 overruns (complexity) | High | Medium | Break into smaller tasks, daily progress checks, reduce scope to BALANCED mode only if needed |
| API contract changes mid-development | High | Low | Lock contracts after Phase 1, formal change control process, version API endpoints |
| E2E test flakiness | Medium | High | Retry logic, wait for WebSocket events properly, isolate test data |
| Documentation lag behind implementation | Medium | Medium | Update docs inline with code changes, Phase 4 dedicated to sync |

---

## Quality Gates

### Per-Phase Gates

**Phase 1 (Backend AutoML):**
- ✅ All unit tests pass (45+ new tests)
- ✅ mypy --strict passes
- ✅ ruff check passes
- ✅ Coverage >85% for new/modified code
- ✅ Manual test: Parallel training with progress callbacks works
- ✅ AUTOML_ENGINE.md created and reviewed

**Phase 2 (Backend API):**
- ✅ All integration tests pass (30+ new tests)
- ✅ Total backend tests: 289 at 100% pass rate
- ✅ WebSocket connection test passes (manual + automated)
- ✅ OpenAPI spec updated and validated
- ✅ API_CONTRACTS.md matches implementation

**Phase 3 (Frontend):**
- ✅ All Jest tests pass (35+ new tests)
- ✅ tsc --noEmit passes (strict mode)
- ✅ eslint passes
- ✅ Manual workflow test: Upload → Train → Compare → Deploy
- ✅ Visual QA: Nova theme, gray palette, Hugeicons, responsive
- ✅ Accessibility check: Keyboard navigation, ARIA labels

**Phase 4 (E2E & Docs):**
- ✅ All E2E tests pass (5+ scenarios)
- ✅ Total test count: 329+ at 100% pass rate
- ✅ Overall coverage: Backend >85%, Frontend >80%
- ✅ Documentation complete and validated
- ✅ CLAUDE.md synchronized

### Integration Gates (Between Phases)

**Phase 1 → Phase 2:**
- ✅ AutoMLEngine.run() returns all_models (not just best_model)
- ✅ Progress callbacks functional and tested
- ✅ Class balancing integrated into feature engineering
- ✅ Time series algorithms available in candidate models

**Phase 2 → Phase 3:**
- ✅ All 5 API endpoints functional and tested
- ✅ WebSocket broadcasts progress updates
- ✅ TrainingJob persists correctly in MongoDB
- ✅ API contracts validated (request/response schemas match)

**Phase 3 → Phase 4:**
- ✅ Complete training workflow works end-to-end
- ✅ WebSocket connection stable over 5+ minute training session
- ✅ UI handles errors gracefully (API failure, WebSocket disconnect)
- ✅ All UI components render correctly on mobile/tablet/desktop

---

## Success Metrics

### Quantitative Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Backend test count | 214 | 289 | pytest output |
| Frontend test count | ~20 | 55+ | jest output |
| E2E test count | 0 | 5+ | playwright output |
| Backend coverage | 85% | >85% | pytest-cov |
| Frontend coverage | 70% | >80% | jest --coverage |
| Training speed (QUICK mode) | N/A | <5 min for 10k rows | Manual test |
| WebSocket latency | N/A | <500ms progress update | Browser DevTools |
| API response time (recommend-algorithms) | N/A | <3s | Server logs |

### Qualitative Metrics

- **User Experience:** Non-experts can train models without ML knowledge (validated by user testing)
- **Code Quality:** Passes all linters with zero warnings
- **Documentation Quality:** New developer can understand AutoML architecture in <30 min
- **Maintainability:** Changes to algorithm selection don't require API changes (loose coupling)
- **Observability:** Training progress visible in logs, Redis, MongoDB, and UI

---

## Rollback Strategy

### Phase-Level Rollback

Each phase is developed in a feature branch:
- `feature/gh-75-phase-1-automl`
- `feature/gh-75-phase-2-api`
- `feature/gh-75-phase-3-frontend`
- `feature/gh-75-phase-4-testing`

**Rollback Triggers:**
- Quality gate failure that cannot be resolved within 2 days
- Discovered architectural flaw requiring redesign
- Dependency unavailability (e.g., OpenAI API, Prophet library)

**Rollback Process:**
1. Identify last known good commit (previous phase completion)
2. Create rollback branch from that commit
3. Document reason for rollback in `.claude-flow/implementations/gh-75/ROLLBACK_LOG.md`
4. Revise affected phase plan
5. Communicate timeline impact to stakeholders

### Feature Flags (Production Deployment)

If deploying incrementally:
- `ENABLE_AI_TRAINING_UI`: Toggle new training page (default: false)
- `ENABLE_PARALLEL_TRAINING`: Toggle parallel execution (default: false)
- `ENABLE_ALGORITHM_RECOMMENDATIONS`: Toggle AI explanations (default: false)

**Gradual Rollout:**
1. Week 10: Deploy backend with feature flags OFF
2. Week 11: Enable ENABLE_PARALLEL_TRAINING, monitor performance
3. Week 12: Enable ENABLE_ALGORITHM_RECOMMENDATIONS, monitor OpenAI costs
4. Week 13: Enable ENABLE_AI_TRAINING_UI for beta users
5. Week 14: Full rollout

---

## Communication & Reporting

### Daily Standups (Async)
Each specialist updates `.claude-flow/implementations/gh-75/DAILY_LOG.md`:
- **Yesterday:** Tasks completed, tests added, blockers encountered
- **Today:** Tasks planned, estimated completion
- **Blockers:** Issues requiring Integration Coordinator attention

### Weekly Integration Checkpoints
Integration Coordinator reviews:
1. Test coverage trends (should never decrease)
2. API contract adherence (Phase 2/3 coordination)
3. Documentation sync status
4. Risk register updates

### Milestone Notifications
Auto-generated notifications on:
- Phase completion (all quality gates passed)
- Quality gate failure (immediate attention required)
- Schedule slip >2 days (risk mitigation needed)

---

## Appendix: Key Files Modified/Created

### Backend (Phase 1-2)

**New Files:**
- `apps/backend/app/services/model_training/algorithm_selector.py`
- `apps/backend/app/services/model_training/explanation_service.py`
- `apps/backend/app/services/model_training/time_series_models.py`
- `apps/backend/app/models/training_job.py`
- `apps/backend/app/api/websocket.py`
- `apps/backend/app/services/training_progress_service.py`
- `apps/backend/tests/test_model_training/test_algorithm_selector.py`
- `apps/backend/tests/test_model_training/test_time_series_models.py`
- `apps/backend/tests/integration/test_training_workflow.py`
- `apps/backend/docs/AUTOML_ENGINE.md`

**Modified Files:**
- `apps/backend/app/services/model_training/automl_engine.py` (parallel training, modes)
- `apps/backend/app/services/model_training/feature_engineer.py` (class balancing)
- `apps/backend/app/api/routes/model_training.py` (5 new endpoints)
- `apps/backend/tests/test_model_training/test_automl_engine.py` (parallel tests)
- `apps/backend/pyproject.toml` (dependencies: imbalanced-learn, statsmodels, prophet)

### Frontend (Phase 3)

**New Files:**
- `apps/frontend/app/datasets/[id]/train/page.tsx`
- `apps/frontend/components/training/ProblemTypeDetector.tsx`
- `apps/frontend/components/training/AlgorithmSelector.tsx`
- `apps/frontend/components/training/TrainingConfig.tsx`
- `apps/frontend/components/training/TrainingProgress.tsx`
- `apps/frontend/components/training/ModelComparison.tsx`
- `apps/frontend/components/training/BestModelCard.tsx`
- `apps/frontend/hooks/useTrainingProgress.ts`
- `apps/frontend/__tests__/components/training/*.test.tsx` (7 test files)

**Modified Files:**
- `apps/frontend/lib/services/model.ts` (6 new methods)
- `apps/frontend/app/datasets/[id]/page.tsx` (add link to train page)

### E2E Tests (Phase 4)

**New Files:**
- `apps/frontend/e2e/workflows/train.spec.ts`

### Documentation (Phase 4)

**Modified Files:**
- `README.md` (Stage 5: Model Training section)
- `CLAUDE.md` (Current Stage, testing commands, architecture updates)
- `apps/backend/docs/SPRINTS.md` (Sprint 12 completion notes)

---

## Next Steps for Integration Coordinator

1. **Validate This Plan:** Review with stakeholders, adjust timeline if needed
2. **Lock API Contracts:** Finalize `API_CONTRACTS.md` (next deliverable)
3. **Create Task Breakdown:** Detail tasks for each specialist in `TASK_BREAKDOWN.md`
4. **Define Quality Gates:** Formalize acceptance criteria in `QUALITY_GATES.md`
5. **Spawn Backend Specialist:** Initiate Phase 1 with detailed task assignment
6. **Monitor Progress:** Daily log reviews, weekly integration checkpoints
7. **Coordinate Handoffs:** Manage Phase 1→2, 2→3 transitions
8. **Final Integration:** Phase 4 E2E testing and documentation sync

---

**Document Version:** 1.0
**Last Updated:** 2025-12-26
**Status:** APPROVED - Ready for API Contracts Definition
