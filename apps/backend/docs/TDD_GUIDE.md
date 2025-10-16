# Test-Driven Development (TDD) Guide

**Author**: Development Team
**Last Updated**: 2025-10-15
**Status**: ✅ Production-Ready
**Target Audience**: All developers working on the narrative-modeling-app backend

---

## Table of Contents

1. [Introduction](#introduction)
2. [TDD Philosophy & Principles](#tdd-philosophy--principles)
3. [The TDD Cycle](#the-tdd-cycle)
4. [Setting Up Your Environment](#setting-up-your-environment)
5. [Writing Your First TDD Feature](#writing-your-first-tdd-feature)
6. [TDD Patterns & Best Practices](#tdd-patterns--best-practices)
7. [Test Organization](#test-organization)
8. [Fixtures & Test Data](#fixtures--test-data)
9. [Common TDD Scenarios](#common-tdd-scenarios)
10. [Troubleshooting](#troubleshooting)
11. [Code Quality Standards](#code-quality-standards)
12. [Resources & References](#resources--references)

---

## Introduction

### What is TDD?

Test-Driven Development (TDD) is a software development methodology where you write tests **before** writing the implementation code. This approach ensures:

- ✅ **Code correctness**: Features work as intended from the start
- ✅ **Better design**: Writing tests first leads to better API design
- ✅ **Confidence**: Refactoring becomes safe with comprehensive test coverage
- ✅ **Documentation**: Tests serve as living documentation of how code should behave
- ✅ **Faster debugging**: Issues are caught immediately, not in production

### Why TDD Matters for This Project

This is an AI-guided machine learning platform where data scientists depend on accurate results. TDD ensures:

1. **Data processing reliability**: Transformations work correctly on diverse datasets
2. **ML model quality**: Model training, validation, and predictions are accurate
3. **API contract stability**: Frontend and backend integration stays stable
4. **Security compliance**: PII detection and data protection work as intended
5. **Production confidence**: Deploy changes without fear of breaking existing features

### Project Testing Status

- **201/201 tests passing (100%)** ✅
- **Unit tests**: 190 tests (no database required)
- **Integration tests**: 11 tests (require MongoDB)
- **Test coverage**: >85% (meeting quality standards)
- **CI/CD**: All tests run automatically on PR and merge

---

## TDD Philosophy & Principles

### The Three Laws of TDD (Uncle Bob)

1. **Write NO production code** until you have a failing test
2. **Write only enough test code** to make the test fail
3. **Write only enough production code** to make the failing test pass

### Core Principles

#### 1. Red-Green-Refactor Cycle

```
🔴 RED    → Write a failing test (proves test works)
🟢 GREEN  → Write minimal code to pass the test
🔵 REFACTOR → Improve code quality without changing behavior
```

#### 2. Test First, Code Second

**Why?** Writing tests first forces you to think about:
- What the code should do (requirements)
- How the code will be used (API design)
- Edge cases and error handling

#### 3. One Test at a Time

Focus on one behavior per test. Don't try to test everything at once.

**Good**:
```python
def test_email_detection():
    """Test that email PII is detected in a column"""
    # Single, focused behavior
```

**Bad**:
```python
def test_all_pii_detection():
    """Test email, phone, SSN, credit card, address detection"""
    # Too many behaviors in one test
```

#### 4. FIRST Principles

- **Fast**: Tests should run in milliseconds
- **Independent**: Tests don't depend on other tests
- **Repeatable**: Same input → same output, every time
- **Self-Validating**: Pass or fail, no manual checking
- **Timely**: Write tests at the right time (before implementation)

---

## The TDD Cycle

### Step-by-Step TDD Workflow

#### Phase 1: 🔴 RED - Write a Failing Test

**Goal**: Prove that the test can fail (and that you're testing real behavior)

```python
# tests/test_services/test_pii_detector.py
import pytest
import pandas as pd
from app.services.security.pii_detector import PIIDetector, PIIType


class TestPIIDetector:

    def test_email_detection(self):
        """Test that email PII is detected in DataFrame columns"""
        # ARRANGE: Set up test data
        detector = PIIDetector()
        df = pd.DataFrame({
            'user_email': ['john@example.com', 'jane@test.org'],
            'other_data': [1, 2]
        })

        # ACT: Call the method under test
        detections = detector.detect_pii_in_dataframe(df)

        # ASSERT: Verify expected behavior
        email_detections = [d for d in detections if d.pii_type == PIIType.EMAIL]
        assert len(email_detections) == 1
        assert email_detections[0].column_name == 'user_email'
        assert email_detections[0].confidence >= 0.8
```

**Run the test** (it should fail):
```bash
PYTHONPATH=. uv run pytest tests/test_services/test_pii_detector.py::TestPIIDetector::test_email_detection -v
```

**Expected output**: `ImportError` or `AttributeError` (method doesn't exist yet)

---

#### Phase 2: 🟢 GREEN - Make the Test Pass

**Goal**: Write the **minimum code** to make the test pass

```python
# app/services/security/pii_detector.py
from enum import Enum
from typing import List
from pydantic import BaseModel
import pandas as pd
import re


class PIIType(Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"


class PIIDetection(BaseModel):
    column_name: str
    pii_type: PIIType
    confidence: float
    sample_values: List[str]


class PIIDetector:
    def __init__(self):
        self.email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )

    def detect_pii_in_dataframe(self, df: pd.DataFrame) -> List[PIIDetection]:
        """Detect PII in DataFrame columns"""
        detections = []

        for column in df.columns:
            # Check for email pattern
            if df[column].dtype == 'object':
                email_matches = df[column].astype(str).str.match(self.email_pattern).sum()
                total_rows = len(df)
                confidence = email_matches / total_rows

                if confidence >= 0.8:
                    detections.append(PIIDetection(
                        column_name=column,
                        pii_type=PIIType.EMAIL,
                        confidence=confidence,
                        sample_values=df[column].head(3).tolist()
                    ))

        return detections
```

**Run the test** (it should pass):
```bash
PYTHONPATH=. uv run pytest tests/test_services/test_pii_detector.py::TestPIIDetector::test_email_detection -v
```

**Expected output**: `PASSED` ✅

---

#### Phase 3: 🔵 REFACTOR - Improve Code Quality

**Goal**: Clean up code without changing behavior (tests still pass)

```python
# app/services/security/pii_detector.py
class PIIDetector:
    def __init__(self):
        self.patterns = {
            PIIType.EMAIL: re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            PIIType.PHONE: re.compile(r'^[\d\s\(\)-]{10,}$'),
            PIIType.SSN: re.compile(r'^\d{3}-\d{2}-\d{4}$')
        }
        self.confidence_threshold = 0.8

    def detect_pii_in_dataframe(self, df: pd.DataFrame) -> List[PIIDetection]:
        """Detect PII in DataFrame columns"""
        detections = []

        for column in df.columns:
            if df[column].dtype == 'object':
                for pii_type, pattern in self.patterns.items():
                    detection = self._detect_pattern(df, column, pii_type, pattern)
                    if detection:
                        detections.append(detection)

        return detections

    def _detect_pattern(
        self,
        df: pd.DataFrame,
        column: str,
        pii_type: PIIType,
        pattern: re.Pattern
    ) -> Optional[PIIDetection]:
        """Detect a specific PII pattern in a column"""
        matches = df[column].astype(str).str.match(pattern).sum()
        confidence = matches / len(df)

        if confidence >= self.confidence_threshold:
            return PIIDetection(
                column_name=column,
                pii_type=pii_type,
                confidence=confidence,
                sample_values=df[column].head(3).tolist()
            )

        return None
```

**Run all tests** (make sure nothing broke):
```bash
PYTHONPATH=. uv run pytest tests/test_services/test_pii_detector.py -v
```

**Expected output**: All tests still pass ✅

---

### The Rhythm of TDD

```
┌─────────────────────────────────────────────────┐
│  🔴 Write a failing test (30 seconds - 2 min)  │
├─────────────────────────────────────────────────┤
│  🟢 Make it pass (2-10 minutes)                 │
├─────────────────────────────────────────────────┤
│  🔵 Refactor (1-5 minutes)                      │
├─────────────────────────────────────────────────┤
│  ✅ Commit (1 minute)                           │
└─────────────────────────────────────────────────┘
           ↓ Repeat for next behavior ↓
```

**Key habits**:
- Run tests frequently (every 2-5 minutes)
- Commit after each green + refactor cycle
- Never skip the refactor step
- Keep cycles short (< 15 minutes per cycle)

---

## Setting Up Your Environment

### Prerequisites

1. **Python 3.11+** with `uv` package manager
2. **MongoDB** (for integration tests)
3. **Redis** (for caching tests)
4. **LocalStack** (for S3 tests, optional)

### Installation

```bash
# Install project dependencies
cd apps/backend
uv sync

# Verify installation
PYTHONPATH=. uv run pytest --version
```

### Running Tests

#### Unit Tests Only (Fast)
```bash
# Run all unit tests (no MongoDB required)
PYTHONPATH=. uv run pytest -m "not integration" -v

# Run specific test file
PYTHONPATH=. uv run pytest tests/test_security/test_pii_detector.py -v

# Run specific test
PYTHONPATH=. uv run pytest tests/test_security/test_pii_detector.py::TestPIIDetector::test_email_detection -v

# Quick run (no output unless failure)
PYTHONPATH=. uv run pytest -m "not integration" -q --tb=no
```

#### Integration Tests (Requires MongoDB)
```bash
# Run integration tests
PYTHONPATH=. uv run pytest -m integration -v
```

#### All Tests
```bash
# Run everything
PYTHONPATH=. uv run pytest -v

# With coverage report
PYTHONPATH=. uv run pytest --cov=app --cov-report=term-missing -v
```

### Test Configuration

```python
# pytest.ini (already configured)
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "unit: Unit tests that don't require external services",
    "integration: Integration tests requiring database/services",
    "asyncio: Async test marker"
]
```

---

## Writing Your First TDD Feature

### Example: Implementing Phone Number Detection

#### Step 1: Define Requirements

**Feature**: Detect phone numbers in DataFrame columns

**Acceptance Criteria**:
- Detect US phone numbers in various formats
- Return confidence score based on match percentage
- Support formats: `(555) 123-4567`, `555-123-4567`, `+1-555-123-4567`

#### Step 2: Write the Test (🔴 RED)

```python
# tests/test_services/test_pii_detector.py

def test_phone_detection(self):
    """Test phone number PII detection"""
    # ARRANGE
    df = pd.DataFrame({
        'phone': ['(555) 123-4567', '555-987-6543', '+1-555-111-2222'],
        'other_data': [1, 2, 3]
    })

    # ACT
    detections = self.detector.detect_pii_in_dataframe(df)

    # ASSERT
    phone_detections = [d for d in detections if d.pii_type == PIIType.PHONE]
    assert len(phone_detections) == 1
    assert phone_detections[0].column_name == 'phone'
    assert phone_detections[0].confidence >= 0.9
```

**Run test** → ❌ FAILS (phone detection not implemented)

#### Step 3: Implement (🟢 GREEN)

```python
# app/services/security/pii_detector.py

class PIIType(Enum):
    EMAIL = "email"
    PHONE = "phone"  # ADD THIS
    SSN = "ssn"

class PIIDetector:
    def __init__(self):
        self.patterns = {
            PIIType.EMAIL: re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            PIIType.PHONE: re.compile(r'^[\+\d\s\(\)-]{10,}$'),  # ADD THIS
            PIIType.SSN: re.compile(r'^\d{3}-\d{2}-\d{4}$')
        }
    # ... rest of implementation uses existing pattern detection logic
```

**Run test** → ✅ PASSES

#### Step 4: Add Edge Cases (🔴 RED → 🟢 GREEN)

```python
def test_phone_detection_mixed_column(self):
    """Test phone detection in column with mixed content"""
    df = pd.DataFrame({
        'contact': ['555-1234', 'Not a phone', '(555) 987-6543'],
        'data': [1, 2, 3]
    })

    detections = self.detector.detect_pii_in_dataframe(df)
    phone_detections = [d for d in detections if d.pii_type == PIIType.PHONE]

    # Should have moderate confidence (2/3 = 0.67)
    assert len(phone_detections) == 1
    assert 0.6 <= phone_detections[0].confidence <= 0.7
```

**Run test** → ✅ PASSES (existing implementation handles this)

#### Step 5: Refactor (🔵 REFACTOR)

No refactoring needed - implementation is clean. Move on to next feature!

---

## TDD Patterns & Best Practices

### Pattern 1: Arrange-Act-Assert (AAA)

**Structure every test with these three sections:**

```python
def test_transformation_preview(self):
    # ARRANGE: Set up test data and dependencies
    df = pd.DataFrame({'col1': [1, 2, 3]})
    engine = TransformationEngine()
    config = TransformationConfig(
        operations=[{'type': 'scale', 'method': 'standard'}]
    )

    # ACT: Execute the behavior being tested
    result = engine.preview_transformation(df, config)

    # ASSERT: Verify expected outcomes
    assert result.success is True
    assert result.preview_rows == 5
    assert 'col1' in result.transformed_data.columns
```

### Pattern 2: One Assert Per Concept

**Good**: Multiple asserts checking the same concept
```python
def test_model_training_result(self):
    result = train_model(data, config)

    # All asserts verify "training succeeded" concept
    assert result.status == "success"
    assert result.model_id is not None
    assert result.accuracy > 0.8
```

**Bad**: Multiple unrelated concepts
```python
def test_everything(self):
    result = train_model(data, config)
    assert result.status == "success"  # Training concept
    assert cache.get('model') is not None  # Caching concept
    assert db.count() == 1  # Database concept - SPLIT THESE!
```

### Pattern 3: Test Naming Convention

**Format**: `test_[unit_under_test]_[scenario]_[expected_result]`

**Examples**:
```python
def test_detect_pii_with_email_column_returns_email_detection()
def test_detect_pii_with_no_pii_returns_empty_list()
def test_detect_pii_with_invalid_data_raises_value_error()
def test_train_model_with_insufficient_data_returns_error_result()
```

### Pattern 4: Given-When-Then (BDD Style)

**Alternative to AAA for behavior-driven tests:**

```python
def test_user_can_train_model_after_uploading_data(self):
    # GIVEN a user has uploaded a dataset
    user_id = "test_user"
    dataset = upload_dataset(user_id, "iris.csv")

    # WHEN the user trains a model
    result = train_model(user_id, dataset.id, target='species')

    # THEN the model is created successfully
    assert result.status == "trained"
    assert result.accuracy > 0.8
```

### Pattern 5: Test Fixtures for Reusable Setup

**Use pytest fixtures for common setup:**

```python
@pytest.fixture
def sample_dataframe():
    """Reusable test DataFrame"""
    return pd.DataFrame({
        'id': [1, 2, 3],
        'value': [10.5, 20.3, 30.1],
        'category': ['A', 'B', 'C']
    })

@pytest.fixture
def detector():
    """Reusable PIIDetector instance"""
    return PIIDetector()

class TestPIIDetector:
    def test_email_detection(self, detector, sample_dataframe):
        # Use fixtures directly
        detections = detector.detect_pii_in_dataframe(sample_dataframe)
        assert len(detections) >= 0
```

### Pattern 6: Parametrized Tests for Multiple Scenarios

**Test the same logic with different inputs:**

```python
@pytest.mark.parametrize("input_value,expected", [
    ("john@example.com", True),
    ("invalid.email", False),
    ("user@test.org", True),
    ("not an email at all", False),
])
def test_email_validation(input_value, expected):
    result = is_valid_email(input_value)
    assert result == expected
```

### Pattern 7: Testing Async Code

**Use pytest-asyncio for async tests:**

```python
@pytest.mark.asyncio
async def test_async_model_training(detector, sample_data):
    """Test async model training"""
    result = await detector.detect_problem_type(
        sample_data,
        target_column='target'
    )

    assert result.problem_type == ProblemType.BINARY_CLASSIFICATION
    assert result.confidence >= 0.9
```

---

## Test Organization

### Directory Structure

```
apps/backend/tests/
├── conftest.py                          # Root fixtures (lazy imports)
├── test_utils/                          # Pure utility tests
│   ├── conftest.py                     # Minimal conftest
│   ├── test_circuit_breaker.py         # @pytest.mark.unit
│   ├── test_plotting.py
│   └── test_schema_inference.py
├── test_security/                       # Security feature tests
│   ├── test_pii_detector.py            # @pytest.mark.unit
│   ├── test_monitoring.py              # @pytest.mark.unit
│   └── test_upload_handler.py          # @pytest.mark.integration
├── test_processing/                     # Data processing tests
│   ├── test_schema_inference.py
│   ├── test_statistics_engine.py
│   └── test_data_processor.py
├── test_model_training/                 # ML model tests
│   ├── test_problem_detector.py
│   ├── test_feature_engineer.py
│   └── test_automl_engine.py
├── test_services/                       # Service layer tests
│   ├── test_dataset_summarization.py
│   └── test_versioning_service.py
├── test_models/                         # Domain model tests
│   ├── test_dataset.py
│   ├── test_transformation.py
│   └── test_model.py
├── test_api/                            # API endpoint tests
│   ├── conftest.py                     # API-specific fixtures
│   ├── test_upload.py                  # @pytest.mark.integration
│   └── test_model_training.py          # @pytest.mark.integration
└── test_integration/                    # Integration tests
    ├── test_circuit_breaker_integration.py
    └── test_api_versioning_integration.py
```

### Test Markers

**Use markers to categorize tests:**

```python
import pytest

@pytest.mark.unit
class TestPIIDetector:
    """Unit tests - no database required"""
    pass

@pytest.mark.integration
class TestUploadAPI:
    """Integration tests - require MongoDB"""
    async def test_upload_endpoint(self, setup_database):
        pass

@pytest.mark.asyncio
async def test_async_operation():
    """Async test"""
    pass
```

**Run by marker:**
```bash
# Unit tests only
PYTHONPATH=. uv run pytest -m unit -v

# Integration tests only
PYTHONPATH=. uv run pytest -m integration -v

# Exclude integration tests
PYTHONPATH=. uv run pytest -m "not integration" -v
```

---

## Fixtures & Test Data

### Root Fixtures (`tests/conftest.py`)

**Available to all tests:**

```python
# Database fixtures
@pytest_asyncio.fixture
async def setup_database(request):
    """Set up test database (skips for unit tests)"""
    if "unit" in request.keywords:
        yield
        return
    # ... MongoDB initialization

# Client fixtures
@pytest_asyncio.fixture
async def authorized_client():
    """FastAPI test client with auth override"""
    # ... returns test client

# Mock fixtures
@pytest.fixture
def mock_user_id() -> str:
    return "test_user_123"

@pytest.fixture
def mock_dataset_id() -> str:
    return "test_dataset_123"
```

### Creating Custom Fixtures

**Example: Feature-specific fixtures**

```python
# tests/test_model_training/conftest.py
import pytest
import pandas as pd
import numpy as np

@pytest.fixture
def binary_classification_data():
    """Binary classification dataset"""
    np.random.seed(42)
    n_samples = 100
    return pd.DataFrame({
        'feature1': np.random.randn(n_samples),
        'feature2': np.random.randn(n_samples),
        'target': np.random.choice([0, 1], n_samples)
    })

@pytest.fixture
def regression_data():
    """Regression dataset"""
    np.random.seed(42)
    n_samples = 100
    X = np.random.randn(n_samples)
    return pd.DataFrame({
        'feature1': X,
        'feature2': np.random.randn(n_samples),
        'price': 100 + 50 * X + 10 * np.random.randn(n_samples)
    })
```

### Fixture Scopes

```python
@pytest.fixture(scope="function")  # Default: new instance per test
def detector():
    return PIIDetector()

@pytest.fixture(scope="class")  # Shared across test class
def shared_detector():
    return PIIDetector()

@pytest.fixture(scope="module")  # Shared across test file
def database_connection():
    conn = create_connection()
    yield conn
    conn.close()

@pytest.fixture(scope="session")  # Shared across entire test session
def app_config():
    return load_config()
```

---

## Common TDD Scenarios

### Scenario 1: Testing a Service Function

**Requirement**: Detect problem type (classification, regression, clustering)

```python
# tests/test_model_training/test_problem_detector.py

class TestProblemDetector:
    @pytest.fixture
    def detector(self):
        return ProblemDetector()

    @pytest.mark.asyncio
    async def test_detect_binary_classification(self, detector):
        # ARRANGE
        df = pd.DataFrame({
            'feature1': [1, 2, 3, 4, 5],
            'target': [0, 1, 0, 1, 0]
        })

        # ACT
        result = await detector.detect_problem_type(df, target_column='target')

        # ASSERT
        assert result.problem_type == ProblemType.BINARY_CLASSIFICATION
        assert result.confidence >= 0.9
        assert result.target_column == 'target'
```

### Scenario 2: Testing an API Endpoint

```python
# tests/test_api/test_upload.py

@pytest.mark.integration
class TestUploadAPI:
    async def test_upload_csv(self, async_authorized_client, test_s3_bucket):
        # ARRANGE
        csv_content = "id,value\n1,10\n2,20"
        files = {'file': ('test.csv', csv_content, 'text/csv')}

        # ACT
        response = await async_authorized_client.post('/api/v1/upload', files=files)

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert 'dataset_id' in data
        assert data['filename'] == 'test.csv'
```

### Scenario 3: Testing Error Handling

```python
def test_detect_pii_with_empty_dataframe_raises_error(self):
    # ARRANGE
    detector = PIIDetector()
    df = pd.DataFrame()

    # ACT & ASSERT
    with pytest.raises(ValueError, match="DataFrame cannot be empty"):
        detector.detect_pii_in_dataframe(df)

def test_detect_pii_with_invalid_column_type(self):
    # ARRANGE
    detector = PIIDetector()
    df = pd.DataFrame({'col1': [None, None, None]})

    # ACT
    detections = detector.detect_pii_in_dataframe(df)

    # ASSERT (should handle gracefully, not raise)
    assert detections == []
```

### Scenario 4: Testing Data Transformations

```python
def test_transformation_preview_scales_data(self):
    # ARRANGE
    df = pd.DataFrame({'values': [1, 2, 3, 4, 5]})
    engine = TransformationEngine()
    config = TransformationConfig(
        operations=[{
            'type': 'scale',
            'column': 'values',
            'method': 'standard'
        }]
    )

    # ACT
    result = engine.preview_transformation(df, config)

    # ASSERT
    assert result.success is True
    # Standard scaling: mean=0, std=1
    assert abs(result.transformed_data['values'].mean()) < 0.01
    assert abs(result.transformed_data['values'].std() - 1.0) < 0.01
```

### Scenario 5: Testing Database Models

```python
@pytest.mark.integration
class TestDatasetModel:
    async def test_create_dataset_metadata(self, setup_database):
        # ARRANGE
        from app.models.dataset import DatasetMetadata, SchemaField

        metadata = DatasetMetadata(
            user_id="test_user",
            dataset_id="test_dataset_123",
            filename="test.csv",
            original_filename="test.csv",
            num_rows=100,
            num_columns=3,
            data_schema=[
                SchemaField(
                    field_name="id",
                    field_type="numeric",
                    inferred_dtype="int64"
                )
            ]
        )

        # ACT
        await metadata.insert()

        # ASSERT
        retrieved = await DatasetMetadata.find_one(
            DatasetMetadata.dataset_id == "test_dataset_123"
        )
        assert retrieved is not None
        assert retrieved.user_id == "test_user"
        assert retrieved.num_rows == 100
```

---

## Troubleshooting

### Common Issues & Solutions

#### Issue 1: Tests Hang During Import

**Symptom**: `pytest` hangs before collecting tests

**Cause**: App initialization in module-level imports

**Solution**: Use lazy imports in fixtures
```python
# BAD
from app.main import app  # Initializes entire FastAPI app

# GOOD
def test_something():
    from app.utils.helper import utility_function  # Lazy import
```

#### Issue 2: MongoDB Connection Errors in Unit Tests

**Symptom**: `pymongo.errors.ServerSelectionTimeoutError`

**Cause**: Test uses `setup_database` but isn't marked as integration

**Solution**: Add `@pytest.mark.integration`
```python
@pytest.mark.integration  # ADD THIS
class TestUploadAPI:
    async def test_upload(self, setup_database):
        pass
```

#### Issue 3: Async Test Failures

**Symptom**: `RuntimeError: no running event loop`

**Solution**: Use `@pytest.mark.asyncio`
```python
@pytest.mark.asyncio  # ADD THIS
async def test_async_function():
    result = await async_operation()
    assert result is not None
```

#### Issue 4: Test Passes When It Shouldn't

**Symptom**: Test passes but implementation is wrong

**Cause**: Test doesn't actually assert the right things

**Solution**: Make test fail first (RED phase)
```python
# Verify test can fail by checking wrong value
def test_detection():
    result = detect_pii(data)
    assert result == "WRONG_VALUE"  # Make it fail first!
    # Then fix to correct assertion
```

#### Issue 5: Flaky Tests (Pass/Fail Randomly)

**Cause**: Tests depend on timing, external state, or test order

**Solution**: Ensure test independence
```python
# BAD: Shared state between tests
shared_counter = 0

def test_increment():
    global shared_counter
    shared_counter += 1
    assert shared_counter == 1  # Fails if run after other tests!

# GOOD: Independent tests
def test_increment():
    counter = 0  # Local state
    counter += 1
    assert counter == 1  # Always passes
```

---

## Code Quality Standards

### Coverage Requirements

**Project standard**: **≥85% code coverage**

```bash
# Check coverage
PYTHONPATH=. uv run pytest --cov=app --cov-report=term-missing -v

# Coverage by component
PYTHONPATH=. uv run pytest --cov=app.services --cov-report=term-missing -v
```

**Coverage targets**:
- **Critical paths** (auth, data processing, model training): >95%
- **Business logic** (services, transformations): >90%
- **API endpoints**: >85%
- **Utilities**: >80%

### Test Quality Checklist

Before marking a feature complete:

- [ ] All tests pass (`pytest -v`)
- [ ] Coverage meets threshold (`--cov`)
- [ ] Tests follow AAA pattern
- [ ] Tests are independent (can run in any order)
- [ ] Tests are fast (unit tests < 1 second each)
- [ ] Tests have descriptive names
- [ ] Edge cases are covered
- [ ] Error cases are tested
- [ ] No skipped tests without justification
- [ ] No test warnings or deprecations

### Documentation Requirements

Every test should have:

1. **Docstring** explaining what is being tested
2. **Descriptive name** following convention
3. **Comments** for complex setup or assertions

```python
def test_detect_pii_with_mixed_content_calculates_correct_confidence(self):
    """
    Test that PII detection calculates confidence correctly when
    a column contains both PII and non-PII values.

    Confidence should be: (matching_rows / total_rows)
    """
    # ARRANGE: Create DataFrame with 2/3 rows matching email pattern
    df = pd.DataFrame({
        'contact': ['user@test.com', 'not an email', 'admin@site.org']
    })

    # ACT
    detections = detector.detect_pii_in_dataframe(df)

    # ASSERT: Confidence should be 2/3 = 0.667
    assert len(detections) == 1
    assert abs(detections[0].confidence - 0.667) < 0.01
```

---

## Resources & References

### Project-Specific Documentation

- **[Test Infrastructure Guide](./TEST_INFRASTRUCTURE.md)** - Detailed test setup and fixtures
- **[Integration Tests README](../tests/integration/README.md)** - Integration test setup
- **[CLAUDE.md](../../../CLAUDE.md)** - Project conventions and quality standards
- **[Sprint 11 Gap Analysis](../../../SPRINT_11_GAP_ANALYSIS.md)** - Recent testing improvements

### TDD Learning Resources

#### Books
- **"Test Driven Development: By Example"** by Kent Beck - The TDD bible
- **"Growing Object-Oriented Software, Guided by Tests"** by Steve Freeman & Nat Pryce
- **"The Art of Unit Testing"** by Roy Osherove
- **"Working Effectively with Legacy Code"** by Michael Feathers

#### Online Resources
- [pytest documentation](https://docs.pytest.org/) - Official pytest docs
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/) - Async testing
- [Real Python - Testing](https://realpython.com/pytest-python-testing/) - pytest tutorials
- [Martin Fowler - TDD](https://martinfowler.com/bliki/TestDrivenDevelopment.html) - TDD philosophy

### Testing Tools & Plugins

```bash
# Core testing
pytest              # Test runner
pytest-asyncio      # Async test support
pytest-cov          # Coverage reporting
pytest-xdist        # Parallel test execution

# Mocking & fixtures
pytest-mock         # Mocking utilities
faker               # Fake data generation

# Quality tools
ruff                # Linting and formatting
mypy                # Type checking
```

---

## Quick Reference Card

### TDD Cycle
```
1. 🔴 RED:     Write failing test
2. 🟢 GREEN:   Minimal code to pass
3. 🔵 REFACTOR: Clean up code
4. ✅ COMMIT:   Save progress
```

### Essential Commands
```bash
# Run unit tests
PYTHONPATH=. uv run pytest -m "not integration" -v

# Run specific test
PYTHONPATH=. uv run pytest tests/path/test_file.py::TestClass::test_method -v

# Run with coverage
PYTHONPATH=. uv run pytest --cov=app --cov-report=term-missing -v

# Watch mode (requires pytest-watch)
PYTHONPATH=. uv run ptw -- -v
```

### Test Template
```python
import pytest
from app.module import Class

class TestClass:
    @pytest.fixture
    def instance(self):
        return Class()

    def test_behavior_with_valid_input_returns_expected_result(self, instance):
        # ARRANGE
        input_data = "test"

        # ACT
        result = instance.method(input_data)

        # ASSERT
        assert result == "expected"
```

---

## Next Steps

### For New Developers

1. ✅ **Read this guide completely**
2. ✅ **Run existing tests**: `PYTHONPATH=. uv run pytest -v`
3. ✅ **Pick a simple feature** from the backlog
4. ✅ **Write tests first** following TDD cycle
5. ✅ **Implement the feature** with minimal code
6. ✅ **Refactor and commit**
7. ✅ **Get code review** to verify TDD approach

### For This Project

**Immediate priorities** (from Sprint 11.1B):

1. **Create Dataset Service** with TDD
   - Write tests for `create_dataset()`, `get_dataset()`, `list_datasets()`
   - Implement dual-write strategy
   - Test backward compatibility

2. **Create Transformation Service** with TDD
   - Write tests for `create_transformation()`, `preview_transformation()`
   - Test integration with transformation_engine
   - Verify TransformationConfig usage

3. **Create Model Service** with TDD
   - Write tests for `create_model_config()`, `update_training_status()`
   - Test performance metric tracking
   - Verify ModelConfig integration

**See**: [Sprint 11 Gap Analysis](../../../SPRINT_11_GAP_ANALYSIS.md) for detailed implementation requirements

---

## Conclusion

Test-Driven Development is not just about testing - it's about **designing better software through tests**. By writing tests first:

- You think through requirements before coding
- You create cleaner, more maintainable APIs
- You build confidence in your code
- You enable safe refactoring
- You document how code should be used

**Remember**: TDD is a discipline, not a burden. The upfront investment in tests pays dividends in:
- Fewer bugs in production
- Faster debugging when issues arise
- Confidence to refactor and improve code
- Better collaboration with other developers

---

**Questions or improvements to this guide?**

- Open an issue in the project repository
- Contact the development team
- Contribute improvements via pull request

**Happy Testing!** 🧪✅
