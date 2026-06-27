# Issues Needing Detailed Implementation Plans

## Overview

This document identifies which issues have detailed implementation plans and which need them before work can begin.

---

## ✅ Issues WITH Implementation Plans

These issues have comprehensive Traycer AI plans and can be started immediately:

### Issue #125 - Fix 23 Failing E2E Smoke Tests
- **Status**: ✅ Complete Traycer AI plan available
- **Plan Location**: GitHub issue comments (Traycer AI section)
- **Key Points**:
  - Fix fixture navigation mismatch (upload vs dashboard)
  - Update CI workflow environment variables
  - Make backend health checks more lenient
  - Add S3 service mock mode
  - 8 implementation steps with clear file references
- **Ready to Start**: YES
- **Estimated Effort**: 3-5 days

### Issue #132 - Feature Store Security Sandboxing
- **Status**: ✅ Complete Traycer AI security plan available
- **Plan Location**: GitHub issue comments (Traycer AI section)
- **Key Points**:
  - Document existing safe architecture (ExpressionEvaluator)
  - Add enhanced security validation layer
  - Implement comprehensive security testing
  - Strengthen input validation and sanitization
  - 8 implementation steps with security architecture diagram
- **Ready to Start**: YES
- **Estimated Effort**: 3-5 days

---

## ⚠️ Issues NEEDING Implementation Plans

These issues require detailed planning before implementation:

### P0 - Beta Blockers (CRITICAL)

#### Issue #75 - Core AutoML Engine with AI-Guided Algorithm Selection
- **Status**: ⚠️ NEEDS PLAN
- **Why Critical**: This is the foundation - all other ML features depend on it
- **Complexity**: HIGH - this is the product's core value proposition
- **Key Decisions Needed**:
  - Which ML libraries? (scikit-learn, XGBoost, LightGBM, AutoGluon?)
  - How many algorithms for beta? (Minimal: 2-3 vs Comprehensive: 10+)
  - Algorithm selection strategy (rule-based vs ML-based meta-learning?)
  - Training orchestration (synchronous vs async background tasks?)
  - Model artifact storage format (pickle, joblib, PMML, ONNX?)
  - Cross-validation strategy
  - How to handle class imbalance, time series, etc.
- **Dependencies**: None, but blocks #79, #80, #82, #83
- **Estimated Planning Time**: 1-2 days
- **Estimated Implementation**: 7-10 days
- **Recommendation**: Start planning NOW - this is the critical path

#### Issue #79 - Comprehensive Model Evaluation Dashboard
- **Status**: ⚠️ NEEDS PLAN
- **Complexity**: MEDIUM - frontend + backend integration
- **Key Decisions Needed**:
  - Which metrics to display? (accuracy, precision, recall, F1, AUC-ROC, etc.)
  - Visualization library? (Chart.js, D3.js, Recharts, Plotly?)
  - How to handle different problem types? (binary, multiclass, regression)
  - Real-time updates during training or post-training only?
  - Export format for reports?
- **Dependencies**: Requires #75 (need trained models to evaluate)
- **Estimated Planning Time**: 1 day
- **Estimated Implementation**: 5-7 days

#### Issue #82 - Single Record and Batch Prediction Interface
- **Status**: ⚠️ NEEDS PLAN
- **Complexity**: MEDIUM - frontend form + backend API
- **Key Decisions Needed**:
  - Single prediction UI design (form-based vs JSON input?)
  - Batch prediction: file upload or API endpoint?
  - How to handle missing features in prediction input?
  - Real-time vs batch processing for large files?
  - Prediction result format and storage
- **Dependencies**: Requires #75 (need trained models)
- **Estimated Planning Time**: 1 day
- **Estimated Implementation**: 5-7 days

---

### P1 - Beta Critical (SHOULD HAVE)

#### Issue #76 - Real-Time Training Monitoring with Progress Visualization
- **Status**: ⚠️ NEEDS PLAN
- **Complexity**: MEDIUM - async communication frontend ↔ backend
- **Key Decisions Needed**:
  - Communication mechanism? (WebSockets, Server-Sent Events, polling?)
  - What to monitor? (epochs, loss, accuracy, time remaining?)
  - How to estimate time remaining with different algorithms?
  - Progress bar UX design
  - How to handle long-running training (hours)?
- **Dependencies**: Works alongside #75
- **Estimated Planning Time**: 1 day
- **Estimated Implementation**: 3-5 days

#### Issue #80 - Model Interpretability Tools (SHAP, Feature Importance)
- **Status**: ⚠️ NEEDS PLAN
- **Complexity**: MEDIUM - SHAP library integration
- **Key Decisions Needed**:
  - SHAP implementation (TreeExplainer, KernelExplainer, LinearExplainer?)
  - Feature importance for each algorithm type
  - How to visualize SHAP values? (waterfall, force plot, summary plot?)
  - Performance considerations for large datasets
  - Frontend visualization library
- **Dependencies**: Requires #75 (need trained models)
- **Estimated Planning Time**: 1 day
- **Estimated Implementation**: 5-7 days

#### Issue #83 - Prediction Confidence Scores and Explanations
- **Status**: ⚠️ NEEDS PLAN
- **Complexity**: LOW - extends #82
- **Key Decisions Needed**:
  - Confidence calculation (predict_proba, calibration?)
  - How to explain individual predictions?
  - Uncertainty quantification for regression
  - Display format (percentage, probability distribution?)
- **Dependencies**: Extends #82
- **Estimated Planning Time**: 0.5 days
- **Estimated Implementation**: 2-3 days

#### Issue #87 - Backend Workflow Persistence and State Synchronization
- **Status**: ⚠️ NEEDS PLAN
- **Complexity**: MEDIUM - state management architecture
- **Key Decisions Needed**:
  - What to persist? (all transformations, features, model configs?)
  - Storage mechanism (MongoDB documents, separate collections?)
  - Versioning strategy for workflow state
  - How to handle partial workflows (user exits mid-process)?
  - Recovery mechanism for failures
- **Dependencies**: None - can work in parallel
- **Estimated Planning Time**: 1 day
- **Estimated Implementation**: 3-5 days

#### Issue #88 - Seamless Stage Transitions with Data Persistence
- **Status**: ⚠️ NEEDS PLAN
- **Complexity**: MEDIUM - frontend state management
- **Key Decisions Needed**:
  - Frontend state library? (Redux, Zustand, Context API?)
  - Navigation flow between stages
  - Data validation before allowing transition
  - How to handle "back" navigation (restore state or reload?)
  - Progress indicator across stages
- **Dependencies**: Works with #87 for backend persistence
- **Estimated Planning Time**: 1 day
- **Estimated Implementation**: 3-5 days

---

## Planning Priority Recommendation

### Immediate (Week 1)
No planning needed - implement #125 and #132 (both have plans)

### High Priority (Start of Week 2)
1. **#75 (AutoML Engine)** - MOST CRITICAL
   - Block 1-2 days for comprehensive planning
   - This is the foundation for everything else
   - Consider using the `Task` tool with `subagent_type='system-architect'` for architecture review

### Medium Priority (During Week 2-3)
2. **#76 (Training Monitoring)** - Plan alongside #75 implementation
3. **#79 (Evaluation Dashboard)** - Plan while #75 is in progress
4. **#87 (Workflow Persistence)** - Can plan in parallel with #75

### Lower Priority (Week 3-4)
5. **#82 (Prediction Interface)** - Plan after #75 is mostly done
6. **#80 (SHAP Interpretability)** - Plan after #75 is mostly done
7. **#83 (Confidence Scores)** - Quick plan, extends #82
8. **#88 (Stage Transitions)** - Plan after understanding state shape from #87

---

## How to Get Implementation Plans

### Option 1: Use Traycer AI (Recommended for complex issues)
Traycer AI can generate comprehensive implementation plans with:
- Step-by-step implementation details
- File references and line numbers
- Dependency diagrams
- Verification steps

**Process**:
1. Add comment to GitHub issue: `@traycerai generate`
2. Wait for Traycer AI to analyze and generate plan
3. Review and refine plan
4. Use generated plan for implementation

**Best for**: #75, #79, #80, #82 (complex features)

### Option 2: Use Claude Code Planning
For simpler issues or when you want more control:

**Process**:
1. Use the `EnterPlanMode` tool in Claude Code
2. Explore codebase to understand current architecture
3. Design implementation approach
4. Get user approval before implementing

**Best for**: #76, #83, #87, #88 (medium complexity)

### Option 3: Manual Planning
For very simple issues:

**Process**:
1. Review existing code patterns
2. Write brief implementation plan in issue comments
3. Get peer review if possible
4. Implement

**Best for**: #83 (extends existing work)

---

## Key Questions to Answer in Each Plan

### For ML Features (#75, #76, #79, #80, #82, #83)
1. Which ML libraries and versions?
2. How to handle different problem types (classification, regression)?
3. Performance targets (latency, throughput)?
4. Error handling strategy?
5. Testing approach (unit, integration, E2E)?
6. API design (request/response schemas)?
7. Frontend components needed?
8. Data storage requirements?

### For State Management (#87, #88)
1. State shape and structure?
2. Persistence mechanism?
3. Synchronization strategy?
4. Conflict resolution?
5. Performance considerations?
6. Testing approach?

---

## Current Status Summary

| Issue | Priority | Has Plan? | Ready to Start? | Blocks Others? |
|-------|----------|-----------|-----------------|----------------|
| #125  | P0       | ✅ Yes    | ✅ Yes          | 🔴 Blocks all frontend |
| #132  | P0       | ✅ Yes    | ✅ Yes          | 🟡 Security requirement |
| #75   | P0       | ❌ No     | ❌ No           | 🔴 Blocks #79, #80, #82, #83 |
| #79   | P0       | ❌ No     | ❌ No           | 🟢 No dependencies |
| #82   | P0       | ❌ No     | ❌ No           | 🟡 Blocks #83 |
| #76   | P1       | ❌ No     | ❌ No           | 🟢 No dependencies |
| #80   | P1       | ❌ No     | ❌ No           | 🟢 No dependencies |
| #83   | P1       | ❌ No     | ❌ No           | 🟢 No dependencies |
| #87   | P1       | ❌ No     | ❌ No           | 🟡 Feeds into #88 |
| #88   | P1       | ❌ No     | ❌ No           | 🟢 No dependencies |

**Action Required**: Create plan for #75 before starting Week 2 work

---

## Next Steps

1. ✅ Run the labeling script: `./scripts/label-github-issues.sh`
2. ✅ Start work on #125 (has plan, blocks everything)
3. ✅ Start work on #132 (has plan, security requirement)
4. ⚠️ **Create implementation plan for #75** (most critical)
5. ⏸️ Wait for #75 plan before planning #79, #80, #82

**Estimated Planning Effort**: 6-8 days total across all 8 issues
**Recommendation**: Plan 1-2 issues ahead of implementation to avoid blocking
