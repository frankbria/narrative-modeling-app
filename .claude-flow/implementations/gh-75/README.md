# GitHub Issue #75: AI-Guided AutoML Training Interface
## Integration Coordination Package

**Status:** ✅ READY FOR EXECUTION
**Created:** 2025-12-26
**Integration Coordinator:** System Architect Agent
**Issue:** https://github.com/frankbria/narrative-modeling-app/issues/75

---

## Executive Summary

This implementation adds a comprehensive AI-guided AutoML training interface to the Narrative Modeling App, transforming it from a basic model training system into an intelligent platform that guides non-expert analysts through algorithm selection, parallel training, and model comparison with real-time progress tracking.

**Scope:**
- **Backend:** 12 new files, 7 modified files, 85+ new tests
- **Frontend:** 14 new files, 2 modified files, 40+ new tests
- **E2E:** 5+ test scenarios
- **Total Effort:** 170-220 hours (6-9 weeks)

**Key Deliverables:**
1. AI-powered algorithm recommendation system with natural language explanations
2. Parallel model training infrastructure (asyncio + ProcessPoolExecutor)
3. Real-time WebSocket progress tracking
4. Comprehensive training UI (7 new React components)
5. Complete API with 5 new endpoints
6. Production-ready test suite (359+ tests at 100% pass rate)

---

## Document Structure

This directory contains all artifacts needed for successful implementation:

### 1. **INTEGRATION_PLAN.md** (569 lines)
**Purpose:** Overall coordination strategy and architecture overview.

**Key Sections:**
- Phase breakdown (4 phases: AutoML Engine, API, Frontend, Testing)
- Specialist coordination strategy (sequential with early parallel opportunity)
- Risk management (technical + schedule)
- Quality gates (per-phase and integration checkpoints)
- Success metrics (quantitative + qualitative)
- Rollback strategy

**Audience:** Integration Coordinator, Project Managers, All Specialists

**Read Time:** 30 minutes

---

### 2. **API_CONTRACTS.md** (1,518 lines)
**Purpose:** Complete API specification between frontend and backend.

**Key Sections:**
- 5 REST API endpoints with full request/response schemas
- WebSocket protocol (11 message types)
- TypeScript type definitions (700+ lines)
- Error handling standards
- Rate limiting specifications
- Mock data for testing

**Status:** 🔒 LOCKED (changes require Integration Coordinator approval)

**Audience:** Backend Specialist, Frontend Specialist, Test Engineer

**Read Time:** 60 minutes (reference document, not sequential read)

---

### 3. **TASK_BREAKDOWN.md** (1,461 lines)
**Purpose:** Detailed task list for each specialist with acceptance criteria.

**Key Sections:**
- **Phase 1:** 10 tasks (Backend AutoML Engine, 60-80 hours)
- **Phase 2:** 8 tasks (Backend API & WebSocket, 40-50 hours)
- **Phase 3:** 9 tasks (Frontend Training Interface, 50-60 hours)
- **Phase 4:** 7 tasks (E2E Testing & Documentation, 20-30 hours)
- **Coordination Checkpoints:** 4 milestones
- **Daily Progress Tracking:** Template included

**Features:**
- Each task has: ID, description, acceptance criteria, dependencies, estimated time, files to modify
- Testing requirements per task
- Quality gate validation tasks

**Audience:** Specialist Agents (Backend, Frontend, Test Engineer)

**Read Time:** 90 minutes (specialists read only their assigned phase)

---

### 4. **QUALITY_GATES.md** (799 lines)
**Purpose:** Formalize acceptance criteria and testing requirements.

**Key Sections:**
- **Per-Phase Gates:** Phase 1 (5 gates), Phase 2 (5 gates), Phase 3 (5 gates), Phase 4 (5 gates)
- **Pre-Merge Gate:** PR checklist (code quality, testing, docs, security, review)
- **Pre-Deployment Gate:** Production readiness (infrastructure, config, monitoring)
- **Continuous Monitoring:** Post-deployment metrics and alerts
- **Escalation Process:** Severity levels and response times

**Automation:**
- Includes bash script template for CI/CD integration
- Pre-commit hooks specification

**Audience:** All Specialists, CI/CD Engineers, QA Team

**Read Time:** 45 minutes

---

### 5. **gh-75-api-contracts.json** (Memory Store)
**Purpose:** Machine-readable API contract for programmatic access.

**Contents:**
- All 5 endpoints with schema
- WebSocket message types
- Rate limits
- Caching strategies
- Training modes configuration
- Error codes

**Usage:**
- Backend validation: Compare implementation to this schema
- Frontend mocking: Generate mock data from this schema
- Contract testing: Automated schema validation

**Audience:** Automated tools, Specialist scripts

---

## Implementation Workflow

### Week 1-3: Phase 1 (Backend AutoML Engine)
**Specialist:** Backend Specialist (Sonnet 4.5)

**Deliverables:**
1. `algorithm_selector.py` - AI-guided algorithm recommendation
2. `explanation_service.py` - OpenAI integration for explanations
3. `time_series_models.py` - ARIMA, Prophet wrappers
4. Enhanced `automl_engine.py` - Parallel training, progress callbacks
5. Enhanced `feature_engineer.py` - Class balancing (SMOTE)
6. `AUTOML_ENGINE.md` - Architecture documentation
7. 45+ unit tests

**Quality Gates:**
- All tests passing (45+)
- Coverage >85%
- mypy/ruff passing
- Manual parallel training test successful

**Coordination Checkpoint:**
- End of Week 3: API contracts locked, Phase 1 report approved

---

### Week 4-5: Phase 2 (Backend API & WebSocket)
**Specialist:** Backend Specialist (Sonnet 4.5)

**Deliverables:**
1. `training_job.py` - Persistent job tracking model
2. `websocket.py` - Real-time progress infrastructure
3. `training_progress_service.py` - Redis + WebSocket bridge
4. Enhanced `model_training.py` - 5 new API endpoints
5. 30+ integration tests
6. OpenAPI spec updated

**Quality Gates:**
- All tests passing (total: 289)
- Coverage >85%
- WebSocket connection stable
- API responses match contracts exactly

**Coordination Checkpoint:**
- End of Week 5: Backend-Frontend integration session, Phase 2 report approved

**⚠️ Critical:** Frontend can begin Phase 3 in parallel after Week 3 (API contracts locked)

---

### Week 4-8: Phase 3 (Frontend Training Interface)
**Specialist:** Frontend Specialist (Sonnet 4.5)

**Can Start:** After Week 3 (API contracts locked), using mock data

**Deliverables:**
1. `lib/types/training.ts` - TypeScript types (from API contract)
2. `lib/services/model.ts` - Enhanced with 6 new API methods
3. `hooks/useTrainingProgress.ts` - WebSocket hook
4. `app/datasets/[id]/train/page.tsx` - Main training page
5. 7 training components:
   - `ProblemTypeDetector.tsx`
   - `AlgorithmSelector.tsx`
   - `TrainingConfig.tsx`
   - `TrainingProgress.tsx`
   - `ModelComparison.tsx`
   - `BestModelCard.tsx`
6. 35+ Jest tests
7. E2E test scaffold

**Quality Gates:**
- All tests passing (35+)
- TypeScript compilation strict mode
- eslint passing
- Visual QA (Nova theme, responsive)
- Accessibility check (WCAG 2.1 AA)

**Coordination Checkpoint:**
- End of Week 5: Switch from mocks to real API (after Phase 2 complete)
- End of Week 8: Pre-production validation, Phase 3 report approved

---

### Week 9: Phase 4 (E2E Testing & Documentation)
**Specialist:** Test Engineer (Haiku)

**Deliverables:**
1. 10+ edge case backend tests
2. 5+ E2E Playwright scenarios
3. `AUTOML_ENGINE.md` - Complete architecture docs
4. Updated `README.md`, `CLAUDE.md`, `SPRINTS.md`
5. Deployment runbook

**Quality Gates:**
- All tests passing (total: 359+)
- Coverage: Backend >85%, Frontend >80%
- E2E scenarios green on clean environment
- Documentation complete and validated
- Performance validation (training times, API response times)
- Security validation (auth, authorization, no secrets exposed)

**Coordination Checkpoint:**
- End of Week 9: Final review, demo, retrospective

---

## Quick Start Guide

### For Integration Coordinator

1. **Review this README** (you are here)
2. **Read INTEGRATION_PLAN.md** (overall strategy)
3. **Lock API_CONTRACTS.md** (version 1.0 approved)
4. **Spawn Backend Specialist** with Phase 1 tasks from TASK_BREAKDOWN.md
5. **Monitor daily progress** via `.claude-flow/implementations/gh-75/DAILY_LOG.md`
6. **Run coordination checkpoints** at end of each phase

### For Backend Specialist

1. **Read assigned phase** in TASK_BREAKDOWN.md (Phase 1 or Phase 2)
2. **Reference API_CONTRACTS.md** for endpoint specifications
3. **Follow quality gates** in QUALITY_GATES.md
4. **Update DAILY_LOG.md** after each task
5. **Signal completion** when all tasks + quality gates passed

### For Frontend Specialist

1. **Read Phase 3** in TASK_BREAKDOWN.md
2. **Study API_CONTRACTS.md** (especially TypeScript types section)
3. **Start with mocks** (after Week 3, API contracts locked)
4. **Switch to real API** (after Week 5, Phase 2 complete)
5. **Follow visual/accessibility guidelines** in QUALITY_GATES.md

### For Test Engineer

1. **Read Phase 4** in TASK_BREAKDOWN.md
2. **Review all quality gates** in QUALITY_GATES.md (you enforce these)
3. **Prepare E2E test infrastructure** (Playwright setup)
4. **Create edge case test scenarios** (OpenAI failures, resource contention)
5. **Validate documentation** (run code examples, check links)

---

## File Manifest

### New Files Created (33 total)

**Backend (12 files):**
```
apps/backend/app/services/model_training/algorithm_selector.py
apps/backend/app/services/model_training/explanation_service.py
apps/backend/app/services/model_training/time_series_models.py
apps/backend/app/models/training_job.py
apps/backend/app/api/websocket.py
apps/backend/app/services/training_progress_service.py
apps/backend/tests/test_model_training/test_algorithm_selector.py
apps/backend/tests/test_model_training/test_time_series_models.py
apps/backend/tests/test_models/test_training_job.py
apps/backend/tests/integration/test_training_workflow.py
apps/backend/tests/integration/test_websocket.py
apps/backend/docs/AUTOML_ENGINE.md
```

**Frontend (14 files):**
```
apps/frontend/lib/types/training.ts
apps/frontend/hooks/useTrainingProgress.ts
apps/frontend/app/datasets/[id]/train/page.tsx
apps/frontend/components/training/ProblemTypeDetector.tsx
apps/frontend/components/training/AlgorithmSelector.tsx
apps/frontend/components/training/TrainingConfig.tsx
apps/frontend/components/training/TrainingProgress.tsx
apps/frontend/components/training/ModelComparison.tsx
apps/frontend/components/training/BestModelCard.tsx
apps/frontend/__tests__/services/model.test.ts
apps/frontend/__tests__/hooks/useTrainingProgress.test.ts
apps/frontend/__tests__/app/train/page.test.tsx
apps/frontend/__tests__/components/training/*.test.tsx (7 files)
apps/frontend/e2e/workflows/train.spec.ts
```

**Documentation (7 files):**
```
.claude-flow/implementations/gh-75/INTEGRATION_PLAN.md
.claude-flow/implementations/gh-75/API_CONTRACTS.md
.claude-flow/implementations/gh-75/TASK_BREAKDOWN.md
.claude-flow/implementations/gh-75/QUALITY_GATES.md
.claude-flow/implementations/gh-75/README.md (this file)
.claude-flow/memory/implementations/gh-75-api-contracts.json
apps/backend/docs/AUTOML_ENGINE.md
```

### Modified Files (10 total)

**Backend (7 files):**
```
apps/backend/app/services/model_training/automl_engine.py
apps/backend/app/services/model_training/feature_engineer.py
apps/backend/app/api/routes/model_training.py
apps/backend/app/main.py
apps/backend/pyproject.toml
apps/backend/tests/test_model_training/test_automl_engine.py
apps/backend/tests/test_model_training/test_feature_engineer.py
```

**Frontend (2 files):**
```
apps/frontend/lib/services/model.ts
apps/frontend/app/datasets/[id]/page.tsx
```

**Documentation (1 file):**
```
README.md (Stage 5: Model Training section)
CLAUDE.md (current stage, test commands, architecture)
apps/backend/docs/SPRINTS.md (Sprint 12 completion)
```

---

## Success Metrics

### Quantitative

| Metric | Baseline | Target | Phase |
|--------|----------|--------|-------|
| Backend tests | 214 | 299 | Phase 2 |
| Frontend tests | ~20 | 55+ | Phase 3 |
| E2E scenarios | 0 | 5+ | Phase 4 |
| Backend coverage | 85% | >85% | Phase 2 |
| Frontend coverage | 70% | >80% | Phase 3 |
| Training speed (QUICK) | N/A | <5 min | Phase 4 |
| API response time | N/A | <3s | Phase 4 |
| WebSocket latency | N/A | <500ms | Phase 4 |

### Qualitative

- **User Experience:** Non-experts can train models without ML knowledge
- **Code Quality:** Passes all linters with zero warnings
- **Documentation Quality:** New developer understands AutoML in <30 min
- **Maintainability:** Algorithm changes don't require API changes (loose coupling)
- **Observability:** Training progress visible in logs, Redis, MongoDB, and UI

---

## Risk Register

### Top 3 Technical Risks

1. **WebSocket Connection Stability** (High Impact, Medium Probability)
   - **Mitigation:** Exponential backoff, heartbeat, polling fallback
   - **Contingency:** Polling-only mode (degraded UX but functional)

2. **Parallel Training Memory Exhaustion** (High Impact, Medium Probability)
   - **Mitigation:** Memory monitoring, configurable max_parallel_jobs, graceful degradation
   - **Contingency:** Sequential training mode (slower but stable)

3. **OpenAI API Rate Limits/Failures** (Medium Impact, Medium Probability)
   - **Mitigation:** Redis caching, fallback to rule-based explanations, retry logic
   - **Contingency:** Rule-based only mode (less informative but functional)

### Top 2 Schedule Risks

1. **Backend Phase 1 Overrun** (High Impact, Medium Probability)
   - **Mitigation:** Break into smaller tasks, daily progress checks
   - **Contingency:** Reduce scope to BALANCED mode only (defer QUICK/COMPREHENSIVE)

2. **E2E Test Flakiness** (Medium Impact, High Probability)
   - **Mitigation:** Retry logic, proper WebSocket waits, isolated test data
   - **Contingency:** Accept higher manual testing burden (increase QA time)

---

## Communication Plan

### Daily Updates
- Specialists update `.claude-flow/implementations/gh-75/DAILY_LOG.md`
- Format: Completed tasks, in-progress tasks, blockers, tomorrow's plan

### Weekly Checkpoints
- Integration Coordinator reviews:
  - Test coverage trends (should never decrease)
  - API contract adherence
  - Documentation sync status
  - Risk register updates

### Phase Completion Milestones
- **Phase 1:** Backend Specialist creates `PHASE_1_REPORT.md`
- **Phase 2:** Backend Specialist creates `PHASE_2_REPORT.md`
- **Phase 3:** Frontend Specialist creates `PHASE_3_REPORT.md`
- **Phase 4:** Test Engineer creates `FINAL_REPORT.md`

---

## Next Actions (Integration Coordinator)

### Immediate (Today)

1. ✅ **Review this package** (you are here)
2. ✅ **Validate INTEGRATION_PLAN.md** (strategy sound?)
3. ✅ **Lock API_CONTRACTS.md** (no changes without approval)
4. 🔲 **Create DAILY_LOG.md** (empty file for specialists to update)
5. 🔲 **Spawn Backend Specialist** with prompt:

```
You are the Backend Specialist for GitHub Issue #75: AI-Guided AutoML Training Interface.

Your assignment: Phase 1 - Backend AutoML Engine (Tasks BE-1.1.1 through BE-1.4.2 + BE-1.QG)

Read the following documents in order:
1. .claude-flow/implementations/gh-75/README.md (overview)
2. .claude-flow/implementations/gh-75/INTEGRATION_PLAN.md (Phase 1 section)
3. .claude-flow/implementations/gh-75/TASK_BREAKDOWN.md (Phase 1 tasks)
4. .claude-flow/implementations/gh-75/QUALITY_GATES.md (Phase 1 gates)

Start with Task BE-1.1.1: Create AlgorithmSelector Service.

After each task, update .claude-flow/implementations/gh-75/DAILY_LOG.md with your progress.

Estimated timeline: 60-80 hours (2-3 weeks).

Signal completion when all Phase 1 tasks + quality gates passed.
```

### Week 3 (After Phase 1)

1. 🔲 **Validate Phase 1 completion** (run quality gates)
2. 🔲 **Conduct Checkpoint 1** (API contracts locked)
3. 🔲 **Spawn Backend Specialist for Phase 2**
4. 🔲 **Spawn Frontend Specialist for Phase 3** (parallel execution)

### Week 5 (After Phase 2)

1. 🔲 **Validate Phase 2 completion**
2. 🔲 **Conduct Checkpoint 2** (Backend-Frontend integration)
3. 🔲 **Frontend switches from mocks to real API**

### Week 8 (After Phase 3)

1. 🔲 **Validate Phase 3 completion**
2. 🔲 **Conduct Checkpoint 3** (Pre-production validation)
3. 🔲 **Spawn Test Engineer for Phase 4**

### Week 9 (After Phase 4)

1. 🔲 **Validate Phase 4 completion**
2. 🔲 **Conduct Checkpoint 4** (Final review)
3. 🔲 **Create Pull Request** (merge to main)
4. 🔲 **Deploy to production** (gradual rollout with feature flags)

---

## Appendix: Key Decisions

### Architectural Decisions

1. **API-First Design:** Contracts defined before implementation (enables parallel frontend work)
2. **WebSocket + Polling:** Primary WebSocket, fallback to polling (reliability)
3. **Redis for Progress:** Temporary storage with MongoDB backup (performance + persistence)
4. **ProcessPoolExecutor:** CPU-bound training in separate processes (true parallelism)
5. **OpenAI with Fallback:** Rule-based explanations if AI fails (graceful degradation)

### Technology Choices

1. **Backend:**
   - FastAPI WebSocket (native support, well-documented)
   - imbalanced-learn (mature, scikit-learn compatible)
   - statsmodels + Prophet (industry-standard time series)
   - pmdarima (auto-ARIMA simplifies hyperparameter search)

2. **Frontend:**
   - React hooks (useTrainingProgress for WebSocket state)
   - shadcn/ui + Nova theme (consistent with existing UI)
   - Recharts (lightweight, easy customization)
   - Playwright (E2E testing standard)

### Process Choices

1. **Sequential Phases:** Backend → API → Frontend (reduces integration risk)
2. **Early Parallel Opportunity:** Frontend starts Week 4 with mocks (accelerates timeline)
3. **Quality Gates:** Per-phase gates prevent technical debt accumulation
4. **Test-First:** Unit tests alongside implementation (not after)

---

## Support & Escalation

### For Questions

1. **API Contract Ambiguity:** Reference `API_CONTRACTS.md`, consult Integration Coordinator if unclear
2. **Task Dependencies Unclear:** Check `TASK_BREAKDOWN.md` dependencies section
3. **Quality Gate Failure:** Review `QUALITY_GATES.md` failure actions

### For Blockers

1. **Critical (Blocker):** Notify Integration Coordinator immediately (Slack/email)
2. **High:** Document in DAILY_LOG.md, flag in daily update
3. **Medium/Low:** Document in DAILY_LOG.md, resolve within phase

### For Changes

1. **API Contract Change:** Formal change request to Integration Coordinator
2. **Task Scope Change:** Document rationale, get approval before proceeding
3. **Timeline Change:** Update DAILY_LOG.md, notify Integration Coordinator

---

## Document Maintenance

- **INTEGRATION_PLAN.md:** Updated after each checkpoint (Integration Coordinator)
- **API_CONTRACTS.md:** LOCKED (version bumps only with formal approval)
- **TASK_BREAKDOWN.md:** Updated if task estimates change (with approval)
- **QUALITY_GATES.md:** Updated if new quality requirements discovered
- **DAILY_LOG.md:** Updated daily by active specialist

---

## Conclusion

This integration coordination package provides everything needed to successfully implement GitHub Issue #75: AI-Guided AutoML Training Interface.

**Key Strengths:**
- ✅ Comprehensive documentation (4,347 lines across 4 docs)
- ✅ Locked API contracts (frontend/backend can work in parallel)
- ✅ Detailed task breakdown (47 tasks with acceptance criteria)
- ✅ Rigorous quality gates (20 gates across 4 phases)
- ✅ Risk mitigation strategies (technical + schedule)
- ✅ Clear communication plan (daily updates, weekly checkpoints)

**Success Criteria:**
- 359+ tests at 100% pass rate
- Coverage: Backend >85%, Frontend >80%
- All quality gates passed
- Documentation synchronized
- Production-ready deployment

**Estimated Timeline:** 6-9 weeks (170-220 hours)

**Next Step:** Integration Coordinator spawns Backend Specialist for Phase 1.

---

**Document Version:** 1.0
**Last Updated:** 2025-12-26
**Status:** ✅ APPROVED - Ready for Execution
**Prepared By:** System Architect Agent (Integration Coordinator)

**Questions?** Contact Integration Coordinator via `.claude-flow/implementations/gh-75/DAILY_LOG.md` (blockers section)
