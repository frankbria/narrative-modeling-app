# Issue #90 — AI assistance integration across all 8 workflow stages (lean, adapted)

**Labels:** enhancement, P2-Medium, backend, ml-core, phase-5 (post-beta V2)

## Why the Traycer plan is over-scoped / stale
- Its centerpiece `app/services/ai_orchestration_service.py` **already exists** (shipped in #89, the previous commit).
- 6 of 8 stages already have backend AI: profiling (#2 ai_analysis/ai_summary), data-prep (#3) + feature-eng (#4) via #89 `recommend-tools`/`optimize-parameters`, model-selection (#5) via `explanation_service`, evaluation (#6) via #79 report card + #81 error analysis.
- Genuine gaps vs the 4 ACs: (a) **Stage 8 deployment has NO AI**, (b) no **shared personality/tone** across services (each has its own inline prompt), (c) no **cross-stage context accumulation**, (d) structured outputs already done.

## Adapted scope — one cohesive capability, backend-only
Build "stage guidance" on the existing #89 `AIOrchestrationService` + #87 `WorkflowState`. Frontend deferred (issue is backend/ml-core labeled — matches #89 precedent).

### Backend
1. **Shared persona** — `AI_MENTOR_PERSONA` constant in `ai_orchestration_service.py`; existing `_openai_summary` + new stage-guidance call both use it -> AC2 consistent tone.
2. **Schemas** (`app/schemas/ai_orchestration.py`): `WorkflowStageId` enum (8 stages), `StageGuidanceRequest{dataset_id, stage, accumulated_context?}`, `StageGuidanceResponse{focus, guidance_summary, key_considerations[], suggested_actions[], context_used[], reasoning_trace[], generated_by, partial}`.
3. **`generate_stage_guidance(profile, stage, request_context, user_id)`**:
   - Context accumulation (AC3): best-effort load persisted `WorkflowState` (#87) -> prior `completed_stages` + `stage_data`; merge request `accumulated_context`; list in `context_used`.
   - Rule-based per-stage core for all 8 stages (works w/o key); reuse `_cleaning/_feature/_modeling_recs` where natural; **dedicated deployment guidance** (real-time vs batch by problem_type/size, monitoring, pre-deploy checklist) — the gap.
   - Optional OpenAI enhancement `_stage_guidance_summary()` behind `@with_circuit_breaker("openai", fallback_value=None)`, JSON mode, persona-prefixed; `generated_by` hybrid/rule_based; never raises.
4. **Endpoint** `POST /api/v1/ai/stage-guidance` (auth, 404 unknown/foreign, never 500).
5. **Tests**: extend `test_services/test_ai_orchestration_service.py` + `test_api/test_ai_orchestration.py`.
6. **Docs**: CLAUDE.md #90 note.

### Dropped from Traycer (with reason)
- Re-create ai_orchestration_service / 5 new *_ai_service.py — already covered by #89 + this one method.
- 5 frontend components / WorkflowContext aiContext / ContextualAIHelp — frontend deferred (backend-labeled).
- Redis caching + per-user rate limit — YAGNI; global rate limiting already exists (#151).
- Separate ai_prompts.py / ai_responses.py modules — one persona constant + extend existing schemas.
