"""
Shared fixtures for benchmark tests.
"""
import pytest
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple


@pytest.fixture
def benchmark_data_1k() -> pd.DataFrame:
    """Generate 1K rows of test data for benchmarking."""
    np.random.seed(42)
    return pd.DataFrame({
        'id': range(1000),
        'numeric_1': np.random.randn(1000),
        'numeric_2': np.random.uniform(0, 100, 1000),
        'numeric_3': np.random.randint(0, 1000, 1000),
        'categorical_1': np.random.choice(['A', 'B', 'C', 'D'], 1000),
        'categorical_2': np.random.choice(['X', 'Y', 'Z'], 1000),
        'text': [f'Sample text {i}' for i in range(1000)],
        'with_missing': [np.nan if i % 10 == 0 else i for i in range(1000)],
        'target': np.random.randint(0, 2, 1000)
    })


@pytest.fixture
def benchmark_data_10k() -> pd.DataFrame:
    """Generate 10K rows of test data for benchmarking."""
    np.random.seed(42)
    return pd.DataFrame({
        'id': range(10000),
        'numeric_1': np.random.randn(10000),
        'numeric_2': np.random.uniform(0, 100, 10000),
        'numeric_3': np.random.randint(0, 1000, 10000),
        'categorical_1': np.random.choice(['A', 'B', 'C', 'D'], 10000),
        'categorical_2': np.random.choice(['X', 'Y', 'Z'], 10000),
        'text': [f'Sample text {i}' for i in range(10000)],
        'with_missing': [np.nan if i % 10 == 0 else i for i in range(10000)],
        'target': np.random.randint(0, 2, 10000)
    })


@pytest.fixture
def benchmark_data_100k() -> pd.DataFrame:
    """Generate 100K rows of test data for benchmarking."""
    np.random.seed(42)
    return pd.DataFrame({
        'id': range(100000),
        'numeric_1': np.random.randn(100000),
        'numeric_2': np.random.uniform(0, 100, 100000),
        'numeric_3': np.random.randint(0, 1000, 100000),
        'categorical_1': np.random.choice(['A', 'B', 'C', 'D'], 100000),
        'categorical_2': np.random.choice(['X', 'Y', 'Z'], 100000),
        'text': [f'Sample text {i}' for i in range(100000)],
        'with_missing': [np.nan if i % 10 == 0 else i for i in range(100000)],
        'target': np.random.randint(0, 2, 100000)
    })


@pytest.fixture
def benchmark_data_50k() -> pd.DataFrame:
    """Generate 50K rows of test data for model training benchmarks."""
    np.random.seed(42)
    n_rows = 50000
    return pd.DataFrame({
        'feature_1': np.random.randn(n_rows),
        'feature_2': np.random.uniform(0, 100, n_rows),
        'feature_3': np.random.randint(0, 10, n_rows),
        'feature_4': np.random.randn(n_rows) * 10,
        'feature_5': np.random.uniform(-50, 50, n_rows),
        'categorical_1': np.random.choice(['A', 'B', 'C'], n_rows),
        'categorical_2': np.random.choice(['X', 'Y'], n_rows),
        'target': np.random.randint(0, 2, n_rows)
    })


@pytest.fixture
def performance_targets() -> Dict[str, float]:
    """
    Define performance targets for benchmark tests.

    All times in seconds unless otherwise specified.
    """
    return {
        # Transformation targets
        'transformation_preview_10k': 2.0,  # <2s for 10K rows
        'transformation_apply_100k': 30.0,  # <30s for 100K rows

        # Model training targets
        'model_training_50k': 300.0,  # <5min (300s) for 50K rows

        # Prediction targets
        'single_prediction': 0.1,  # <100ms (0.1s)
        'batch_prediction_throughput': 1000.0,  # 1000 rows/sec
    }


@pytest.fixture
def trained_model_small(benchmark_data_1k) -> Tuple[Any, pd.DataFrame]:
    """
    Provide a pre-trained model for prediction benchmarks.
    Returns (model, test_data).
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    # Prepare data
    X = benchmark_data_1k[['numeric_1', 'numeric_2', 'numeric_3']]
    y = benchmark_data_1k['target']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Train model
    model = RandomForestClassifier(n_estimators=10, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    return model, X_test


@pytest.fixture
def trained_model_large(benchmark_data_10k) -> Tuple[Any, pd.DataFrame]:
    """
    Provide a larger pre-trained model for batch prediction benchmarks.
    Returns (model, test_data).
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    # Prepare data
    X = benchmark_data_10k[['numeric_1', 'numeric_2', 'numeric_3']]
    y = benchmark_data_10k['target']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Train model
    model = RandomForestClassifier(n_estimators=20, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    return model, X_test
