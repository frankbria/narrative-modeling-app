"""
Model training performance benchmarks.

Tests model training operations to ensure they meet performance targets:
- Training duration: <5min (300s) for 50K rows
- Different algorithms: logistic regression, random forest, XGBoost
"""
import pytest
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import xgboost as xgb


class TestModelTrainingPerformance:
    """Benchmark model training operations"""

    def test_train_logistic_regression_50k(self, benchmark, benchmark_data_50k, performance_targets):
        """Benchmark logistic regression training (50K rows)"""
        X = benchmark_data_50k[['feature_1', 'feature_2', 'feature_3', 'feature_4', 'feature_5']]
        y = benchmark_data_50k['target']

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        def train_model():
            model = LogisticRegression(max_iter=1000, random_state=42, n_jobs=-1)
            model.fit(X_train, y_train)
            return model

        model = benchmark(train_model)

        # Verify model trained successfully
        assert model is not None
        assert hasattr(model, 'predict')

        # Check performance target
        assert benchmark.stats['mean'] < performance_targets['model_training_50k'], \
            f"Training took {benchmark.stats['mean']:.2f}s, target is {performance_targets['model_training_50k']}s"

    def test_train_random_forest_50k(self, benchmark, benchmark_data_50k, performance_targets):
        """Benchmark random forest training (50K rows)"""
        X = benchmark_data_50k[['feature_1', 'feature_2', 'feature_3', 'feature_4', 'feature_5']]
        y = benchmark_data_50k['target']

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        def train_model():
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            model.fit(X_train, y_train)
            return model

        model = benchmark(train_model)

        assert model is not None
        assert hasattr(model, 'predict')
        assert benchmark.stats['mean'] < performance_targets['model_training_50k'], \
            f"Training took {benchmark.stats['mean']:.2f}s, target is {performance_targets['model_training_50k']}s"

    def test_train_xgboost_50k(self, benchmark, benchmark_data_50k, performance_targets):
        """Benchmark XGBoost training (50K rows)"""
        X = benchmark_data_50k[['feature_1', 'feature_2', 'feature_3', 'feature_4', 'feature_5']]
        y = benchmark_data_50k['target']

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        def train_model():
            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                n_jobs=-1,
                tree_method='hist'  # Faster histogram-based algorithm
            )
            model.fit(X_train, y_train, verbose=False)
            return model

        model = benchmark(train_model)

        assert model is not None
        assert hasattr(model, 'predict')
        assert benchmark.stats['mean'] < performance_targets['model_training_50k'], \
            f"Training took {benchmark.stats['mean']:.2f}s, target is {performance_targets['model_training_50k']}s"


class TestModelTrainingScalability:
    """Test model training scalability across different data sizes"""

    @pytest.mark.parametrize("n_rows", [1000, 10000, 50000])
    def test_scalability_logistic_regression(self, benchmark, n_rows):
        """Test how logistic regression training scales with data size"""
        np.random.seed(42)
        X = np.random.randn(n_rows, 5)
        y = np.random.randint(0, 2, n_rows)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        def train_model():
            model = LogisticRegression(max_iter=1000, random_state=42, n_jobs=-1)
            model.fit(X_train, y_train)
            return model

        model = benchmark(train_model)
        assert model is not None

        # Log scaling metrics
        print(f"\nLogistic Regression with {n_rows} rows: {benchmark.stats['mean']:.3f}s")

    @pytest.mark.parametrize("n_rows", [1000, 10000, 50000])
    def test_scalability_random_forest(self, benchmark, n_rows):
        """Test how random forest training scales with data size"""
        np.random.seed(42)
        X = np.random.randn(n_rows, 5)
        y = np.random.randint(0, 2, n_rows)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        def train_model():
            model = RandomForestClassifier(
                n_estimators=50,  # Reduced for faster training
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            model.fit(X_train, y_train)
            return model

        model = benchmark(train_model)
        assert model is not None

        # Log scaling metrics
        print(f"\nRandom Forest with {n_rows} rows: {benchmark.stats['mean']:.3f}s")

    @pytest.mark.parametrize("n_rows", [1000, 10000, 50000])
    def test_scalability_xgboost(self, benchmark, n_rows):
        """Test how XGBoost training scales with data size"""
        np.random.seed(42)
        X = np.random.randn(n_rows, 5)
        y = np.random.randint(0, 2, n_rows)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        def train_model():
            model = xgb.XGBClassifier(
                n_estimators=50,  # Reduced for faster training
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                n_jobs=-1,
                tree_method='hist'
            )
            model.fit(X_train, y_train, verbose=False)
            return model

        model = benchmark(train_model)
        assert model is not None

        # Log scaling metrics
        print(f"\nXGBoost with {n_rows} rows: {benchmark.stats['mean']:.3f}s")


class TestModelTrainingWithTransformations:
    """Benchmark model training with data transformation pipeline"""

    def test_train_with_preprocessing_50k(self, benchmark, benchmark_data_50k, performance_targets):
        """Benchmark training with preprocessing pipeline (50K rows)"""
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline

        X = benchmark_data_50k[['feature_1', 'feature_2', 'feature_3', 'feature_4', 'feature_5']]
        y = benchmark_data_50k['target']

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        def train_pipeline():
            pipeline = Pipeline([
                ('scaler', StandardScaler()),
                ('classifier', LogisticRegression(max_iter=1000, random_state=42, n_jobs=-1))
            ])
            pipeline.fit(X_train, y_train)
            return pipeline

        pipeline = benchmark(train_pipeline)

        assert pipeline is not None
        assert hasattr(pipeline, 'predict')
        # Allow 50% overhead for preprocessing
        assert benchmark.stats['mean'] < performance_targets['model_training_50k'] * 1.5, \
            f"Training with preprocessing took {benchmark.stats['mean']:.2f}s, target is {performance_targets['model_training_50k'] * 1.5}s"
