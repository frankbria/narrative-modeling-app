# Task Breakdown: AI-Guided AutoML Training Interface
## GitHub Issue #75

**Version:** 1.0
**Created:** 2025-12-26
**For:** Specialist Agents (Backend, Frontend, Test Engineer)

---

## How to Use This Document

Each specialist receives a phase-specific task list with:
- **Task ID:** Unique identifier (e.g., `BE-1.1.1`)
- **Description:** What to implement
- **Acceptance Criteria:** How to verify completion
- **Dependencies:** Prerequisites before starting
- **Estimated Time:** Hours (for planning)
- **Files:** Specific files to create/modify

**Workflow:**
1. Read assigned phase tasks
2. Complete tasks sequentially (respect dependencies)
3. Update `.claude-flow/implementations/gh-75/DAILY_LOG.md` after each task
4. Run tests after each task
5. Signal completion when all phase tasks done + quality gates passed

---

## Phase 1: Backend AutoML Engine (Backend Specialist)

**Goal:** Enhance AutoML with AI guidance, parallel training, and new algorithms.
**Estimated Time:** 60-80 hours (2-3 weeks)
**Model:** Claude Sonnet 4.5

### Phase 1.1: Algorithm Selection Infrastructure

#### Task BE-1.1.1: Create AlgorithmSelector Service
**Description:** Implement algorithm selection with rule-based prioritization.

**Acceptance Criteria:**
- ✅ File `apps/backend/app/services/model_training/algorithm_selector.py` created
- ✅ `DataProfile` dataclass with fields: n_samples, n_features, feature_types_dist, class_balance_ratio, missing_value_pct, high_cardinality_features
- ✅ `AlgorithmRecommendation` dataclass with all fields from API contract
- ✅ `AlgorithmSelector` class with `select_algorithms()` method
- ✅ Selection rules implemented:
  - Dataset size thresholds (SVM/KNN <5000, GBM for large)
  - Class imbalance detection (ratio >2:1)
  - High cardinality handling
  - Interpretability scoring (1-10)
  - Training time estimation formulas
- ✅ Returns recommendations sorted by priority
- ✅ Method signature: `select_algorithms(problem_type: ProblemType, data_profile: DataProfile, config: AlgorithmSelectionConfig) -> List[AlgorithmRecommendation]`

**Dependencies:** None

**Files to Create:**
- `apps/backend/app/services/model_training/algorithm_selector.py`

**Files to Modify:**
- `apps/backend/app/services/model_training/__init__.py` (add imports)

**Estimated Time:** 6 hours

**Testing:**
- Create `tests/test_model_training/test_algorithm_selector.py`
- Tests: dataset size rules, class imbalance detection, interpretability scoring, priority ordering
- Target: 10+ unit tests, >90% coverage

---

#### Task BE-1.1.2: Create ExplanationService
**Description:** Integrate OpenAI API for AI-generated algorithm explanations.

**Acceptance Criteria:**
- ✅ File `apps/backend/app/services/model_training/explanation_service.py` created
- ✅ `ExplanationService` class with methods:
  - `explain_algorithm_selection(algorithms, data_profile, problem_type) -> Dict[str, str]`
  - `explain_best_model(best_model, all_models, comparison_metrics) -> str`
  - `explain_model_tradeoffs(model_a, model_b) -> str`
- ✅ Uses existing `OpenAIService` pattern (see `apps/backend/app/services/openai_service.py`)
- ✅ Structured prompts with data characteristics, algorithm properties
- ✅ Redis caching with key pattern `explanation:{hash}`, TTL 1 hour
- ✅ Fallback to rule-based explanations if OpenAI fails (no exceptions thrown)
- ✅ Handles rate limits gracefully

**Dependencies:** Task BE-1.1.1 (needs AlgorithmRecommendation)

**Files to Create:**
- `apps/backend/app/services/model_training/explanation_service.py`

**Files to Modify:**
- `apps/backend/app/services/model_training/__init__.py`

**Estimated Time:** 5 hours

**Testing:**
- Add tests to `tests/test_model_training/test_algorithm_selector.py`
- Mock OpenAI API calls
- Tests: successful explanation, OpenAI failure fallback, Redis caching, hash collision
- Target: 8+ unit tests, >85% coverage

---

#### Task BE-1.1.3: Integrate AlgorithmSelector with AutoMLEngine
**Description:** Connect algorithm selection to AutoML engine.

**Acceptance Criteria:**
- ✅ `AutoMLEngine._get_candidate_models()` modified to use `AlgorithmSelector` if training_mode provided
- ✅ Backward compatibility: old behavior works if no training_mode
- ✅ Generate `DataProfile` from input DataFrame
- ✅ Filter candidates by training_mode (QUICK=3-5, BALANCED=5-7, COMPREHENSIVE=8-10)
- ✅ Pass algorithm recommendations to caller (stored in AutoMLResult.metadata)

**Dependencies:** Task BE-1.1.2

**Files to Modify:**
- `apps/backend/app/services/model_training/automl_engine.py`
- `apps/backend/app/services/model_training/__init__.py` (export new types)

**Estimated Time:** 3 hours

**Testing:**
- Modify `tests/test_model_training/test_automl_engine.py`
- Tests: training mode filtering, DataProfile generation, backward compatibility
- Target: 5+ new tests

---

### Phase 1.2: Parallel Training Infrastructure

#### Task BE-1.2.1: Implement Parallel Training with asyncio
**Description:** Enable concurrent model training with ProcessPoolExecutor.

**Acceptance Criteria:**
- ✅ `ParallelTrainingConfig` dataclass added with fields: max_parallel_jobs (default 4), use_multiprocessing (default True), timeout_per_model (default 600)
- ✅ `AutoMLEngine._train_models_parallel()` method implemented using:
  - `asyncio.gather()` for coordination
  - `concurrent.futures.ProcessPoolExecutor` for CPU-bound training
  - `asyncio.wait_for()` for timeouts
- ✅ `_train_single_model_async()` wrapper for sklearn training in executor
- ✅ Graceful degradation: If parallel fails, fall back to sequential training
- ✅ Memory monitoring: Log memory usage per model
- ✅ Stores intermediate results in Redis: `training:{job_id}:model:{algorithm}`

**Dependencies:** None (independent of Phase 1.1)

**Files to Modify:**
- `apps/backend/app/services/model_training/automl_engine.py`

**Estimated Time:** 8 hours

**Testing:**
- Modify `tests/test_model_training/test_automl_engine.py`
- Mock sklearn models to control timing
- Tests: parallel execution, timeout handling, fallback to sequential, Redis storage
- Target: 10+ new tests, >85% coverage for new code

---

#### Task BE-1.2.2: Implement Progress Callback Mechanism
**Description:** Add progress callbacks for real-time training updates.

**Acceptance Criteria:**
- ✅ `ProgressCallback` protocol/interface defined with methods:
  - `on_training_started(total_algorithms: int)`
  - `on_algorithm_started(algorithm: str, index: int)`
  - `on_cv_fold_completed(algorithm: str, fold: int, total_folds: int, score: float)`
  - `on_algorithm_completed(algorithm: str, result: ModelCandidate)`
  - `on_algorithm_failed(algorithm: str, error: Exception)`
  - `on_training_completed(best_model: ModelCandidate, all_models: List[ModelCandidate])`
- ✅ `AutoMLEngine.run()` accepts optional `progress_callback: ProgressCallback`
- ✅ Callbacks invoked at appropriate points in training loop
- ✅ Callbacks don't block training (run in separate thread or async)
- ✅ Exception in callback doesn't crash training (logged and ignored)

**Dependencies:** Task BE-1.2.1

**Files to Modify:**
- `apps/backend/app/services/model_training/automl_engine.py`

**Estimated Time:** 4 hours

**Testing:**
- Add tests to `tests/test_model_training/test_automl_engine.py`
- Mock callback to verify invocations
- Tests: callback called with correct args, exception handling, async safety
- Target: 6+ new tests

---

### Phase 1.3: Class Balancing & Time Series

#### Task BE-1.3.1: Add Class Balancing to FeatureEngineer
**Description:** Integrate imbalanced-learn for class balancing.

**Acceptance Criteria:**
- ✅ Add `imbalanced-learn>=0.11.0` to `apps/backend/pyproject.toml`
- ✅ Run `uv sync` to install
- ✅ `ClassBalancingConfig` dataclass in `feature_engineer.py` with fields: method (SMOTE/RANDOM_OVERSAMPLE/RANDOM_UNDERSAMPLE/SMOTE_TOMEK), sampling_strategy (auto or float), k_neighbors (default 5)
- ✅ `FeatureEngineer._balance_classes()` method:
  - Detects class imbalance (ratio >2:1)
  - Applies selected method
  - Returns balanced X, y
  - Logs balancing metadata (original counts, new counts)
- ✅ Integrated into `fit_transform()` before feature selection
- ✅ Balancing metadata stored in `FeatureEngineeringResult.metadata`
- ✅ Only applied for classification problems

**Dependencies:** None

**Files to Modify:**
- `apps/backend/pyproject.toml`
- `apps/backend/app/services/model_training/feature_engineer.py`

**Estimated Time:** 5 hours

**Testing:**
- Modify `tests/test_model_training/test_feature_engineer.py`
- Create imbalanced synthetic dataset
- Tests: SMOTE application, ratio detection, metadata storage, regression skip
- Target: 8+ new tests, >90% coverage

---

#### Task BE-1.3.2: Create Time Series Models Module
**Description:** Add ARIMA and Prophet wrappers for time series.

**Acceptance Criteria:**
- ✅ Add to `apps/backend/pyproject.toml`:
  - `statsmodels>=0.14.0`
  - `prophet>=1.1.0`
  - `pmdarima>=2.0.0` (for auto-ARIMA)
- ✅ Run `uv sync`
- ✅ File `apps/backend/app/services/model_training/time_series_models.py` created
- ✅ `ARIMAModel` wrapper class:
  - Scikit-learn compatible interface (fit, predict)
  - Uses `pmdarima.auto_arima` for hyperparameter search
  - Stores ARIMA order in metadata
- ✅ `ProphetModel` wrapper class:
  - Scikit-learn compatible interface
  - Automatic seasonality detection
  - Handles daily/weekly/yearly patterns
- ✅ `TimeSeriesPreprocessor` class:
  - Datetime feature extraction (hour, day, month, year)
  - Lag features (lag 1-7 for daily data)
  - Rolling statistics (mean, std for windows 7, 30)
- ✅ Time series cross-validation using `TimeSeriesSplit`
- ✅ Integration into `AutoMLEngine._get_candidate_models()` when problem_type is TIME_SERIES_*

**Dependencies:** None

**Files to Create:**
- `apps/backend/app/services/model_training/time_series_models.py`

**Files to Modify:**
- `apps/backend/pyproject.toml`
- `apps/backend/app/services/model_training/automl_engine.py` (add time series candidates)

**Estimated Time:** 10 hours

**Testing:**
- Create `tests/test_model_training/test_time_series_models.py`
- Use synthetic time series data
- Tests: ARIMA fit/predict, Prophet fit/predict, preprocessing, TimeSeriesSplit
- Target: 12+ tests, >85% coverage

---

### Phase 1.4: Training Modes & Model Comparison

#### Task BE-1.4.1: Implement Training Modes
**Description:** Add QUICK/BALANCED/COMPREHENSIVE training configurations.

**Acceptance Criteria:**
- ✅ `TrainingMode` enum added with values: QUICK, BALANCED, COMPREHENSIVE
- ✅ `OptimizeFor` enum added with values: ACCURACY, SPEED, INTERPRETABILITY
- ✅ Mode configurations in `AutoMLEngine`:
  - QUICK: 3-5 algorithms, no hyperparameter tuning, 3-fold CV, 10min timeout
  - BALANCED: 5-7 algorithms, basic GridSearchCV, 5-fold CV, 30min timeout
  - COMPREHENSIVE: 8-10 algorithms, extensive GridSearchCV, 10-fold CV, 2hr timeout
- ✅ `optimize_for` affects algorithm prioritization in `AlgorithmSelector`
- ✅ Basic hyperparameter tuning for COMPREHENSIVE mode using `GridSearchCV`
- ✅ Configuration stored in `AutoMLResult.metadata`

**Dependencies:** Task BE-1.1.3, Task BE-1.2.1

**Files to Modify:**
- `apps/backend/app/services/model_training/automl_engine.py`
- `apps/backend/app/services/model_training/algorithm_selector.py` (optimize_for logic)

**Estimated Time:** 6 hours

**Testing:**
- Modify `tests/test_model_training/test_automl_engine.py`
- Tests: mode configurations applied, algorithm count correct, CV folds correct, hyperparameter tuning in COMPREHENSIVE
- Target: 8+ new tests

---

#### Task BE-1.4.2: Implement Model Comparison
**Description:** Add model comparison with statistical significance and AI explanations.

**Acceptance Criteria:**
- ✅ `ModelComparison` dataclass with fields from API contract
- ✅ `AutoMLEngine.compare_models()` method:
  - Ranks models by primary metric (CV score)
  - Calculates secondary metrics: training_time, model_size, interpretability_score
  - Generates comparison matrix
  - Identifies best model considering trade-offs
  - Performs paired t-test on CV scores (statistical significance)
  - Calls `ExplanationService` for natural language comparison
- ✅ Returns `ModelComparison` object
- ✅ Integrated into `AutoMLEngine.run()` (returned in AutoMLResult)

**Dependencies:** Task BE-1.1.2 (ExplanationService)

**Files to Modify:**
- `apps/backend/app/services/model_training/automl_engine.py`

**Estimated Time:** 5 hours

**Testing:**
- Modify `tests/test_model_training/test_automl_engine.py`
- Mock models with known scores
- Tests: ranking correctness, t-test calculation, comparison generation
- Target: 6+ new tests

---

### Phase 1 Quality Gates

#### Task BE-1.QG: Phase 1 Quality Gate Validation
**Description:** Verify all Phase 1 acceptance criteria.

**Checklist:**
- ✅ All 45+ unit tests passing (run: `cd apps/backend && uv run pytest tests/test_model_training/ -v`)
- ✅ mypy checks passing (run: `uv run mypy app/services/model_training/`)
- ✅ ruff checks passing (run: `uv run ruff check app/services/model_training/`)
- ✅ Coverage >85% for new/modified code (run: `uv run pytest --cov=app/services/model_training --cov-report=term`)
- ✅ Manual test: Run AutoML with parallel training
  - Create test script `scripts/test_parallel_training.py`
  - Train 5 models in parallel
  - Verify progress callbacks called
  - Verify results stored in Redis
- ✅ Documentation: Create `apps/backend/docs/AUTOML_ENGINE.md`
  - Architecture diagram
  - Algorithm selection rules table
  - Training modes comparison table
  - Code examples

**Deliverable:** Phase 1 completion report in `.claude-flow/implementations/gh-75/PHASE_1_REPORT.md`

---

## Phase 2: Backend API & WebSocket (Backend Specialist)

**Goal:** Expose AutoML via REST API with real-time progress tracking.
**Estimated Time:** 40-50 hours (1-2 weeks)
**Model:** Claude Sonnet 4.5
**Prerequisites:** Phase 1 complete

### Phase 2.1: Training Job Management

#### Task BE-2.1.1: Create TrainingJob Model
**Description:** Implement persistent training job tracking.

**Acceptance Criteria:**
- ✅ File `apps/backend/app/models/training_job.py` created
- ✅ `TrainingJob` document extends `BatchJob` pattern
- ✅ Additional fields:
  - dataset_id, target_column, training_config (Dict)
  - algorithm_recommendations (List[Dict])
  - trained_models (List[str]) - model_ids
  - best_model_id (str)
  - comparison_results (Dict)
- ✅ `TrainingProgress` embedded document with fields from API contract
- ✅ Methods:
  - `update_algorithm_progress(algorithm, cv_fold, total_folds)`
  - `add_trained_model(model_id, algorithm, cv_score)`
  - `mark_best_model(model_id)`
- ✅ Indexes on: job_id, user_id, status, created_at

**Dependencies:** None

**Files to Create:**
- `apps/backend/app/models/training_job.py`

**Files to Modify:**
- `apps/backend/app/models/__init__.py` (export TrainingJob)

**Estimated Time:** 4 hours

**Testing:**
- Create `tests/test_models/test_training_job.py`
- Tests: job creation, progress updates, model tracking, status transitions
- Target: 8+ tests, >90% coverage

---

### Phase 2.2: WebSocket Infrastructure

#### Task BE-2.2.1: Create WebSocket Endpoint
**Description:** Implement WebSocket server for real-time progress.

**Acceptance Criteria:**
- ✅ File `apps/backend/app/api/websocket.py` created
- ✅ `ConnectionManager` class:
  - Manages active WebSocket connections per job_id
  - `connect(websocket, job_id, user_id)`
  - `disconnect(websocket, job_id)`
  - `broadcast_to_job(job_id, message: dict)`
  - Supports multiple clients per job_id
- ✅ WebSocket endpoint `/ws/training/{job_id}`:
  - FastAPI WebSocket route
  - JWT authentication from query param: `?token={jwt}`
  - Validates user access to job_id
  - Sends `connection_ack` on connect
  - Handles `ping`/`pong` messages
  - Handles `cancel_training` message
- ✅ Heartbeat mechanism: Send every 30 seconds
- ✅ Graceful disconnect on training completion

**Dependencies:** Task BE-2.1.1 (needs TrainingJob for validation)

**Files to Create:**
- `apps/backend/app/api/websocket.py`

**Files to Modify:**
- `apps/backend/app/main.py` (register WebSocket route)

**Estimated Time:** 6 hours

**Testing:**
- Create `tests/integration/test_websocket.py`
- Use FastAPI WebSocket test client
- Tests: connection, authentication, broadcast, disconnect, heartbeat
- Target: 10+ integration tests

---

#### Task BE-2.2.2: Create TrainingProgressService
**Description:** Bridge between Redis, WebSocket, and training callbacks.

**Acceptance Criteria:**
- ✅ File `apps/backend/app/services/training_progress_service.py` created
- ✅ `TrainingProgressService` class:
  - `update_progress(job_id, progress_data: dict)`:
    - Stores in Redis (`training_progress:{job_id}`, TTL 24 hours)
    - Broadcasts via WebSocket using ConnectionManager
    - Updates TrainingJob in MongoDB
  - `get_progress(job_id) -> dict`: Retrieves from Redis
  - Implements `ProgressCallback` interface from Phase 1
- ✅ Message formatting per WebSocket protocol (API contract)
- ✅ Handles partial updates (merge with existing progress)

**Dependencies:** Task BE-2.2.1, Phase 1 (ProgressCallback)

**Files to Create:**
- `apps/backend/app/services/training_progress_service.py`

**Estimated Time:** 5 hours

**Testing:**
- Add to `tests/integration/test_websocket.py`
- Tests: Redis storage, WebSocket broadcast, progress merging
- Target: 8+ tests

---

### Phase 2.3: Enhanced Training API

#### Task BE-2.3.1: Implement Detect Problem Type Endpoint
**Description:** Add POST /datasets/{id}/detect-problem-type.

**Acceptance Criteria:**
- ✅ Endpoint matches API contract exactly
- ✅ Loads dataset from S3 using UserData.s3_url
- ✅ Validates user access (JWT authentication)
- ✅ Calls existing `ProblemDetector.detect_problem_type()`
- ✅ Returns response matching contract schema
- ✅ Redis caching (key: `problem_detection:{dataset_id}:{target_column}`, TTL 1 hour)
- ✅ Error handling: 404 (dataset not found), 422 (invalid column)

**Dependencies:** None (uses existing ProblemDetector)

**Files to Modify:**
- `apps/backend/app/api/routes/model_training.py`

**Estimated Time:** 3 hours

**Testing:**
- Modify `tests/test_api/test_model_training.py` (or create if missing)
- Tests: successful detection, caching, invalid dataset, invalid column
- Target: 5+ integration tests

---

#### Task BE-2.3.2: Implement Recommend Algorithms Endpoint
**Description:** Add POST /datasets/{id}/recommend-algorithms.

**Acceptance Criteria:**
- ✅ Endpoint matches API contract exactly
- ✅ Generates `DataProfile` from dataset
- ✅ Calls `AlgorithmSelector.select_algorithms()`
- ✅ Calls `ExplanationService` for AI explanations
- ✅ Returns response matching contract schema
- ✅ Redis caching (key: `algorithm_recommendations:{dataset_id}:{hash(request)}`, TTL 1 hour)
- ✅ Request validation: training_mode, optimize_for enums
- ✅ Error handling: 404, 400 (invalid enums)

**Dependencies:** Phase 1 (AlgorithmSelector, ExplanationService)

**Files to Modify:**
- `apps/backend/app/api/routes/model_training.py`

**Estimated Time:** 4 hours

**Testing:**
- Modify `tests/test_api/test_model_training.py`
- Mock OpenAI calls
- Tests: successful recommendations, caching, mode filtering, invalid inputs
- Target: 6+ integration tests

---

#### Task BE-2.3.3: Implement Start AutoML Training Endpoint
**Description:** Add POST /datasets/{id}/train-automl.

**Acceptance Criteria:**
- ✅ Endpoint matches API contract exactly
- ✅ Creates `TrainingJob` with status PENDING
- ✅ Queues background task (FastAPI BackgroundTasks)
- ✅ Prevents concurrent training on same dataset (409 if exists)
- ✅ Returns 202 with job_id and websocket_url
- ✅ Validates selected_algorithms against available algorithms
- ✅ Stores configuration in TrainingJob for auditability
- ✅ Initializes Redis progress key

**Dependencies:** Task BE-2.1.1, Phase 1

**Files to Modify:**
- `apps/backend/app/api/routes/model_training.py`

**Estimated Time:** 5 hours

**Testing:**
- Modify `tests/test_api/test_model_training.py`
- Tests: job creation, concurrent prevention, validation, background task queued
- Target: 7+ integration tests

---

#### Task BE-2.3.4: Refactor train_model_task for Progress Tracking
**Description:** Update background training task to use TrainingJob and progress callbacks.

**Acceptance Criteria:**
- ✅ Fetches `TrainingJob` at start
- ✅ Creates `TrainingProgressService` instance
- ✅ Passes progress callbacks to `AutoMLEngine.run()`
- ✅ Updates TrainingJob status: PENDING → RUNNING → COMPLETED/FAILED
- ✅ Stores all trained models (not just best) in MongoDB
- ✅ Saves model comparison results in TrainingJob
- ✅ Calls `ExplanationService.explain_best_model()` after training
- ✅ Broadcasts final `training_completed` or `training_failed` message
- ✅ Error handling: logs errors, updates job status to FAILED

**Dependencies:** Task BE-2.2.2, Task BE-2.3.3

**Files to Modify:**
- `apps/backend/app/api/routes/model_training.py` (train_model_task function)

**Estimated Time:** 6 hours

**Testing:**
- Create `tests/integration/test_training_workflow.py`
- End-to-end test: start training → monitor progress → verify completion
- Tests: success flow, failure handling, progress updates, WebSocket messages
- Target: 8+ integration tests (requires MongoDB + Redis)

---

#### Task BE-2.3.5: Implement Get Training Job Status Endpoint
**Description:** Add GET /training-jobs/{id}/status.

**Acceptance Criteria:**
- ✅ Endpoint matches API contract exactly
- ✅ Fetches `TrainingJob` from MongoDB
- ✅ Validates user_id matches job owner
- ✅ Returns progress from Redis (falls back to MongoDB if Redis key expired)
- ✅ Returns response matching contract schema
- ✅ Error handling: 404 (job not found)

**Dependencies:** Task BE-2.1.1

**Files to Modify:**
- `apps/backend/app/api/routes/model_training.py`

**Estimated Time:** 2 hours

**Testing:**
- Modify `tests/test_api/test_model_training.py`
- Tests: job found, Redis priority, MongoDB fallback, access denied
- Target: 4+ tests

---

#### Task BE-2.3.6: Implement Get Training Job Results Endpoint
**Description:** Add GET /training-jobs/{id}/results.

**Acceptance Criteria:**
- ✅ Endpoint matches API contract exactly
- ✅ Only returns if status=COMPLETED (409 otherwise)
- ✅ Fetches all trained models from MongoDB (MLModel collection)
- ✅ Includes model comparison from TrainingJob
- ✅ Returns response matching contract schema
- ✅ Redis caching (key: `training_results:{job_id}`, TTL 24 hours)
- ✅ Error handling: 404 (job not found), 409 (not completed)

**Dependencies:** Task BE-2.1.1

**Files to Modify:**
- `apps/backend/app/api/routes/model_training.py`

**Estimated Time:** 3 hours

**Testing:**
- Modify `tests/test_api/test_model_training.py`
- Tests: completed job, caching, incomplete job (409), not found
- Target: 5+ tests

---

### Phase 2 Quality Gates

#### Task BE-2.QG: Phase 2 Quality Gate Validation
**Description:** Verify all Phase 2 acceptance criteria.

**Checklist:**
- ✅ All 30+ API/integration tests passing (run: `cd apps/backend && uv run pytest tests/test_api/ tests/integration/ -v`)
- ✅ Total backend tests: 214 baseline + 75 new = 289 tests at 100% pass rate
- ✅ Coverage >85% overall backend (run: `uv run pytest --cov=app --cov-report=html`)
- ✅ mypy checks passing (run: `uv run mypy app/`)
- ✅ ruff checks passing (run: `uv run ruff check app/`)
- ✅ Manual WebSocket test:
  - Create test script `scripts/test_websocket_training.py`
  - Start training via API
  - Connect WebSocket
  - Verify messages received in correct order
  - Verify heartbeat every 30 seconds
  - Verify training_completed message
- ✅ API documentation: Update OpenAPI spec (auto-generated from FastAPI)
- ✅ Contract validation: API responses match `API_CONTRACTS.md` exactly

**Deliverable:** Phase 2 completion report in `.claude-flow/implementations/gh-75/PHASE_2_REPORT.md`

---

## Phase 3: Frontend Training Interface (Frontend Specialist)

**Goal:** Build comprehensive training UI with real-time progress.
**Estimated Time:** 50-60 hours (2-3 weeks)
**Model:** Claude Sonnet 4.5
**Prerequisites:** Phase 2 complete (or API contracts locked)

**Note:** Can start after Week 3 using API contracts and mock data.

### Phase 3.1: Service Layer & WebSocket Hook

#### Task FE-3.1.1: Enhance Model Service
**Description:** Add API client methods for training endpoints.

**Acceptance Criteria:**
- ✅ File `apps/frontend/lib/services/model.ts` modified
- ✅ New methods (TypeScript, type-safe):
  - `detectProblemType(datasetId, request, token): Promise<ProblemDetectionResult>`
  - `recommendAlgorithms(datasetId, request, token): Promise<AlgorithmRecommendationsResponse>`
  - `startAutoMLTraining(datasetId, request, token): Promise<TrainingJobResponse>`
  - `getTrainingJobStatus(jobId, token): Promise<TrainingJobStatusResponse>`
  - `getTrainingJobResults(jobId, token): Promise<TrainingResultsResponse>`
  - `cancelTrainingJob(jobId, token): Promise<void>`
- ✅ Error handling: HTTP status codes mapped to user-friendly errors
- ✅ Request/response types match API contracts
- ✅ Base URL from environment variable

**Dependencies:** None (uses API contracts)

**Files to Modify:**
- `apps/frontend/lib/services/model.ts`

**Files to Create:**
- `apps/frontend/lib/types/training.ts` (TypeScript types from API contract)

**Estimated Time:** 4 hours

**Testing:**
- Create `apps/frontend/__tests__/services/model.test.ts`
- Mock fetch API
- Tests: successful requests, error handling, type validation
- Target: 8+ unit tests

---

#### Task FE-3.1.2: Create useTrainingProgress Hook
**Description:** Custom React hook for WebSocket connection.

**Acceptance Criteria:**
- ✅ File `apps/frontend/hooks/useTrainingProgress.ts` created
- ✅ Hook signature: `useTrainingProgress(jobId: string, token: string) => { progress, isConnected, error, connect, disconnect }`
- ✅ Establishes WebSocket connection to `/ws/training/{jobId}?token={token}`
- ✅ Parses WebSocket messages (type safety with discriminated union)
- ✅ Updates React state on each message
- ✅ Reconnection logic: Exponential backoff (1s, 2s, 4s, 8s, max 16s)
- ✅ Auto-disconnect on training_completed or training_failed
- ✅ Cleanup on unmount
- ✅ Handles connection errors gracefully (falls back to polling)

**Dependencies:** None

**Files to Create:**
- `apps/frontend/hooks/useTrainingProgress.ts`

**Estimated Time:** 6 hours

**Testing:**
- Create `apps/frontend/__tests__/hooks/useTrainingProgress.test.ts`
- Mock WebSocket
- Tests: connection, message parsing, reconnection, cleanup
- Target: 10+ unit tests

---

### Phase 3.2: Training Page Structure

#### Task FE-3.2.1: Create Training Page Component
**Description:** Main training page with workflow state machine.

**Acceptance Criteria:**
- ✅ File `apps/frontend/app/datasets/[id]/train/page.tsx` created
- ✅ Workflow states: CONFIGURE | DETECTING | RECOMMENDING | TRAINING | COMPLETED
- ✅ React state management (useState for states, useEffect for data loading)
- ✅ Fetches dataset metadata on mount
- ✅ Renders appropriate component per state:
  - CONFIGURE: ProblemTypeDetector + AlgorithmSelector + TrainingConfig
  - DETECTING: Loading spinner + "Analyzing target column..."
  - RECOMMENDING: Loading spinner + "Generating algorithm recommendations..."
  - TRAINING: TrainingProgress
  - COMPLETED: ModelComparison + BestModelCard
- ✅ Navigation: Stepper/breadcrumb showing current step
- ✅ Error boundary for graceful error handling
- ✅ Back navigation warning if training in progress

**Dependencies:** None

**Files to Create:**
- `apps/frontend/app/datasets/[id]/train/page.tsx`

**Files to Modify:**
- `apps/frontend/app/datasets/[id]/page.tsx` (add "Train Model" button linking to /train)

**Estimated Time:** 5 hours

**Testing:**
- Create `apps/frontend/__tests__/app/train/page.test.tsx`
- Tests: state transitions, component rendering, error boundary
- Target: 6+ tests

---

### Phase 3.3: Configuration Components (Steps 1-3)

#### Task FE-3.3.1: Create ProblemTypeDetector Component
**Description:** Target column selector and problem type detection UI.

**Acceptance Criteria:**
- ✅ File `apps/frontend/components/training/ProblemTypeDetector.tsx` created
- ✅ UI elements:
  - Dropdown/select for target column (from dataset metadata)
  - "Detect Problem Type" button
  - Detected problem type badge with confidence (color-coded: green >0.8, yellow 0.6-0.8, red <0.6)
  - Expandable card with AI reasoning
  - Recommendation chips (e.g., "Consider log transformation")
  - Manual override selector (if confidence <0.8)
- ✅ Calls `api.detectProblemType()` on button click
- ✅ Loading state during detection
- ✅ Error handling with toast notification
- ✅ "Continue" button (emits event to parent with problem_type)

**Dependencies:** Task FE-3.1.1

**Files to Create:**
- `apps/frontend/components/training/ProblemTypeDetector.tsx`

**Design:** Nova theme, gray palette, Hugeicons (use `@hugeicons/react`)

**Estimated Time:** 6 hours

**Testing:**
- Create `apps/frontend/__tests__/components/training/ProblemTypeDetector.test.tsx`
- Mock API calls
- Tests: column selection, detection flow, confidence display, manual override
- Target: 7+ tests

---

#### Task FE-3.3.2: Create AlgorithmSelector Component
**Description:** Algorithm recommendation and selection UI.

**Acceptance Criteria:**
- ✅ File `apps/frontend/components/training/AlgorithmSelector.tsx` created
- ✅ UI elements:
  - Training mode selector: Radio buttons (Quick/Balanced/Comprehensive) with descriptions
  - Optimize_for selector: Radio buttons (Accuracy/Speed/Interpretability)
  - Class balancing toggle + method selector (if classification)
  - Algorithm cards grid:
    - Algorithm name + icon (Hugeicons)
    - Priority badge (High/Medium/Low based on priority 1-10)
    - Expected performance range (progress bar or range display)
    - Training time estimate
    - Interpretability score (star rating 1-10)
    - Pros/cons lists (expandable)
    - AI explanation (expandable section)
    - Checkbox to select/deselect
  - Footer: Selected count, estimated total time
- ✅ Calls `api.recommendAlgorithms()` when mode/optimize_for changes
- ✅ Loading skeleton during recommendation fetch
- ✅ Default: All algorithms selected
- ✅ "Continue" button (emits selected algorithms to parent)

**Dependencies:** Task FE-3.1.1

**Files to Create:**
- `apps/frontend/components/training/AlgorithmSelector.tsx`

**Design:** Card grid, responsive (1 col mobile, 2 col tablet, 3 col desktop)

**Estimated Time:** 8 hours

**Testing:**
- Create `apps/frontend/__tests__/components/training/AlgorithmSelector.test.tsx`
- Tests: mode selection, algorithm filtering, selection/deselection, time calculation
- Target: 8+ tests

---

#### Task FE-3.3.3: Create TrainingConfig Component
**Description:** Advanced training configuration UI.

**Acceptance Criteria:**
- ✅ File `apps/frontend/components/training/TrainingConfig.tsx` created
- ✅ UI elements:
  - Model name input (optional, placeholder auto-generated)
  - Model description textarea (optional)
  - Advanced options (collapsible):
    - CV folds slider (3-10, default 5)
    - Test size slider (0.1-0.4, default 0.2)
    - Random seed input (default 42)
    - Max parallel jobs slider (1-8, default 4)
    - Timeout per model slider (60-3600s, default 600)
  - Feature engineering toggles (from existing ModelTrainingButton.tsx):
    - Enable feature engineering
    - Enable feature selection
    - Max features input
    - Scaling method dropdown
  - Configuration summary card (read-only preview)
  - "Start Training" button (emits full config to parent)
- ✅ Form validation: Required fields, numeric ranges
- ✅ Default values from API contract

**Dependencies:** None

**Files to Create:**
- `apps/frontend/components/training/TrainingConfig.tsx`

**Estimated Time:** 6 hours

**Testing:**
- Create `apps/frontend/__tests__/components/training/TrainingConfig.test.tsx`
- Tests: form validation, default values, config preview
- Target: 6+ tests

---

### Phase 3.4: Progress & Results Components (Steps 4-5)

#### Task FE-3.4.1: Create TrainingProgress Component
**Description:** Real-time training progress display with WebSocket.

**Acceptance Criteria:**
- ✅ File `apps/frontend/components/training/TrainingProgress.tsx` created
- ✅ Uses `useTrainingProgress` hook
- ✅ UI elements:
  - Overall progress bar (0-100% with percentage text)
  - Algorithm list with status badges:
    - PENDING: gray badge
    - TRAINING: blue badge + pulsing animation
    - COMPLETED: green badge + checkmark icon
    - FAILED: red badge + error icon
  - Currently training algorithm card:
    - Algorithm name + icon
    - CV fold progress: "Fold 3/5"
    - Individual fold scores (mini chart)
    - Elapsed time + estimated remaining time
  - Completed algorithms list:
    - Algorithm name + CV score + test score
    - Expandable: Training time, hyperparameters
  - Training logs: Scrollable terminal-style component (recent 50 messages)
  - Cancel training button (with confirmation dialog)
- ✅ WebSocket fallback: If connection fails, fall back to polling (5s interval)
- ✅ Auto-scroll logs to bottom
- ✅ Handles all WebSocket message types from contract

**Dependencies:** Task FE-3.1.2

**Files to Create:**
- `apps/frontend/components/training/TrainingProgress.tsx`

**Design:** Terminal theme for logs (monospace font, dark background)

**Estimated Time:** 10 hours

**Testing:**
- Create `apps/frontend/__tests__/components/training/TrainingProgress.test.tsx`
- Mock WebSocket messages
- Tests: progress updates, status badges, log display, cancellation
- Target: 10+ tests

---

#### Task FE-3.4.2: Create ModelComparison Component
**Description:** Comprehensive model comparison table and visualizations.

**Acceptance Criteria:**
- ✅ File `apps/frontend/components/training/ModelComparison.tsx` created
- ✅ UI elements:
  - Comparison table (sortable columns):
    - Algorithm (with icon)
    - CV Score (sortable, default sort)
    - Test Score
    - Training Time (human-readable: "45s", "2m 15s")
    - Model Size (human-readable: "1.0 MB")
    - Interpretability (star rating)
    - Rank badge (1st = gold, 2nd = silver, 3rd = bronze)
  - Best model row: Gold background highlight
  - Visualizations (Recharts library):
    - Bar chart: CV scores comparison
    - Scatter plot: Accuracy vs Training Time (Pareto frontier)
    - Radar chart: Multi-metric comparison (top 3 models)
  - AI-generated comparison explanation card
  - Statistical significance table (expandable)
  - "View Details" button per model → Modal with:
    - Full metrics table
    - Feature importance chart (bar chart, top 20 features)
    - Confusion matrix (classification) or residual plot (regression)
    - Hyperparameters JSON viewer
- ✅ Responsive: Table scrolls horizontally on mobile
- ✅ Accessibility: ARIA labels, keyboard navigation

**Dependencies:** None (receives data from parent)

**Files to Create:**
- `apps/frontend/components/training/ModelComparison.tsx`

**Design:** Nova theme, use shadcn/ui Table component

**Estimated Time:** 10 hours

**Testing:**
- Create `apps/frontend/__tests__/components/training/ModelComparison.test.tsx`
- Tests: table rendering, sorting, modal, chart data
- Target: 8+ tests

---

#### Task FE-3.4.3: Create BestModelCard Component
**Description:** Prominent display of best model with actions.

**Acceptance Criteria:**
- ✅ File `apps/frontend/components/training/BestModelCard.tsx` created
- ✅ UI elements:
  - Large card with trophy icon (Hugeicons)
  - Algorithm name (large heading)
  - Key metrics (large numbers with labels):
    - CV Score
    - Test Score
    - Training Time
  - AI explanation: "Why this model was chosen" (expandable)
  - Trade-off analysis vs second-best model (expandable)
  - Action buttons:
    - "Deploy Model" (primary button) → Navigates to deployment page
    - "View Details" (secondary) → Opens same modal as ModelComparison
    - "Download Model" (tertiary) → Downloads .pkl file
  - Model metadata footer:
    - Training date
    - Dataset info (name, rows)
    - Feature count
- ✅ Gradient background (gold accent)
- ✅ Celebrate animation on mount (confetti or subtle pulse)

**Dependencies:** None

**Files to Create:**
- `apps/frontend/components/training/BestModelCard.tsx`

**Design:** Hero card, visually distinct from ModelComparison

**Estimated Time:** 5 hours

**Testing:**
- Create `apps/frontend/__tests__/components/training/BestModelCard.test.tsx`
- Tests: rendering, action buttons, navigation
- Target: 5+ tests

---

### Phase 3 Quality Gates

#### Task FE-3.QG: Phase 3 Quality Gate Validation
**Description:** Verify all Phase 3 acceptance criteria.

**Checklist:**
- ✅ All 35+ frontend Jest tests passing (run: `cd apps/frontend && npm test`)
- ✅ TypeScript compilation passes (run: `npm run type-check` or `tsc --noEmit`)
- ✅ eslint checks passing (run: `npm run lint`)
- ✅ Component tests cover user interactions, state management
- ✅ Manual workflow test (with mock backend or real API):
  - Navigate to /datasets/{id}/train
  - Complete full workflow: Configure → Detect → Recommend → Train → Compare
  - Verify WebSocket updates in real-time
  - Verify UI responsiveness on mobile/tablet/desktop
- ✅ Visual QA:
  - Nova theme consistency (gray palette, not zinc)
  - Hugeicons used (not Lucide)
  - Nunito Sans font
  - Responsive design (test on 3 screen sizes)
- ✅ Accessibility check:
  - Keyboard navigation works (Tab through all interactive elements)
  - ARIA labels present on custom components
  - Screen reader test (basic: heading hierarchy, button labels)
- ✅ Integration with backend: Connect to real API (Phase 2 complete), verify no type mismatches

**Deliverable:** Phase 3 completion report in `.claude-flow/implementations/gh-75/PHASE_3_REPORT.md`

---

## Phase 4: Testing & Documentation (Test Engineer)

**Goal:** Comprehensive E2E testing, documentation, deployment readiness.
**Estimated Time:** 20-30 hours (1 week)
**Model:** Claude Haiku (cost-effective)
**Prerequisites:** Phases 1-3 complete

### Phase 4.1: Backend Test Hardening

#### Task TEST-4.1.1: Add Edge Case Backend Tests
**Description:** Cover error scenarios and edge cases.

**Acceptance Criteria:**
- ✅ Tests added to `tests/integration/test_training_workflow.py`:
  - OpenAI API failure (mock timeout, rate limit) → Falls back to rule-based
  - S3 failure during dataset load → Returns 503
  - MongoDB timeout during job creation → Retries, then fails gracefully
  - Redis unavailable → Falls back to MongoDB for progress
  - Concurrent training jobs on same dataset → Returns 409
  - Training cancellation mid-training → Job status = CANCELLED, cleanup
  - Model training timeout → Skips model, continues with others
  - All models fail → Training job status = FAILED, error message clear
- ✅ Resource contention test:
  - Start 3 training jobs simultaneously
  - Verify max_parallel_jobs respected
  - Verify no memory exhaustion (monitor memory during test)
- ✅ All tests passing

**Dependencies:** None

**Estimated Time:** 8 hours

**Testing:**
- Target: 10+ additional integration tests
- Run full backend suite: 289 + 10 = 299 tests at 100% pass rate

---

### Phase 4.2: E2E Testing

#### Task TEST-4.2.1: Create E2E Training Workflow Test
**Description:** Playwright test for complete training workflow.

**Acceptance Criteria:**
- ✅ File `apps/frontend/e2e/workflows/train.spec.ts` created
- ✅ Test: Happy path
  - Upload dataset (CSV with target column)
  - Navigate to /datasets/{id}/train
  - Select target column → Detect problem type → Verify badge shown
  - Select training mode (BALANCED) → Verify algorithms recommended
  - Deselect one algorithm → Verify count updates
  - Configure training → Click "Start Training"
  - Wait for WebSocket messages → Verify progress bar updates
  - Wait for completion → Verify ModelComparison table rendered
  - Verify best model card shows correct algorithm
  - Click "View Details" → Verify modal opens with charts
- ✅ Test: WebSocket reconnection
  - Start training
  - Close WebSocket connection mid-training (simulate network failure)
  - Verify UI falls back to polling
  - Verify progress still updates
  - Verify completion detected
- ✅ Test: Training cancellation
  - Start training
  - Click "Cancel Training" → Confirm dialog
  - Verify WebSocket receives `training_cancelled` message
  - Verify job status = CANCELLED in UI
- ✅ Test: Error handling
  - Start training with invalid dataset (e.g., all null values)
  - Verify error message displayed in UI
  - Verify job status = FAILED
- ✅ Test: Concurrent user sessions (optional)
  - Open two browser contexts with different users
  - Verify each user sees only their own training jobs

**Dependencies:** Phase 3 complete

**Estimated Time:** 10 hours

**Testing:**
- Target: 5+ E2E scenarios
- Run: `npm run test:e2e` (Playwright)
- All scenarios green on clean environment

---

### Phase 4.3: Documentation & Knowledge Transfer

#### Task DOC-4.3.1: Create AUTOML_ENGINE.md
**Description:** Comprehensive AutoML architecture documentation.

**Acceptance Criteria:**
- ✅ File `apps/backend/docs/AUTOML_ENGINE.md` created
- ✅ Sections:
  - **Overview:** High-level architecture diagram (Mermaid)
  - **Components:**
    - AutoMLEngine: Entry point, orchestrates training
    - AlgorithmSelector: Rule-based selection + AI explanations
    - ExplanationService: OpenAI integration
    - FeatureEngineer: Preprocessing + class balancing
    - Time Series Models: ARIMA, Prophet wrappers
    - TrainingProgressService: Redis + WebSocket bridge
  - **Algorithm Selection Rules:** Table with conditions and actions
  - **Training Modes:** Comparison table (QUICK/BALANCED/COMPREHENSIVE)
  - **Parallel Training:** Process pool architecture, memory management
  - **WebSocket Protocol:** Message types, flow diagram
  - **Code Examples:**
    - Basic usage: Run AutoML on dataset
    - With progress callbacks
    - Custom algorithm selection
  - **Troubleshooting:**
    - OpenAI API failures
    - Memory issues during parallel training
    - WebSocket connection drops
  - **Performance Tuning:** max_parallel_jobs, timeout_per_model recommendations

**Dependencies:** None

**Estimated Time:** 6 hours

**Validation:**
- Review by Backend Specialist
- New developer can understand architecture in <30 min (timed test)

---

#### Task DOC-4.3.2: Update README.md
**Description:** Add Stage 5: Model Training documentation.

**Acceptance Criteria:**
- ✅ File `README.md` modified
- ✅ New section: **Stage 5: Model Training**
  - Overview of AI-guided AutoML
  - Training modes explanation
  - API endpoint list with brief descriptions
  - Link to AUTOML_ENGINE.md for details
- ✅ Training workflow example (cURL or Python)
- ✅ Troubleshooting section:
  - "Training job stuck at 50%" → Check Redis, WebSocket connection
  - "Out of memory error" → Reduce max_parallel_jobs
  - "All models failed" → Check dataset quality, target column

**Dependencies:** Task DOC-4.3.1

**Estimated Time:** 2 hours

---

#### Task DOC-4.3.3: Update CLAUDE.md
**Description:** Synchronize project instructions with implementation.

**Acceptance Criteria:**
- ✅ File `CLAUDE.md` modified
- ✅ **Current Stage:** Update to "Sprint 12 Complete (GH-75), Sprint 13 Ready"
- ✅ **Testing Commands:** Add:
  - `cd apps/backend && uv run pytest tests/integration/test_training_workflow.py -v` (training workflow)
  - `cd apps/frontend && npm run test:e2e -- train.spec.ts` (E2E training)
- ✅ **Architecture Components:** Add:
  - Training API: 5 endpoints for AutoML workflow
  - WebSocket: Real-time progress tracking
  - Time Series: ARIMA, Prophet support
- ✅ **Test Suite Status:** Update counts:
  - Backend: 299 tests (was 214)
  - Frontend: 55+ tests (was ~20)
  - E2E: 5+ scenarios (was 0)

**Dependencies:** Task DOC-4.3.2

**Estimated Time:** 1 hour

---

#### Task DOC-4.3.4: Update SPRINTS.md
**Description:** Document Sprint 12 completion.

**Acceptance Criteria:**
- ✅ File `apps/backend/docs/SPRINTS.md` modified
- ✅ New section: **Sprint 12: AI-Guided AutoML Training Interface (GH-75)**
  - Dates: 2025-12-26 to [completion date]
  - Goals: List from Integration Plan
  - Achievements:
    - 5 new API endpoints
    - WebSocket real-time progress
    - Parallel training infrastructure
    - 7 new frontend components
    - 85+ new tests
  - Metrics:
    - Test coverage: Backend >85%, Frontend >80%
    - Total tests: 359+ (299 backend, 55 frontend, 5 E2E)
  - Lessons Learned:
    - WebSocket reconnection complexity
    - OpenAI caching reduces costs by 70%
    - Parallel training memory management critical
  - Next Sprint: Model Deployment & Monitoring (tentative)

**Dependencies:** None

**Estimated Time:** 1 hour

---

### Phase 4 Quality Gates

#### Task TEST-4.QG: Final Integration Validation
**Description:** Comprehensive system validation.

**Checklist:**
- ✅ All tests passing:
  - Backend: 299 tests (100% pass rate)
  - Frontend: 55+ tests (100% pass rate)
  - E2E: 5+ scenarios (100% pass rate)
  - **Total: 359+ tests**
- ✅ Coverage verification:
  - Backend: >85% (run: `cd apps/backend && uv run pytest --cov=app --cov-report=html`)
  - Frontend: >80% (run: `cd apps/frontend && npm run test:coverage`)
- ✅ All quality gates passing:
  - mypy: 0 errors
  - ruff: 0 errors
  - eslint: 0 errors
  - tsc: 0 errors
- ✅ E2E tests green on clean environment:
  - Fresh MongoDB instance
  - Fresh Redis instance
  - No cached data
  - Run full E2E suite: `npm run test:e2e`
- ✅ Documentation validated:
  - README.md: Links work, examples tested
  - AUTOML_ENGINE.md: Code examples run successfully
  - CLAUDE.md: Synchronized with implementation
  - SPRINTS.md: Sprint 12 documented
- ✅ Performance validation:
  - Training 5 models on 10k rows: <5 minutes (QUICK mode)
  - WebSocket message latency: <500ms
  - API response time (recommend-algorithms): <3s
- ✅ Security validation:
  - JWT authentication on all endpoints
  - User access control: Cannot access other users' jobs
  - WebSocket authentication validated
- ✅ Accessibility validation:
  - Keyboard navigation: All interactive elements reachable
  - Screen reader: Headings, buttons labeled correctly
  - WCAG 2.1 AA: Contrast ratios pass (use axe DevTools)

**Deliverable:** Final integration report in `.claude-flow/implementations/gh-75/FINAL_REPORT.md`

---

## Coordination Checkpoints

### Checkpoint 1: API Contracts Locked (End of Week 3)
**Participants:** Integration Coordinator, Backend Specialist
**Agenda:**
- Validate Phase 1 complete (all quality gates passed)
- Review `API_CONTRACTS.md` against implementation
- Lock contracts (no changes without formal process)
- Green-light Frontend Specialist to begin Phase 3

**Deliverables:**
- `API_CONTRACTS.md` version 1.0 LOCKED
- Phase 1 completion report approved

---

### Checkpoint 2: Backend-Frontend Integration (End of Week 5)
**Participants:** Integration Coordinator, Backend Specialist, Frontend Specialist
**Agenda:**
- Validate Phase 2 complete (API functional)
- Test API endpoints with Postman/cURL
- Validate WebSocket protocol
- Frontend switches from mocks to real API
- Joint integration test session

**Deliverables:**
- Integration test results document
- List of any API contract deviations (should be zero)
- Phase 2 completion report approved

---

### Checkpoint 3: Pre-Production Validation (End of Week 8)
**Participants:** Integration Coordinator, All Specialists
**Agenda:**
- Validate Phase 3 complete (UI functional)
- E2E testing session (all participants)
- Documentation review
- Performance testing results
- Go/No-Go decision for Phase 4

**Deliverables:**
- E2E test results
- Performance metrics report
- Phase 3 completion report approved

---

### Checkpoint 4: Final Review (End of Week 9)
**Participants:** Integration Coordinator, All Specialists, Stakeholders
**Agenda:**
- Validate Phase 4 complete (all tests green)
- Documentation walkthrough
- Demo: Complete training workflow
- Deployment plan review
- Retrospective: Lessons learned

**Deliverables:**
- Final integration report
- Deployment checklist
- Sprint 12 retrospective notes

---

## Daily Progress Tracking Template

Each specialist updates `.claude-flow/implementations/gh-75/DAILY_LOG.md`:

```markdown
## [Date] - [Specialist Name]

### Completed
- [x] Task BE-1.1.1: Created AlgorithmSelector service (6h)
- [x] Task BE-1.1.2: Created ExplanationService (5h)

### In Progress
- [ ] Task BE-1.1.3: Integrating AlgorithmSelector with AutoMLEngine (2h remaining)

### Blockers
- None

### Tests Added
- 10 unit tests for AlgorithmSelector (all passing)
- 8 unit tests for ExplanationService (all passing)

### Notes
- OpenAI caching working well, reduces duplicate calls by 70%
- Need to clarify expected behavior when confidence <0.5 (asked Integration Coordinator)

### Tomorrow's Plan
- Complete Task BE-1.1.3
- Begin Task BE-1.2.1 (Parallel Training)
```

---

## Task Ownership Summary

| Phase | Tasks | Specialist | Model | Estimated Hours |
|-------|-------|------------|-------|-----------------|
| 1 | BE-1.1.1 to BE-1.4.2 + QG | Backend Specialist | Sonnet 4.5 | 60-80 |
| 2 | BE-2.1.1 to BE-2.3.6 + QG | Backend Specialist | Sonnet 4.5 | 40-50 |
| 3 | FE-3.1.1 to FE-3.4.3 + QG | Frontend Specialist | Sonnet 4.5 | 50-60 |
| 4 | TEST-4.1.1 to DOC-4.3.4 + QG | Test Engineer | Haiku | 20-30 |
| **Total** | **47 tasks** | **3 specialists** | | **170-220 hours** |

**Timeline:** 6-9 weeks (as planned)

---

## Appendix: File Manifest

### New Files (Backend)
1. `apps/backend/app/services/model_training/algorithm_selector.py`
2. `apps/backend/app/services/model_training/explanation_service.py`
3. `apps/backend/app/services/model_training/time_series_models.py`
4. `apps/backend/app/models/training_job.py`
5. `apps/backend/app/api/websocket.py`
6. `apps/backend/app/services/training_progress_service.py`
7. `apps/backend/tests/test_model_training/test_algorithm_selector.py`
8. `apps/backend/tests/test_model_training/test_time_series_models.py`
9. `apps/backend/tests/test_models/test_training_job.py`
10. `apps/backend/tests/integration/test_training_workflow.py`
11. `apps/backend/tests/integration/test_websocket.py`
12. `apps/backend/docs/AUTOML_ENGINE.md`

### Modified Files (Backend)
1. `apps/backend/app/services/model_training/automl_engine.py`
2. `apps/backend/app/services/model_training/feature_engineer.py`
3. `apps/backend/app/api/routes/model_training.py`
4. `apps/backend/app/main.py` (WebSocket route registration)
5. `apps/backend/pyproject.toml` (dependencies)
6. `apps/backend/tests/test_model_training/test_automl_engine.py`
7. `apps/backend/tests/test_model_training/test_feature_engineer.py`

### New Files (Frontend)
1. `apps/frontend/lib/types/training.ts`
2. `apps/frontend/hooks/useTrainingProgress.ts`
3. `apps/frontend/app/datasets/[id]/train/page.tsx`
4. `apps/frontend/components/training/ProblemTypeDetector.tsx`
5. `apps/frontend/components/training/AlgorithmSelector.tsx`
6. `apps/frontend/components/training/TrainingConfig.tsx`
7. `apps/frontend/components/training/TrainingProgress.tsx`
8. `apps/frontend/components/training/ModelComparison.tsx`
9. `apps/frontend/components/training/BestModelCard.tsx`
10. `apps/frontend/__tests__/services/model.test.ts`
11. `apps/frontend/__tests__/hooks/useTrainingProgress.test.ts`
12. `apps/frontend/__tests__/app/train/page.test.tsx`
13. `apps/frontend/__tests__/components/training/*.test.tsx` (7 files)
14. `apps/frontend/e2e/workflows/train.spec.ts`

### Modified Files (Frontend)
1. `apps/frontend/lib/services/model.ts`
2. `apps/frontend/app/datasets/[id]/page.tsx` (add train link)

### Documentation
1. `README.md` (Stage 5 section)
2. `CLAUDE.md` (current stage, testing commands)
3. `apps/backend/docs/SPRINTS.md` (Sprint 12 completion)

**Total Files:**
- New: 33
- Modified: 10
- **Total: 43 files**

---

**Document Status:** READY FOR SPECIALIST ASSIGNMENT
**Next Action:** Integration Coordinator spawns Backend Specialist with Phase 1 tasks
**Last Updated:** 2025-12-26
