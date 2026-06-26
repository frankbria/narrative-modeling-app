# Issue #89 — [P5.7] AI decision engine for tool selection and parameter optimization

**Plan source:** CodeRabbit comment plan (heavily trimmed — bot plan over-scoped ~13 files / "5-6 weeks").
**Surface:** Backend only (issue labels: backend, ml-core, phase-5). Frontend wiring deferred.

## Adapted (lean) plan — reuse established patterns

- OpenAI-with-deterministic-fallback -> EvaluationExplanationService (works fully with NO API key)
- DataProfile dataclass -> model_training/algorithm_selector.py
- TransformationType (41-value SSoT) -> app/models/transformation.py
- Rich metadata exists: DatasetMetadata, ColumnStats, DataIssueRecord, TransformationConfig
- circuit breaker -> @with_circuit_breaker

### Step 1 - Schemas (app/schemas/ai_orchestration.py)
Objective enum; ToolRecommendation; ToolRecommendationRequest/Response (pipeline_suggestion, reasoning_trace,
personalization_applied, partial); ParameterOptimizationRequest/Response; AIFeedbackRequest/Response.

### Step 2 - Feedback model (app/models/ai_feedback.py) + register in registry.py
AIRecommendationFeedback Beanie doc (user_id, dataset_id, recommendation_id, tool_type, action, rating?,
comment?, modification?, context, created_at; indexes user_id/tool_type/action).

### Step 3 - One service module (app/services/ai_orchestration_service.py)
AIOrchestrationService (never raises, degrades): build_profile(); rule-based recommenders per objective;
recommend_tools() rules+optional-OpenAI+feedback-aware ordered pipeline; optimize_parameters() rule-based;
templated/OpenAI explanations; personalization via feedback counts; module singleton.

### Step 4 - Router (app/api/routes/ai_orchestration.py) + register in main.py
POST /api/v1/ai/recommend-tools, /optimize-parameters, /feedback. Auth + ownership 404 + partial never-500.

### Step 5 - Tests
tests/test_services/test_ai_orchestration_service.py + tests/test_api/test_ai_orchestration.py

## Deviations from CodeRabbit plan
- 7 service files -> ONE module. Dropped practices.json/KnowledgeBase/BestPractice (inline heuristics).
- Dropped DataProfileBuilder module + FeedbackAnalyzer class. "Learning" = beta-level feedback counts.
- Endpoint works fully WITHOUT OpenAI key (matches #79). Frontend deferred (backend-labeled issue).

## Acceptance criteria
- [ ] AI tool selection based on data profile and objective
- [ ] Parameter optimization suggestions at each stage
- [ ] Multi-stage pipeline construction
- [ ] Plain-language explanations for all decisions
- [ ] Learning from user feedback; context-aware recommendations
