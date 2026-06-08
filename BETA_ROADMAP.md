# Beta Roadmap - Narrative Modeling App

## ⚡ 2026-06-05 Issue Triage Update

All open GitHub issues were re-triaged against the codebase and renumbered into
phases. **Work issues top-to-bottom by phase number** (`gh issue list` sorted by title):

| Phase | Theme | Issues (in order) |
|-------|-------|-------------------|
| **1 — Unblock & secure** | CI + security, no dependencies | P1.1 #147 (E2E S3 mock), P1.2 #132 (sandboxing), P1.3 #149 (SKIP_AUTH guard), P1.4 #150 (real CI pipeline), P1.5 #165 (replace vulnerable xlsx), P1.6 #164 (staging env + CI deploy — after P1.4) |
| **2 — Core ML pipeline** | The product | P2.1 #75 (AutoML engine — critical path), P2.2 #76 (training progress), P2.3 #79 (evaluation dashboard), P2.4 #87 (workflow persistence), P2.5 #155 (prepare-page crash), P2.6 #156 (ml/train 404) |
| **3 — Predictions & trust** | Complete the journey | P3.1 #82 (prediction UI), P3.2 #83 (confidence), P3.3 #80 (SHAP), P3.4 #88 (stage transitions) |
| **4 — Beta hardening** | Launch readiness | P4.1 #151 (rate limiting), P4.2 #152 (onboarding/docs/feedback), P4.3 #153 (frontend TODOs), P4.4 #157 (flaky perf tests), P4.5 #168 (deploy page contract), P4.6 #170 (real viz data — after P4.5), P4.7 #162 (history type casing), P4.8 #176 (CI/Docker hardening follow-ups — after P1.4) |
| **5 — Post-beta V2** | Deferred enhancements | P5.1 #77, P5.2 #78, P5.3 #81, P5.4 #84, P5.5 #85, P5.6 #86, P5.7 #89, P5.8 #90, P5.9 #101, P5.10 #102 |

**Closed as icebox (V3+, reopen post-V2)**: #91–#100 (RBAC, audit logging, DB
connectors, cloud storage, drift detection, degradation alerts, domain templates,
plugins, governance, A/B testing).

**Resolved open questions**: #125 and #35 are closed (superseded by #147).

Phase references below in this document predate the triage; the table above is
authoritative for issue numbering.

## Executive Summary

**Current State**: 30% complete - Backend infrastructure is excellent (214/214 tests passing), but core ML features are not implemented.

**Beta Target**: 5-7 weeks for minimum viable beta (P0 issues only), 7-9 weeks for recommended beta (P0 + P1).

**Critical Path**: Issue #75 (Core AutoML Engine) - everything else depends on this.

---

## What is a "Beta-Ready" Product?

A viable beta must support this complete user journey:

```
Upload CSV → Auto-Profile → Clean Data → Engineer Features →
Train Model (AI-guided) → Evaluate Performance → Make Predictions
```

### Current Capability Assessment

| Stage | Backend | Frontend | Status |
|-------|---------|----------|--------|
| Data Upload | ✅ Working | ⚠️ Broken (E2E tests) | Sprint 12 complete |
| Data Profiling | ✅ Infrastructure ready | ⚠️ Broken (E2E tests) | Backend APIs exist |
| Data Preparation | ✅ Working | ⚠️ Broken (E2E tests) | Transformations ready |
| Feature Engineering | ✅ Feature Store done | ❌ No AI suggestions | Backend only |
| **Model Training** | ⚠️ Infrastructure only | ❌ Not implemented | **BLOCKER** |
| **Model Evaluation** | ❌ Not implemented | ❌ Not implemented | **BLOCKER** |
| **Predictions** | ⚠️ Infrastructure only | ❌ Not implemented | **BLOCKER** |
| Deployment | ⚠️ API structure only | ❌ Not implemented | Post-beta |

**Key Insight**: Infrastructure (85%) vs. Product Features (15%)

---

## Priority Framework

### P0 - Beta Blockers (MUST HAVE)

Without these 5 issues, there's no product to beta test:

#### 1. Issue #125 - Fix 23 Failing E2E Smoke Tests
- **Type**: Bug, Frontend
- **Why Blocker**: Can't verify any frontend work; users can't use the app
- **Status**: ✅ Has Traycer AI implementation plan
- **Estimate**: 3-5 days
- **Dependencies**: None - START HERE
- **Success Criteria**: All 27 E2E smoke tests passing

#### 2. Issue #132 - Feature Store Security Sandboxing
- **Type**: Security Vulnerability, Backend
- **Why Blocker**: Arbitrary code execution risk - cannot ship with this
- **Status**: ✅ Has Traycer AI security plan
- **Estimate**: 3-5 days
- **Dependencies**: None - can work in parallel with #125
- **Success Criteria**: RestrictedPython or DSL implementation, security tests passing

#### 3. Issue #75 - Core AutoML Engine with AI-Guided Algorithm Selection
- **Type**: Enhancement, Backend
- **Why Blocker**: THE PRODUCT - users came for AutoML, this is the engine
- **Status**: ⚠️ Needs detailed implementation plan
- **Estimate**: 7-10 days
- **Dependencies**: Blocked by #125 (need frontend to test)
- **Success Criteria**:
  - Auto-detect problem type (classification/regression)
  - Recommend 3-5 suitable algorithms
  - Train models with progress tracking
  - Save trained model artifacts

#### 4. Issue #79 - Comprehensive Model Evaluation Dashboard
- **Type**: Enhancement, Frontend + Backend
- **Why Blocker**: Users must know if their model is good
- **Status**: ⚠️ Needs detailed implementation plan
- **Estimate**: 5-7 days
- **Dependencies**: Requires #75 (need trained models to evaluate)
- **Success Criteria**:
  - Accuracy metrics in business terms
  - Compare to baseline performance
  - Confusion matrix, ROC curves
  - "Model Report Card" summary

#### 5. Issue #82 - Single Record and Batch Prediction Interface
- **Type**: Enhancement, Frontend + Backend
- **Why Blocker**: Users need to USE trained models
- **Status**: ⚠️ Needs detailed implementation plan
- **Estimate**: 5-7 days
- **Dependencies**: Requires #75 (need trained models)
- **Success Criteria**:
  - Single prediction form
  - Batch CSV upload for scoring
  - Confidence scores displayed
  - Download predictions

**Total P0 Estimate**: 23-34 days (4.5-7 weeks)

---

### P1 - Beta Critical (SHOULD HAVE)

These 5 issues significantly improve beta quality:

#### 6. Issue #76 - Real-Time Training Monitoring with Progress Visualization
- **Type**: Enhancement, Frontend + Backend
- **Impact**: Users see progress instead of "waiting for 10 minutes"
- **Status**: ⚠️ Needs detailed implementation plan
- **Estimate**: 3-5 days
- **Dependencies**: Works alongside #75

#### 7. Issue #80 - Model Interpretability Tools (SHAP, Feature Importance)
- **Type**: Enhancement, Backend
- **Impact**: Users TRUST predictions (critical for ML adoption)
- **Status**: ⚠️ Needs detailed implementation plan
- **Estimate**: 5-7 days
- **Dependencies**: Requires #75

#### 8. Issue #83 - Prediction Confidence Scores and Explanations
- **Type**: Enhancement, Backend
- **Impact**: Users understand prediction uncertainty
- **Status**: ⚠️ Needs detailed implementation plan
- **Estimate**: 2-3 days
- **Dependencies**: Extends #82

#### 9. Issue #87 - Backend Workflow Persistence and State Synchronization
- **Type**: Enhancement, Backend
- **Impact**: Don't lose user work on errors/refreshes
- **Status**: ⚠️ Needs detailed implementation plan
- **Estimate**: 3-5 days
- **Dependencies**: None - can work in parallel

#### 10. Issue #88 - Seamless Stage Transitions with Data Persistence
- **Type**: Enhancement, Frontend
- **Impact**: Smooth UX across the workflow
- **Status**: ⚠️ Needs detailed implementation plan
- **Estimate**: 3-5 days
- **Dependencies**: Ties together #87

**Total P1 Estimate**: 16-25 days (3-5 weeks)

---

### P2 - Post-Beta V2 (HIGH VALUE)

These 10 issues are enhancements for Version 2:

#### Advanced ML Features
- **#77** - Automated Hyperparameter Tuning (can start with defaults in beta)
- **#78** - Model Versioning and History Tracking (can track manually in beta)
- **#81** - Error Analysis with Pattern Detection (can analyze manually in beta)

#### Deployment Enhancements
- **#84** - One-Click REST API Deployment (beta can use raw API endpoints)
- **#85** - Deployment Monitoring Dashboard (beta can use basic logging)
- **#86** - Integration Tools (Client SDKs, Postman Collections)

#### AI Enhancements
- **#89** - AI Decision Engine for Tool Selection and Parameter Optimization
- **#90** - Comprehensive AI Integration Points Across All Stages

#### Optimization Features
- **#101** - Progressive Model Training Mode (Quick vs Comprehensive)
- **#102** - Data Quality Scoring System

**Estimated for V2**: 30-40 days (6-8 weeks post-beta)

---

### P3 - Future Enhancements (V3+)

These 11 issues (all marked [LOW] priority) are for later releases:

#### Enterprise Features
- **#91** - Role-Based Access Control (RBAC) for Team Collaboration
- **#92** - Comprehensive Audit Logging System

#### Data Integration
- **#93** - Database Connectors for Live Data Sources
- **#94** - Cloud Storage Integrations (Google Drive, Dropbox, OneDrive)

#### Production ML
- **#95** - Data Drift Detection for Production Models
- **#96** - Model Performance Degradation Detection and Alerts

#### Advanced Features
- **#97** - Domain-Specific Feature Engineering Templates
- **#98** - Plugin Architecture for Custom Tools and Extensions
- **#99** - Data Governance Features (Classification, Lineage, Retention)
- **#100** - A/B Testing Framework for Model Deployment

**Estimated for V3**: 40-50 days (8-10 weeks post-V2)

---

## Implementation Phases

### Phase 1: Make It Work (Week 1)
**Goal**: Fix critical bugs so we can see progress

**Tasks**:
- [ ] Fix #125 - E2E tests (FIRST - blocks all frontend verification)
- [ ] Fix #132 - Security vulnerability (PARALLEL - different code area)

**Deliverables**:
- All 27 E2E smoke tests passing
- Secure feature execution environment
- Frontend is functional and testable

**Estimated**: 5-7 days

---

### Phase 2: Build Core ML Pipeline (Weeks 2-3)
**Goal**: Implement the actual product value proposition

**Tasks**:
- [ ] Implement #75 - AutoML Engine (FOUNDATION - 7-10 days)
- [ ] Implement #76 - Training Monitoring (alongside #75 - 3-5 days)
- [ ] Implement #79 - Evaluation Dashboard (after #75 - 5-7 days)
- [ ] Implement #87 - Workflow Persistence (PARALLEL - 3-5 days)

**Deliverables**:
- Users can train models with AI-guided algorithm selection
- Real-time training progress visible
- Comprehensive evaluation metrics displayed
- Work persists across sessions

**Estimated**: 14-21 days

**Critical Path**: #75 → #79 (sequential dependency)

---

### Phase 3: Prediction & Polish (Week 4)
**Goal**: Complete the user journey end-to-end

**Tasks**:
- [ ] Implement #82 - Prediction Interface (5-7 days)
- [ ] Implement #83 - Confidence Scores (2-3 days)
- [ ] Implement #80 - Interpretability/SHAP (5-7 days)
- [ ] Implement #88 - Stage Transitions (3-5 days)

**Deliverables**:
- Users can make single and batch predictions
- Predictions include confidence scores and explanations
- SHAP values show feature importance
- Seamless navigation across workflow stages

**Estimated**: 15-22 days

**Critical Path**: #82 → #83 (sequential dependency)

---

### Phase 4: Beta Preparation (Week 5)
**Goal**: Make it production-ready for beta users

**Tasks**:
- [ ] Integration testing across all features
- [ ] Bug fixes from integration testing
- [ ] Performance optimization (load testing)
- [ ] User documentation and onboarding
- [ ] Beta user onboarding flow
- [ ] Feedback collection mechanism

**Deliverables**:
- All features work together seamlessly
- Performance meets targets (p95 < 500ms)
- Documentation for beta users
- Onboarding tutorial/wizard
- Feedback forms and analytics

**Estimated**: 5-7 days

---

## Timeline Summary

### Minimum Viable Beta (P0 Only)
**Duration**: 5-7 weeks
**Scope**: Core user journey works end-to-end
**Risk**: Missing P1 features may frustrate early users

### Recommended Beta (P0 + P1)
**Duration**: 7-9 weeks
**Scope**: Complete, polished user experience
**Risk**: Lower - includes all critical UX features

### Version 2 Release (P0 + P1 + P2)
**Duration**: 13-17 weeks from start (6-8 weeks post-beta)
**Scope**: Advanced ML features, deployment enhancements

### Version 3+ (All Features)
**Duration**: 21-27 weeks from start (14-18 weeks post-beta)
**Scope**: Enterprise features, advanced integrations

---

## Dependency Map

```
Week 1:
  #125 (E2E tests) ────────────┐
  #132 (Security)             │
                              │
Week 2-3:                     │
  #87 (Persistence)           │
                              ├──> Phase 2 Complete
  #125 ──> #75 (AutoML) ──────┤
              │               │
              ├──> #76 (Monitoring)
              │               │
              └──> #79 (Evaluation)

Week 4:
  #75 ──> #82 (Predictions) ──> #83 (Confidence)
  #75 ──> #80 (Interpretability)
  #87 + others ──> #88 (Stage Transitions)

Week 5:
  All above ──> Integration Testing ──> Beta Launch
```

**Critical Path**: #125 → #75 → #79/#82 → Integration → Beta

---

## Success Metrics for Beta

### User Journey Metrics
- **Time to first model**: < 30 minutes (target from USER_STORIES.md)
- **Success rate by stage**:
  - Data Loading: 95%
  - Model Training: 90%
  - Model Evaluation: 95%
  - Predictions: 95%

### Quality Metrics
- **Model accuracy improvement**: 20%+ vs. baseline
- **User-reported confidence**: 4.5/5
- **Support ticket rate**: < 5% of active users

### Technical Metrics
- **API response time (p95)**: < 500ms
- **Model training time (median)**: < 10 minutes
- **Platform availability**: 99.9%
- **Test coverage**: > 85% (maintained)

---

## Risk Assessment

### High Risks

#### Risk: #75 (AutoML) is more complex than estimated
- **Mitigation**: Start with simple algorithm selection (Random Forest + Logistic Regression only)
- **Fallback**: Defer hyperparameter tuning to post-beta

#### Risk: Integration issues between frontend and backend ML APIs
- **Mitigation**: Create integration tests early (Phase 2)
- **Fallback**: Additional week for bug fixes

#### Risk: Performance issues with large datasets
- **Mitigation**: Performance testing in Phase 4
- **Fallback**: Add dataset size limits for beta

### Medium Risks

#### Risk: SHAP interpretability (#80) has library compatibility issues
- **Mitigation**: Test early with scikit-learn models
- **Fallback**: Use simpler feature importance for beta

#### Risk: Frontend state management becomes complex with workflow persistence
- **Mitigation**: Clear architectural design before #87/#88
- **Fallback**: Simplified state persistence for beta

---

## Open Questions & Decisions Needed

### Issue #35 vs #125
- **Question**: Is #35 a duplicate of #125 or a separate set of failures?
- **Action**: Investigate and close duplicate if confirmed
- **Owner**: TBD
- **Deadline**: Before starting Phase 1

### AutoML Scope for Beta (#75)
- **Question**: How many algorithms should we support in beta?
- **Options**:
  - Minimal (2-3 algorithms: Logistic Regression, Random Forest, XGBoost)
  - Moderate (5-7 algorithms: add SVM, KNN, Decision Trees)
  - Comprehensive (10+ algorithms: add Neural Nets, Ensemble methods)
- **Recommendation**: Start with Minimal for beta
- **Owner**: TBD
- **Deadline**: Before starting #75 implementation

### Interpretability Depth (#80)
- **Question**: SHAP values only, or also LIME, PDP, ICE plots?
- **Recommendation**: SHAP + feature importance for beta, others in V2
- **Owner**: TBD
- **Deadline**: Before starting #80 implementation

### Deployment Strategy (#84-86)
- **Question**: Should V2 focus on deployment or advanced ML first?
- **Recommendation**: Depends on beta user feedback
- **Owner**: TBD
- **Deadline**: Mid-beta (week 3-4 of beta testing)

---

## Beta User Acceptance Criteria

A beta is ready when a user can:

1. ✅ **Upload data** (CSV/XLSX) without errors
2. ✅ **View automatic data profiling** and insights
3. ✅ **Apply transformations** (cleaning, encoding, scaling)
4. ✅ **Get AI-powered feature suggestions** and apply them
5. ✅ **Train a model** with AI-guided algorithm selection
6. ✅ **See training progress** in real-time
7. ✅ **Evaluate model performance** with clear metrics
8. ✅ **Understand why the model works** (interpretability)
9. ✅ **Make predictions** on new data (single + batch)
10. ✅ **Trust the predictions** (confidence scores, explanations)

**All 10 criteria must be met for beta launch.**

---

## Post-Beta Product Roadmap

### Version 1.1 (1-2 months post-beta)
**Focus**: Advanced ML capabilities
- Add #77 (Hyperparameter Tuning)
- Add #78 (Model Versioning)
- Add #81 (Error Analysis)
- Improvements from beta user feedback

### Version 1.2 (3-4 months post-beta)
**Focus**: Deployment and integration
- Add #84 (One-Click API Deployment)
- Add #85 (Deployment Monitoring)
- Add #86 (Client SDKs and integration tools)
- Production deployment workflows

### Version 2.0 (6 months post-beta)
**Focus**: AI enhancements and optimization
- Add #89 (AI Decision Engine)
- Add #90 (Comprehensive AI Integration)
- Add #101 (Progressive Training Mode)
- Add #102 (Data Quality Scoring)
- Major UX improvements

### Version 3.0+ (12+ months)
**Focus**: Enterprise and advanced features
- Add #91-100 (Enterprise, governance, advanced integrations)
- Multi-user collaboration
- Advanced deployment options (edge, streaming)
- Marketplace and pre-built models

---

## Questions or Updates?

This roadmap is a living document. Update it as:
- Issues are completed
- Timeline estimates are refined
- New priorities emerge from beta testing
- Dependencies are discovered

**Last Updated**: 2026-06-05 (issue triage — see table at top)
**Next Review**: After Phase 1 completion
