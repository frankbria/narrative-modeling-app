# API Contracts: AI-Guided AutoML Training Interface
## GitHub Issue #75

**Version:** 1.0
**Created:** 2025-12-26
**Status:** LOCKED - Do not modify without Integration Coordinator approval

---

## Contract Overview

This document defines the complete API interface between frontend and backend for the AI-Guided AutoML Training Interface. All endpoints use JWT authentication via `Authorization: Bearer <token>` header.

**Base URL:** `http://localhost:8000/api/v1/ml` (development)
**API Version:** v1
**Authentication:** NextAuth JWT tokens

---

## Endpoint 1: Detect Problem Type

### Metadata
- **Method:** POST
- **Path:** `/datasets/{dataset_id}/detect-problem-type`
- **Purpose:** Analyze target column and recommend problem type (classification vs regression)
- **Phase:** 2 (Backend API)
- **Frontend Usage:** ProblemTypeDetector.tsx

### Request

**Path Parameters:**
```typescript
{
  dataset_id: string  // MongoDB ObjectId or custom dataset ID
}
```

**Body Schema:**
```typescript
{
  target_column: string  // Column name to analyze
}
```

**Example:**
```json
POST /api/v1/ml/datasets/dataset_20251226_143022/detect-problem-type
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

{
  "target_column": "price"
}
```

### Response

**Success (200):**
```typescript
{
  problem_type: "REGRESSION" | "BINARY_CLASSIFICATION" | "MULTICLASS_CLASSIFICATION" | "TIME_SERIES_FORECASTING" | "TIME_SERIES_CLASSIFICATION",
  confidence: number,  // 0.0 to 1.0
  reasoning: string,   // Human-readable explanation
  metadata: {
    unique_values: number,
    data_type: string,
    sample_values: any[],
    null_percentage: number,
    recommendations: string[]  // e.g., ["Consider log transformation", "High class imbalance detected"]
  }
}
```

**Example:**
```json
{
  "problem_type": "REGRESSION",
  "confidence": 0.95,
  "reasoning": "Target column 'price' has 1,247 unique numeric values with continuous distribution, indicating a regression problem.",
  "metadata": {
    "unique_values": 1247,
    "data_type": "float64",
    "sample_values": [125000.0, 235000.0, 189000.0, 312000.0, 156000.0],
    "null_percentage": 0.02,
    "recommendations": [
      "Consider log transformation due to skewed distribution",
      "Remove outliers beyond 3 standard deviations"
    ]
  }
}
```

**Error (404):**
```json
{
  "detail": "Dataset not found or access denied"
}
```

**Error (422):**
```json
{
  "detail": "Column 'invalid_col' not found in dataset"
}
```

### Implementation Notes
- Uses existing `ProblemDetector.detect_problem_type()` method
- Loads dataset from S3 using `UserData.s3_url`
- Caches result in Redis for 1 hour (key: `problem_detection:{dataset_id}:{target_column}`)
- Validates user access to dataset before processing

---

## Endpoint 2: Recommend Algorithms

### Metadata
- **Method:** POST
- **Path:** `/datasets/{dataset_id}/recommend-algorithms`
- **Purpose:** Get ranked algorithm recommendations with AI explanations
- **Phase:** 2 (Backend API)
- **Frontend Usage:** AlgorithmSelector.tsx

### Request

**Path Parameters:**
```typescript
{
  dataset_id: string
}
```

**Body Schema:**
```typescript
{
  problem_type: "REGRESSION" | "BINARY_CLASSIFICATION" | "MULTICLASS_CLASSIFICATION" | "TIME_SERIES_FORECASTING" | "TIME_SERIES_CLASSIFICATION",
  target_column: string,
  training_mode?: "QUICK" | "BALANCED" | "COMPREHENSIVE",  // Default: BALANCED
  optimize_for?: "ACCURACY" | "SPEED" | "INTERPRETABILITY",  // Default: ACCURACY
  class_balancing?: {
    enabled: boolean,
    method?: "SMOTE" | "RANDOM_OVERSAMPLE" | "RANDOM_UNDERSAMPLE" | "SMOTE_TOMEK"
  }
}
```

**Example:**
```json
POST /api/v1/ml/datasets/dataset_20251226_143022/recommend-algorithms
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

{
  "problem_type": "BINARY_CLASSIFICATION",
  "target_column": "churn",
  "training_mode": "BALANCED",
  "optimize_for": "ACCURACY",
  "class_balancing": {
    "enabled": true,
    "method": "SMOTE"
  }
}
```

### Response

**Success (200):**
```typescript
{
  recommendations: Array<{
    algorithm: string,             // e.g., "Random Forest", "XGBoost"
    priority: number,              // 1-10 (10 = highest priority)
    expected_performance: {
      min: number,                 // Expected CV score range
      max: number
    },
    training_time_estimate: number, // Seconds
    interpretability_score: number, // 1-10 (10 = most interpretable)
    explanation: string,           // AI-generated explanation
    pros: string[],
    cons: string[],
    hyperparameters: Record<string, any>, // Default hyperparameters
    requires_scaling: boolean,
    supports_feature_importance: boolean
  }>,
  data_profile: {
    n_samples: number,
    n_features: number,
    feature_types: {
      numeric: number,
      categorical: number,
      datetime: number
    },
    class_balance_ratio?: number,  // For classification only
    missing_value_percentage: number,
    high_cardinality_features: string[]
  },
  estimated_total_time: number  // Total training time in seconds
}
```

**Example:**
```json
{
  "recommendations": [
    {
      "algorithm": "XGBoost",
      "priority": 10,
      "expected_performance": {
        "min": 0.82,
        "max": 0.89
      },
      "training_time_estimate": 45,
      "interpretability_score": 6,
      "explanation": "XGBoost is recommended as the top choice for this binary classification task with class imbalance. It handles the 10:1 class ratio effectively and provides excellent performance on medium-sized datasets. The algorithm naturally handles missing values and provides feature importance scores for interpretability.",
      "pros": [
        "Excellent performance on imbalanced datasets",
        "Built-in regularization prevents overfitting",
        "Handles missing values automatically",
        "Fast training with parallelization"
      ],
      "cons": [
        "Less interpretable than linear models or decision trees",
        "Requires careful hyperparameter tuning for optimal results",
        "Can overfit on very small datasets"
      ],
      "hyperparameters": {
        "n_estimators": 100,
        "learning_rate": 0.1,
        "max_depth": 6,
        "scale_pos_weight": 10
      },
      "requires_scaling": false,
      "supports_feature_importance": true
    },
    {
      "algorithm": "Random Forest",
      "priority": 9,
      "expected_performance": {
        "min": 0.78,
        "max": 0.86
      },
      "training_time_estimate": 60,
      "interpretability_score": 7,
      "explanation": "Random Forest is a strong alternative that provides robust performance with minimal tuning. It's more interpretable than XGBoost and handles the class imbalance well when combined with SMOTE preprocessing.",
      "pros": [
        "Robust to outliers and noise",
        "Minimal hyperparameter tuning needed",
        "Provides feature importance",
        "Good generalization"
      ],
      "cons": [
        "Slower training than gradient boosting methods",
        "Larger model size",
        "Can be memory-intensive for large datasets"
      ],
      "hyperparameters": {
        "n_estimators": 100,
        "max_depth": null,
        "class_weight": "balanced"
      },
      "requires_scaling": false,
      "supports_feature_importance": true
    },
    {
      "algorithm": "Logistic Regression",
      "priority": 7,
      "expected_performance": {
        "min": 0.72,
        "max": 0.79
      },
      "training_time_estimate": 5,
      "interpretability_score": 10,
      "explanation": "Logistic Regression offers maximum interpretability with coefficient-based feature importance. While it may not achieve the highest accuracy, it provides clear insights into feature relationships and is excellent for establishing a performance baseline.",
      "pros": [
        "Highly interpretable coefficients",
        "Very fast training",
        "Low memory footprint",
        "Probabilistic predictions"
      ],
      "cons": [
        "Assumes linear relationships",
        "Lower accuracy than tree-based models",
        "Requires feature scaling",
        "Struggles with complex feature interactions"
      ],
      "hyperparameters": {
        "C": 1.0,
        "penalty": "l2",
        "class_weight": "balanced"
      },
      "requires_scaling": true,
      "supports_feature_importance": true
    }
  ],
  "data_profile": {
    "n_samples": 15000,
    "n_features": 23,
    "feature_types": {
      "numeric": 18,
      "categorical": 5,
      "datetime": 0
    },
    "class_balance_ratio": 10.2,
    "missing_value_percentage": 3.5,
    "high_cardinality_features": ["customer_id", "transaction_id"]
  },
  "estimated_total_time": 110
}
```

**Error (404):**
```json
{
  "detail": "Dataset not found or access denied"
}
```

**Error (400):**
```json
{
  "detail": "Invalid training_mode: INVALID. Must be one of: QUICK, BALANCED, COMPREHENSIVE"
}
```

### Implementation Notes
- Uses `AlgorithmSelector.select_algorithms()` method
- Generates `DataProfile` by analyzing dataset from S3
- Integrates `ExplanationService` for AI-generated explanations
- Caches recommendations in Redis (key: `algorithm_recommendations:{dataset_id}:{hash(request)}`, TTL: 1 hour)
- Returns 3-10 algorithms depending on training_mode:
  - QUICK: 3-5 algorithms
  - BALANCED: 5-7 algorithms
  - COMPREHENSIVE: 8-10 algorithms

---

## Endpoint 3: Start AutoML Training

### Metadata
- **Method:** POST
- **Path:** `/datasets/{dataset_id}/train-automl`
- **Purpose:** Initiate asynchronous AutoML training with progress tracking
- **Phase:** 2 (Backend API)
- **Frontend Usage:** TrainingConfig.tsx, TrainingProgress.tsx

### Request

**Path Parameters:**
```typescript
{
  dataset_id: string
}
```

**Body Schema:**
```typescript
{
  target_column: string,
  name?: string,  // Model name (auto-generated if not provided)
  description?: string,
  training_mode: "QUICK" | "BALANCED" | "COMPREHENSIVE",
  optimize_for: "ACCURACY" | "SPEED" | "INTERPRETABILITY",
  selected_algorithms?: string[],  // If empty, use all recommended algorithms
  feature_config?: {
    enable_feature_engineering: boolean,
    enable_feature_selection: boolean,
    max_features?: number,
    scaling_method?: "standard" | "minmax" | "robust"
  },
  class_balancing?: {
    enabled: boolean,
    method?: "SMOTE" | "RANDOM_OVERSAMPLE" | "RANDOM_UNDERSAMPLE" | "SMOTE_TOMEK",
    sampling_strategy?: "auto" | number  // Target ratio or "auto"
  },
  training_config: {
    cv_folds: number,      // Default: 5
    test_size: number,     // Default: 0.2
    random_state: number,  // Default: 42
    max_parallel_jobs?: number,  // Default: 4
    timeout_per_model?: number   // Seconds, default: 600
  }
}
```

**Example:**
```json
POST /api/v1/ml/datasets/dataset_20251226_143022/train-automl
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

{
  "target_column": "churn",
  "name": "Churn Prediction Model v1",
  "description": "Binary classification model to predict customer churn",
  "training_mode": "BALANCED",
  "optimize_for": "ACCURACY",
  "selected_algorithms": ["XGBoost", "Random Forest", "Logistic Regression"],
  "feature_config": {
    "enable_feature_engineering": true,
    "enable_feature_selection": true,
    "max_features": 50,
    "scaling_method": "standard"
  },
  "class_balancing": {
    "enabled": true,
    "method": "SMOTE",
    "sampling_strategy": "auto"
  },
  "training_config": {
    "cv_folds": 5,
    "test_size": 0.2,
    "random_state": 42,
    "max_parallel_jobs": 4,
    "timeout_per_model": 600
  }
}
```

### Response

**Success (202 Accepted):**
```typescript
{
  job_id: string,       // Unique training job ID
  status: "PENDING",
  message: string,
  websocket_url: string,  // WebSocket endpoint for progress tracking
  estimated_completion_time: string  // ISO 8601 datetime
}
```

**Example:**
```json
{
  "job_id": "training_job_20251226_143530",
  "status": "PENDING",
  "message": "Training job queued. Connect to WebSocket for real-time progress.",
  "websocket_url": "/ws/training/training_job_20251226_143530",
  "estimated_completion_time": "2025-12-26T14:40:00Z"
}
```

**Error (404):**
```json
{
  "detail": "Dataset not found or access denied"
}
```

**Error (400):**
```json
{
  "detail": "Invalid algorithm: InvalidAlgo. Must be one of: XGBoost, Random Forest, LightGBM, ..."
}
```

**Error (409 Conflict):**
```json
{
  "detail": "Training job already running for this dataset. Job ID: training_job_20251226_140000"
}
```

### Implementation Notes
- Creates `TrainingJob` document in MongoDB with status=PENDING
- Queues background task using FastAPI BackgroundTasks
- Returns immediately with job_id for progress tracking
- Prevents concurrent training on same dataset (409 if active job exists)
- Stores training configuration in TrainingJob for auditability
- Initializes Redis progress key: `training_progress:{job_id}`

---

## Endpoint 4: Get Training Job Status

### Metadata
- **Method:** GET
- **Path:** `/training-jobs/{job_id}/status`
- **Purpose:** Poll current training job status and progress
- **Phase:** 2 (Backend API)
- **Frontend Usage:** Polling fallback if WebSocket fails

### Request

**Path Parameters:**
```typescript
{
  job_id: string
}
```

**Example:**
```http
GET /api/v1/ml/training-jobs/training_job_20251226_143530/status
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Response

**Success (200):**
```typescript
{
  job_id: string,
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED",
  progress: {
    current_algorithm: string | null,
    completed_algorithms: string[],
    total_algorithms: number,
    current_cv_fold: number,
    total_cv_folds: number,
    percentage_complete: number,  // 0-100
    estimated_time_remaining: number  // Seconds
  },
  created_at: string,  // ISO 8601
  started_at: string | null,
  completed_at: string | null,
  error_message: string | null
}
```

**Example (Running):**
```json
{
  "job_id": "training_job_20251226_143530",
  "status": "RUNNING",
  "progress": {
    "current_algorithm": "Random Forest",
    "completed_algorithms": ["Logistic Regression", "XGBoost"],
    "total_algorithms": 5,
    "current_cv_fold": 3,
    "total_cv_folds": 5,
    "percentage_complete": 52.0,
    "estimated_time_remaining": 135
  },
  "created_at": "2025-12-26T14:35:30Z",
  "started_at": "2025-12-26T14:35:35Z",
  "completed_at": null,
  "error_message": null
}
```

**Example (Completed):**
```json
{
  "job_id": "training_job_20251226_143530",
  "status": "COMPLETED",
  "progress": {
    "current_algorithm": null,
    "completed_algorithms": ["Logistic Regression", "XGBoost", "Random Forest", "LightGBM", "Gradient Boosting"],
    "total_algorithms": 5,
    "current_cv_fold": 5,
    "total_cv_folds": 5,
    "percentage_complete": 100.0,
    "estimated_time_remaining": 0
  },
  "created_at": "2025-12-26T14:35:30Z",
  "started_at": "2025-12-26T14:35:35Z",
  "completed_at": "2025-12-26T14:40:12Z",
  "error_message": null
}
```

**Example (Failed):**
```json
{
  "job_id": "training_job_20251226_143530",
  "status": "FAILED",
  "progress": {
    "current_algorithm": "XGBoost",
    "completed_algorithms": ["Logistic Regression"],
    "total_algorithms": 5,
    "current_cv_fold": 2,
    "total_cv_folds": 5,
    "percentage_complete": 25.0,
    "estimated_time_remaining": 0
  },
  "created_at": "2025-12-26T14:35:30Z",
  "started_at": "2025-12-26T14:35:35Z",
  "completed_at": "2025-12-26T14:37:45Z",
  "error_message": "Out of memory error during XGBoost training. Reduce max_parallel_jobs or dataset size."
}
```

**Error (404):**
```json
{
  "detail": "Training job not found or access denied"
}
```

### Implementation Notes
- Fetches `TrainingJob` from MongoDB
- Validates user_id matches job owner
- Returns progress from Redis if available, falls back to MongoDB
- Used for polling fallback if WebSocket connection fails
- Recommended polling interval: 5 seconds

---

## Endpoint 5: Get Training Job Results

### Metadata
- **Method:** GET
- **Path:** `/training-jobs/{job_id}/results`
- **Purpose:** Retrieve complete training results with all models and comparison
- **Phase:** 2 (Backend API)
- **Frontend Usage:** ModelComparison.tsx, BestModelCard.tsx

### Request

**Path Parameters:**
```typescript
{
  job_id: string
}
```

**Query Parameters:**
```typescript
{
  include_model_artifacts?: boolean  // Default: false (S3 paths only, no model bytes)
}
```

**Example:**
```http
GET /api/v1/ml/training-jobs/training_job_20251226_143530/results?include_model_artifacts=false
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Response

**Success (200):**
```typescript
{
  job_id: string,
  status: "COMPLETED" | "FAILED",
  best_model: {
    model_id: string,
    algorithm: string,
    cv_score: number,
    cv_std: number,
    test_score: number,
    training_time: number,
    model_size: number,
    feature_importance: Record<string, number> | null,
    hyperparameters: Record<string, any>,
    metrics: {
      accuracy?: number,
      precision?: number,
      recall?: number,
      f1_score?: number,
      roc_auc?: number,
      r2_score?: number,
      mse?: number,
      mae?: number
    },
    model_path: string  // S3 path
  },
  all_models: Array<{
    model_id: string,
    algorithm: string,
    cv_score: number,
    cv_std: number,
    test_score: number,
    training_time: number,
    model_size: number,
    hyperparameters: Record<string, any>,
    metrics: Record<string, number>,
    model_path: string,
    rank: number  // 1 = best, 2 = second best, etc.
  }>,
  model_comparison: {
    ranking: Array<{
      rank: number,
      algorithm: string,
      cv_score: number,
      test_score: number,
      training_time: number
    }>,
    performance_summary: string,  // AI-generated summary
    recommendation: string,       // Why best model was chosen
    trade_off_analysis: string,   // Comparison with second-best model
    statistical_significance: Array<{
      model_a: string,
      model_b: string,
      p_value: number,
      significant: boolean
    }>
  },
  training_metadata: {
    dataset_id: string,
    target_column: string,
    problem_type: string,
    n_samples: number,
    n_features_original: number,
    n_features_engineered: number,
    class_balance_applied: boolean,
    training_mode: string,
    total_training_time: number,
    created_at: string,
    completed_at: string
  }
}
```

**Example:**
```json
{
  "job_id": "training_job_20251226_143530",
  "status": "COMPLETED",
  "best_model": {
    "model_id": "model_20251226_144012",
    "algorithm": "XGBoost",
    "cv_score": 0.87,
    "cv_std": 0.03,
    "test_score": 0.85,
    "training_time": 45.2,
    "model_size": 1048576,
    "feature_importance": {
      "recency": 0.23,
      "frequency": 0.19,
      "monetary": 0.18,
      "tenure_months": 0.12,
      "support_tickets": 0.08
    },
    "hyperparameters": {
      "n_estimators": 100,
      "learning_rate": 0.1,
      "max_depth": 6,
      "scale_pos_weight": 10
    },
    "metrics": {
      "accuracy": 0.85,
      "precision": 0.79,
      "recall": 0.83,
      "f1_score": 0.81,
      "roc_auc": 0.87
    },
    "model_path": "s3://narrative-models/user_123/models/model_20251226_144012.pkl"
  },
  "all_models": [
    {
      "model_id": "model_20251226_144012",
      "algorithm": "XGBoost",
      "cv_score": 0.87,
      "cv_std": 0.03,
      "test_score": 0.85,
      "training_time": 45.2,
      "model_size": 1048576,
      "hyperparameters": {
        "n_estimators": 100,
        "learning_rate": 0.1,
        "max_depth": 6
      },
      "metrics": {
        "accuracy": 0.85,
        "precision": 0.79,
        "recall": 0.83,
        "f1_score": 0.81,
        "roc_auc": 0.87
      },
      "model_path": "s3://narrative-models/user_123/models/model_20251226_144012.pkl",
      "rank": 1
    },
    {
      "model_id": "model_20251226_143955",
      "algorithm": "Random Forest",
      "cv_score": 0.84,
      "cv_std": 0.04,
      "test_score": 0.83,
      "training_time": 60.5,
      "model_size": 2097152,
      "hyperparameters": {
        "n_estimators": 100,
        "max_depth": null
      },
      "metrics": {
        "accuracy": 0.83,
        "precision": 0.76,
        "recall": 0.81,
        "f1_score": 0.78,
        "roc_auc": 0.84
      },
      "model_path": "s3://narrative-models/user_123/models/model_20251226_143955.pkl",
      "rank": 2
    },
    {
      "model_id": "model_20251226_143845",
      "algorithm": "Logistic Regression",
      "cv_score": 0.78,
      "cv_std": 0.05,
      "test_score": 0.76,
      "training_time": 5.1,
      "model_size": 51200,
      "hyperparameters": {
        "C": 1.0,
        "penalty": "l2"
      },
      "metrics": {
        "accuracy": 0.76,
        "precision": 0.71,
        "recall": 0.74,
        "f1_score": 0.72,
        "roc_auc": 0.78
      },
      "model_path": "s3://narrative-models/user_123/models/model_20251226_143845.pkl",
      "rank": 3
    }
  ],
  "model_comparison": {
    "ranking": [
      {
        "rank": 1,
        "algorithm": "XGBoost",
        "cv_score": 0.87,
        "test_score": 0.85,
        "training_time": 45.2
      },
      {
        "rank": 2,
        "algorithm": "Random Forest",
        "cv_score": 0.84,
        "test_score": 0.83,
        "training_time": 60.5
      },
      {
        "rank": 3,
        "algorithm": "Logistic Regression",
        "cv_score": 0.78,
        "test_score": 0.76,
        "training_time": 5.1
      }
    ],
    "performance_summary": "All three models demonstrated strong predictive performance, with XGBoost achieving the highest cross-validation score (0.87) and test score (0.85). Random Forest followed closely with CV score 0.84, while Logistic Regression provided a fast baseline at 0.78.",
    "recommendation": "XGBoost is recommended as the production model. It achieved the best performance across all metrics (accuracy: 0.85, F1: 0.81, ROC-AUC: 0.87) while maintaining reasonable training time (45 seconds). The model successfully handles the class imbalance and provides feature importance scores for interpretability.",
    "trade_off_analysis": "While Random Forest is only 0.03 points lower in CV score and provides slightly better interpretability, XGBoost offers superior generalization (test score 0.85 vs 0.83) and 25% faster training time. The small performance gap doesn't justify the increased model size (2MB vs 1MB) of Random Forest. For production deployment, XGBoost's balance of accuracy, speed, and model size makes it the optimal choice.",
    "statistical_significance": [
      {
        "model_a": "XGBoost",
        "model_b": "Random Forest",
        "p_value": 0.04,
        "significant": true
      },
      {
        "model_a": "XGBoost",
        "model_b": "Logistic Regression",
        "p_value": 0.001,
        "significant": true
      },
      {
        "model_a": "Random Forest",
        "model_b": "Logistic Regression",
        "p_value": 0.008,
        "significant": true
      }
    ]
  },
  "training_metadata": {
    "dataset_id": "dataset_20251226_143022",
    "target_column": "churn",
    "problem_type": "BINARY_CLASSIFICATION",
    "n_samples": 15000,
    "n_features_original": 23,
    "n_features_engineered": 35,
    "class_balance_applied": true,
    "training_mode": "BALANCED",
    "total_training_time": 110.8,
    "created_at": "2025-12-26T14:35:30Z",
    "completed_at": "2025-12-26T14:40:12Z"
  }
}
```

**Error (404):**
```json
{
  "detail": "Training job not found or access denied"
}
```

**Error (409 Conflict):**
```json
{
  "detail": "Training job not yet completed. Status: RUNNING"
}
```

### Implementation Notes
- Only returns results if status=COMPLETED
- Returns 409 if job is still PENDING or RUNNING
- Fetches all models from MongoDB (MLModel collection)
- Uses `ExplanationService` to generate comparison text
- Caches results in Redis (key: `training_results:{job_id}`, TTL: 24 hours)
- If include_model_artifacts=true, includes base64-encoded model bytes (use with caution for large models)

---

## WebSocket Protocol

### Endpoint
- **Path:** `/ws/training/{job_id}`
- **Protocol:** WebSocket (ws:// or wss://)
- **Authentication:** JWT token in connection params

### Connection

**Frontend Example:**
```typescript
const token = await getSession().then(s => s?.token);
const ws = new WebSocket(
  `ws://localhost:8000/ws/training/${jobId}?token=${token}`
);
```

### Message Types (Server → Client)

#### 1. Connection Acknowledged
```json
{
  "type": "connection_ack",
  "job_id": "training_job_20251226_143530",
  "timestamp": "2025-12-26T14:35:40Z"
}
```

#### 2. Training Started
```json
{
  "type": "training_started",
  "job_id": "training_job_20251226_143530",
  "total_algorithms": 5,
  "estimated_completion": "2025-12-26T14:40:00Z",
  "timestamp": "2025-12-26T14:35:45Z"
}
```

#### 3. Algorithm Started
```json
{
  "type": "algorithm_started",
  "job_id": "training_job_20251226_143530",
  "algorithm": "XGBoost",
  "algorithm_index": 1,
  "total_algorithms": 5,
  "timestamp": "2025-12-26T14:35:50Z"
}
```

#### 4. CV Fold Progress
```json
{
  "type": "cv_fold_progress",
  "job_id": "training_job_20251226_143530",
  "algorithm": "XGBoost",
  "current_fold": 3,
  "total_folds": 5,
  "fold_score": 0.86,
  "timestamp": "2025-12-26T14:36:10Z"
}
```

#### 5. Algorithm Completed
```json
{
  "type": "algorithm_completed",
  "job_id": "training_job_20251226_143530",
  "algorithm": "XGBoost",
  "cv_score": 0.87,
  "cv_std": 0.03,
  "test_score": 0.85,
  "training_time": 45.2,
  "completed_algorithms": 2,
  "total_algorithms": 5,
  "percentage_complete": 40.0,
  "estimated_time_remaining": 120,
  "timestamp": "2025-12-26T14:36:35Z"
}
```

#### 6. Algorithm Failed
```json
{
  "type": "algorithm_failed",
  "job_id": "training_job_20251226_143530",
  "algorithm": "SVM",
  "error": "Timeout after 600 seconds",
  "completed_algorithms": 3,
  "total_algorithms": 5,
  "timestamp": "2025-12-26T14:38:15Z"
}
```

#### 7. Training Completed
```json
{
  "type": "training_completed",
  "job_id": "training_job_20251226_143530",
  "best_model": {
    "algorithm": "XGBoost",
    "cv_score": 0.87,
    "test_score": 0.85
  },
  "total_algorithms_trained": 5,
  "total_training_time": 110.8,
  "results_url": "/api/v1/ml/training-jobs/training_job_20251226_143530/results",
  "timestamp": "2025-12-26T14:40:12Z"
}
```

#### 8. Training Failed
```json
{
  "type": "training_failed",
  "job_id": "training_job_20251226_143530",
  "error": "Out of memory error during parallel training",
  "failed_algorithm": "XGBoost",
  "completed_algorithms": ["Logistic Regression"],
  "timestamp": "2025-12-26T14:37:45Z"
}
```

#### 9. Heartbeat (every 30 seconds)
```json
{
  "type": "heartbeat",
  "timestamp": "2025-12-26T14:36:00Z"
}
```

### Message Types (Client → Server)

#### 1. Ping (optional, for testing connection)
```json
{
  "type": "ping"
}
```

**Response:**
```json
{
  "type": "pong",
  "timestamp": "2025-12-26T14:36:05Z"
}
```

#### 2. Cancel Training
```json
{
  "type": "cancel_training",
  "job_id": "training_job_20251226_143530"
}
```

**Response:**
```json
{
  "type": "training_cancelled",
  "job_id": "training_job_20251226_143530",
  "message": "Training job cancelled by user",
  "timestamp": "2025-12-26T14:36:30Z"
}
```

### Connection Lifecycle

1. **Connect:** Client establishes WebSocket with JWT token
2. **Authenticate:** Server validates token and user access to job
3. **Acknowledge:** Server sends connection_ack
4. **Stream Progress:** Server broadcasts all progress updates
5. **Completion/Failure:** Server sends final message (training_completed or training_failed)
6. **Disconnect:** Server closes connection after completion (client should also close)

### Error Handling

#### Authentication Failure
```json
{
  "type": "error",
  "code": "AUTH_FAILED",
  "message": "Invalid or expired token",
  "timestamp": "2025-12-26T14:35:40Z"
}
```
**Action:** Server closes connection immediately.

#### Job Not Found
```json
{
  "type": "error",
  "code": "JOB_NOT_FOUND",
  "message": "Training job not found or access denied",
  "timestamp": "2025-12-26T14:35:40Z"
}
```
**Action:** Server closes connection immediately.

### Implementation Notes
- Server maintains `ConnectionManager` with active connections per job_id
- Multiple clients can connect to same job_id (broadcast to all)
- Server sends heartbeat every 30 seconds to detect stale connections
- Client should reconnect with exponential backoff if connection drops
- Progress updates stored in Redis before broadcasting (for reconnection scenarios)
- Connection closed automatically after training_completed or training_failed

---

## TypeScript Type Definitions

### Frontend Types (`lib/types/training.ts`)

```typescript
// Enums
export enum ProblemType {
  REGRESSION = "REGRESSION",
  BINARY_CLASSIFICATION = "BINARY_CLASSIFICATION",
  MULTICLASS_CLASSIFICATION = "MULTICLASS_CLASSIFICATION",
  TIME_SERIES_FORECASTING = "TIME_SERIES_FORECASTING",
  TIME_SERIES_CLASSIFICATION = "TIME_SERIES_CLASSIFICATION"
}

export enum TrainingMode {
  QUICK = "QUICK",
  BALANCED = "BALANCED",
  COMPREHENSIVE = "COMPREHENSIVE"
}

export enum OptimizeFor {
  ACCURACY = "ACCURACY",
  SPEED = "SPEED",
  INTERPRETABILITY = "INTERPRETABILITY"
}

export enum TrainingJobStatus {
  PENDING = "PENDING",
  RUNNING = "RUNNING",
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
  CANCELLED = "CANCELLED"
}

// Request Types
export interface DetectProblemTypeRequest {
  target_column: string;
}

export interface RecommendAlgorithmsRequest {
  problem_type: ProblemType;
  target_column: string;
  training_mode?: TrainingMode;
  optimize_for?: OptimizeFor;
  class_balancing?: {
    enabled: boolean;
    method?: "SMOTE" | "RANDOM_OVERSAMPLE" | "RANDOM_UNDERSAMPLE" | "SMOTE_TOMEK";
  };
}

export interface StartAutoMLTrainingRequest {
  target_column: string;
  name?: string;
  description?: string;
  training_mode: TrainingMode;
  optimize_for: OptimizeFor;
  selected_algorithms?: string[];
  feature_config?: {
    enable_feature_engineering: boolean;
    enable_feature_selection: boolean;
    max_features?: number;
    scaling_method?: "standard" | "minmax" | "robust";
  };
  class_balancing?: {
    enabled: boolean;
    method?: "SMOTE" | "RANDOM_OVERSAMPLE" | "RANDOM_UNDERSAMPLE" | "SMOTE_TOMEK";
    sampling_strategy?: "auto" | number;
  };
  training_config: {
    cv_folds: number;
    test_size: number;
    random_state: number;
    max_parallel_jobs?: number;
    timeout_per_model?: number;
  };
}

// Response Types
export interface ProblemDetectionResult {
  problem_type: ProblemType;
  confidence: number;
  reasoning: string;
  metadata: {
    unique_values: number;
    data_type: string;
    sample_values: any[];
    null_percentage: number;
    recommendations: string[];
  };
}

export interface AlgorithmRecommendation {
  algorithm: string;
  priority: number;
  expected_performance: {
    min: number;
    max: number;
  };
  training_time_estimate: number;
  interpretability_score: number;
  explanation: string;
  pros: string[];
  cons: string[];
  hyperparameters: Record<string, any>;
  requires_scaling: boolean;
  supports_feature_importance: boolean;
}

export interface AlgorithmRecommendationsResponse {
  recommendations: AlgorithmRecommendation[];
  data_profile: {
    n_samples: number;
    n_features: number;
    feature_types: {
      numeric: number;
      categorical: number;
      datetime: number;
    };
    class_balance_ratio?: number;
    missing_value_percentage: number;
    high_cardinality_features: string[];
  };
  estimated_total_time: number;
}

export interface TrainingJobResponse {
  job_id: string;
  status: TrainingJobStatus;
  message: string;
  websocket_url: string;
  estimated_completion_time: string;
}

export interface TrainingProgress {
  current_algorithm: string | null;
  completed_algorithms: string[];
  total_algorithms: number;
  current_cv_fold: number;
  total_cv_folds: number;
  percentage_complete: number;
  estimated_time_remaining: number;
}

export interface TrainingJobStatusResponse {
  job_id: string;
  status: TrainingJobStatus;
  progress: TrainingProgress;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface ModelResult {
  model_id: string;
  algorithm: string;
  cv_score: number;
  cv_std: number;
  test_score: number;
  training_time: number;
  model_size: number;
  hyperparameters: Record<string, any>;
  metrics: Record<string, number>;
  model_path: string;
  rank: number;
  feature_importance?: Record<string, number>;
}

export interface ModelComparison {
  ranking: Array<{
    rank: number;
    algorithm: string;
    cv_score: number;
    test_score: number;
    training_time: number;
  }>;
  performance_summary: string;
  recommendation: string;
  trade_off_analysis: string;
  statistical_significance: Array<{
    model_a: string;
    model_b: string;
    p_value: number;
    significant: boolean;
  }>;
}

export interface TrainingResultsResponse {
  job_id: string;
  status: TrainingJobStatus;
  best_model: ModelResult & { feature_importance: Record<string, number> | null };
  all_models: ModelResult[];
  model_comparison: ModelComparison;
  training_metadata: {
    dataset_id: string;
    target_column: string;
    problem_type: string;
    n_samples: number;
    n_features_original: number;
    n_features_engineered: number;
    class_balance_applied: boolean;
    training_mode: string;
    total_training_time: number;
    created_at: string;
    completed_at: string;
  };
}

// WebSocket Message Types
export type WebSocketMessage =
  | { type: "connection_ack"; job_id: string; timestamp: string }
  | { type: "training_started"; job_id: string; total_algorithms: number; estimated_completion: string; timestamp: string }
  | { type: "algorithm_started"; job_id: string; algorithm: string; algorithm_index: number; total_algorithms: number; timestamp: string }
  | { type: "cv_fold_progress"; job_id: string; algorithm: string; current_fold: number; total_folds: number; fold_score: number; timestamp: string }
  | { type: "algorithm_completed"; job_id: string; algorithm: string; cv_score: number; cv_std: number; test_score: number; training_time: number; completed_algorithms: number; total_algorithms: number; percentage_complete: number; estimated_time_remaining: number; timestamp: string }
  | { type: "algorithm_failed"; job_id: string; algorithm: string; error: string; completed_algorithms: number; total_algorithms: number; timestamp: string }
  | { type: "training_completed"; job_id: string; best_model: { algorithm: string; cv_score: number; test_score: number }; total_algorithms_trained: number; total_training_time: number; results_url: string; timestamp: string }
  | { type: "training_failed"; job_id: string; error: string; failed_algorithm: string; completed_algorithms: string[]; timestamp: string }
  | { type: "heartbeat"; timestamp: string }
  | { type: "pong"; timestamp: string }
  | { type: "training_cancelled"; job_id: string; message: string; timestamp: string }
  | { type: "error"; code: string; message: string; timestamp: string };
```

---

## Error Handling Standards

### HTTP Status Codes

| Code | Usage | Example |
|------|-------|---------|
| 200 | Success | GET /training-jobs/{id}/status (job found) |
| 202 | Accepted (Async) | POST /train-automl (job queued) |
| 400 | Bad Request | Invalid training_mode value |
| 401 | Unauthorized | Missing or invalid JWT token |
| 404 | Not Found | Dataset or job not found |
| 409 | Conflict | Concurrent training job already running |
| 422 | Validation Error | Invalid column name, missing required field |
| 500 | Internal Server Error | Unhandled exception (logged, not exposed) |
| 503 | Service Unavailable | Redis/MongoDB connection failure |

### Error Response Schema

```typescript
{
  detail: string,           // Human-readable error message
  error_code?: string,      // Machine-readable code (e.g., "DATASET_NOT_FOUND")
  field?: string,           // Specific field that caused error (422 only)
  timestamp?: string        // ISO 8601 timestamp
}
```

### Frontend Error Handling Pattern

```typescript
try {
  const result = await api.detectProblemType(datasetId, { target_column });
  // Handle success
} catch (error) {
  if (error.status === 404) {
    // Dataset not found - redirect to upload page
  } else if (error.status === 422) {
    // Validation error - show field-specific error
  } else {
    // Generic error - show toast notification
  }
}
```

---

## Rate Limiting

### OpenAI API Calls (Internal)
- **Algorithm Recommendations:** 1 call per request (cached for 1 hour)
- **Model Comparison:** 1 call per training job (cached for 24 hours)
- **Fallback:** If OpenAI fails, return rule-based explanations without AI

### Client Rate Limits
- **Detect Problem Type:** 10 requests/minute per user
- **Recommend Algorithms:** 5 requests/minute per user
- **Start Training:** 3 requests/minute per user (prevent spam)
- **Get Status:** 60 requests/minute per user (polling)
- **Get Results:** 20 requests/minute per user

**Rate Limit Response (429):**
```json
{
  "detail": "Rate limit exceeded. Try again in 30 seconds.",
  "retry_after": 30
}
```

---

## Versioning Strategy

### API Version
- Current: `v1`
- Path prefix: `/api/v1/ml`
- Breaking changes require new version: `/api/v2/ml`

### Backward Compatibility Rules
1. **Additive changes OK:** New optional fields, new endpoints
2. **Breaking changes require v2:** Removing fields, changing field types, changing semantics
3. **Deprecation policy:** 6-month notice before removing v1

### Schema Versioning
- All responses include implicit schema version via structure
- Frontend validates response structure, falls back gracefully if unknown fields

---

## Testing Requirements

### Contract Testing (Phase 2)

**Backend Contract Tests:**
- OpenAPI schema validation for all endpoints
- Request/response schema validation with Pydantic
- WebSocket message type validation

**Frontend Contract Tests:**
- Mock API responses match TypeScript types
- WebSocket message parsing tests
- Error response handling tests

### Integration Testing (Phase 4)

**API Integration Tests:**
- Full workflow: detect → recommend → train → status → results
- WebSocket connection lifecycle
- Concurrent training job prevention (409 response)
- Error scenarios: invalid dataset, missing columns, OpenAI failure

**E2E Tests:**
- Complete UI workflow with real API calls
- WebSocket reconnection scenarios
- Training cancellation

---

## Contract Change Management

### Change Request Process

1. **Proposal:** Document proposed change in `.claude-flow/implementations/gh-75/CONTRACT_CHANGES.md`
2. **Impact Analysis:** Identify affected components (backend, frontend, tests)
3. **Approval:** Integration Coordinator reviews and approves
4. **Version Bump:** Update contract version in this document header
5. **Implementation:** Update backend, frontend, tests in lockstep
6. **Validation:** Run contract tests to ensure compatibility

### Version History

| Version | Date | Changes | Approved By |
|---------|------|---------|-------------|
| 1.0 | 2025-12-26 | Initial contract definition | Integration Coordinator |

---

## Appendix: Mock Data for Testing

### Mock Problem Detection Response
```json
{
  "problem_type": "BINARY_CLASSIFICATION",
  "confidence": 0.92,
  "reasoning": "Target column has 2 unique values (0, 1) with balanced distribution.",
  "metadata": {
    "unique_values": 2,
    "data_type": "int64",
    "sample_values": [0, 1, 0, 1, 0],
    "null_percentage": 0.0,
    "recommendations": []
  }
}
```

### Mock Algorithm Recommendations Response
See Endpoint 2 example response (complete mock data provided).

### Mock WebSocket Messages Sequence
```json
// 1. Connection
{"type": "connection_ack", "job_id": "job_123", "timestamp": "2025-12-26T14:00:00Z"}

// 2. Start
{"type": "training_started", "job_id": "job_123", "total_algorithms": 3, "estimated_completion": "2025-12-26T14:05:00Z", "timestamp": "2025-12-26T14:00:05Z"}

// 3. Algorithm 1
{"type": "algorithm_started", "job_id": "job_123", "algorithm": "Logistic Regression", "algorithm_index": 1, "total_algorithms": 3, "timestamp": "2025-12-26T14:00:10Z"}
{"type": "cv_fold_progress", "job_id": "job_123", "algorithm": "Logistic Regression", "current_fold": 1, "total_folds": 5, "fold_score": 0.76, "timestamp": "2025-12-26T14:00:12Z"}
// ... folds 2-5 ...
{"type": "algorithm_completed", "job_id": "job_123", "algorithm": "Logistic Regression", "cv_score": 0.78, "cv_std": 0.02, "test_score": 0.76, "training_time": 5.1, "completed_algorithms": 1, "total_algorithms": 3, "percentage_complete": 33.3, "estimated_time_remaining": 100, "timestamp": "2025-12-26T14:00:20Z"}

// 4. Algorithm 2 (similar pattern)
// 5. Algorithm 3 (similar pattern)

// 6. Complete
{"type": "training_completed", "job_id": "job_123", "best_model": {"algorithm": "XGBoost", "cv_score": 0.87, "test_score": 0.85}, "total_algorithms_trained": 3, "total_training_time": 110.8, "results_url": "/api/v1/ml/training-jobs/job_123/results", "timestamp": "2025-12-26T14:05:12Z"}
```

---

**Contract Status:** LOCKED
**Next Review:** After Phase 1 completion (before Phase 2 implementation)
**Contact:** Integration Coordinator for change requests
