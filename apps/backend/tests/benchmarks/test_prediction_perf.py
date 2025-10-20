"""
Prediction performance benchmarks.

Tests prediction operations to ensure they meet performance targets:
- Single prediction: <100ms (0.1s)
- Batch prediction: 1000 rows/sec
"""
import pytest
import pandas as pd
import numpy as np


class TestPredictionPerformance:
    """Benchmark prediction operations"""

    def test_single_prediction_rf(self, benchmark, trained_model_small, performance_targets):
        """Benchmark single prediction with Random Forest (<100ms)"""
        model, X_test = trained_model_small

        # Create single row for prediction
        single_row = X_test.iloc[[0]]

        def predict_single():
            return model.predict(single_row)

        result = benchmark(predict_single)

        # Verify prediction
        assert result is not None
        assert len(result) == 1

        # Check performance target (convert to seconds)
        assert benchmark.stats['mean'] < performance_targets['single_prediction'], \
            f"Single prediction took {benchmark.stats['mean']*1000:.2f}ms, target is {performance_targets['single_prediction']*1000}ms"

    def test_single_prediction_proba_rf(self, benchmark, trained_model_small, performance_targets):
        """Benchmark single prediction with probabilities (<100ms)"""
        model, X_test = trained_model_small

        # Create single row for prediction
        single_row = X_test.iloc[[0]]

        def predict_proba():
            return model.predict_proba(single_row)

        result = benchmark(predict_proba)

        assert result is not None
        assert result.shape[0] == 1
        assert benchmark.stats['mean'] < performance_targets['single_prediction'], \
            f"Single predict_proba took {benchmark.stats['mean']*1000:.2f}ms, target is {performance_targets['single_prediction']*1000}ms"

    def test_batch_prediction_1000_rows(self, benchmark, trained_model_large, performance_targets):
        """Benchmark batch prediction for 1000 rows (target: 1000 rows/sec)"""
        model, X_test = trained_model_large

        # Take exactly 1000 rows
        batch_data = X_test.iloc[:1000]

        def predict_batch():
            return model.predict(batch_data)

        result = benchmark(predict_batch)

        # Verify predictions
        assert result is not None
        assert len(result) == 1000

        # Check throughput (1000 rows should process in ~1 second)
        rows_per_sec = 1000 / benchmark.stats['mean']
        assert rows_per_sec >= performance_targets['batch_prediction_throughput'], \
            f"Batch prediction throughput: {rows_per_sec:.0f} rows/sec, target is {performance_targets['batch_prediction_throughput']} rows/sec"

    def test_batch_prediction_10000_rows(self, benchmark, trained_model_large):
        """Benchmark batch prediction for 10K rows"""
        model, X_test = trained_model_large

        # Use all test data (approximately 2000 rows from 10K split)
        batch_data = X_test

        def predict_batch():
            return model.predict(batch_data)

        result = benchmark(predict_batch)

        assert result is not None
        assert len(result) == len(batch_data)

        # Log throughput
        rows_per_sec = len(batch_data) / benchmark.stats['mean']
        print(f"\nBatch prediction ({len(batch_data)} rows): {rows_per_sec:.0f} rows/sec")


class TestPredictionScalability:
    """Test prediction scalability across different batch sizes"""

    @pytest.mark.parametrize("batch_size", [1, 10, 100, 1000, 10000])
    def test_scalability_batch_prediction(self, benchmark, trained_model_large, batch_size):
        """Test how batch prediction scales with batch size"""
        model, X_test = trained_model_large

        # Ensure we have enough data
        if len(X_test) < batch_size:
            pytest.skip(f"Not enough test data for batch size {batch_size}")

        batch_data = X_test.iloc[:batch_size]

        def predict_batch():
            return model.predict(batch_data)

        result = benchmark(predict_batch)

        assert result is not None
        assert len(result) == batch_size

        # Log scaling metrics
        rows_per_sec = batch_size / benchmark.stats['mean']
        latency_ms = (benchmark.stats['mean'] / batch_size) * 1000
        print(f"\nBatch size {batch_size}: {rows_per_sec:.0f} rows/sec, {latency_ms:.2f}ms per row")


class TestPredictionMemoryEfficiency:
    """Test memory efficiency of prediction operations"""

    def test_batch_prediction_memory_1000(self, benchmark, trained_model_large):
        """Benchmark memory usage for batch prediction (1000 rows)"""
        import psutil
        import os

        model, X_test = trained_model_large
        batch_data = X_test.iloc[:1000]

        process = psutil.Process(os.getpid())

        def predict_with_memory():
            mem_before = process.memory_info().rss / 1024 / 1024  # MB
            result = model.predict(batch_data)
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            return result, mem_after - mem_before

        result, mem_used = benchmark(predict_with_memory)

        assert result is not None
        print(f"\nMemory used for 1000 predictions: {mem_used:.2f} MB")

    def test_batch_prediction_memory_10000(self, benchmark, trained_model_large):
        """Benchmark memory usage for batch prediction (10K rows)"""
        import psutil
        import os

        model, X_test = trained_model_large
        # Extend test data if needed
        if len(X_test) < 10000:
            # Repeat the data to get 10K rows
            repetitions = (10000 // len(X_test)) + 1
            batch_data = pd.concat([X_test] * repetitions, ignore_index=True).iloc[:10000]
        else:
            batch_data = X_test.iloc[:10000]

        process = psutil.Process(os.getpid())

        def predict_with_memory():
            mem_before = process.memory_info().rss / 1024 / 1024  # MB
            result = model.predict(batch_data)
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            return result, mem_after - mem_before

        result, mem_used = benchmark(predict_with_memory)

        assert result is not None
        print(f"\nMemory used for 10K predictions: {mem_used:.2f} MB")


class TestPredictionWithDifferentModels:
    """Compare prediction performance across different model types"""

    def test_logistic_regression_prediction(self, benchmark, benchmark_data_1k):
        """Benchmark logistic regression prediction"""
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split

        X = benchmark_data_1k[['numeric_1', 'numeric_2', 'numeric_3']]
        y = benchmark_data_1k['target']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Train model
        model = LogisticRegression(max_iter=1000, random_state=42)
        model.fit(X_train, y_train)

        # Benchmark prediction
        batch_data = X_test.iloc[:100]

        def predict():
            return model.predict(batch_data)

        result = benchmark(predict)
        assert result is not None

        rows_per_sec = 100 / benchmark.stats['mean']
        print(f"\nLogistic Regression: {rows_per_sec:.0f} rows/sec")

    def test_random_forest_prediction(self, benchmark, benchmark_data_1k):
        """Benchmark random forest prediction"""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split

        X = benchmark_data_1k[['numeric_1', 'numeric_2', 'numeric_3']]
        y = benchmark_data_1k['target']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Train model
        model = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)

        # Benchmark prediction
        batch_data = X_test.iloc[:100]

        def predict():
            return model.predict(batch_data)

        result = benchmark(predict)
        assert result is not None

        rows_per_sec = 100 / benchmark.stats['mean']
        print(f"\nRandom Forest: {rows_per_sec:.0f} rows/sec")

    def test_xgboost_prediction(self, benchmark, benchmark_data_1k):
        """Benchmark XGBoost prediction"""
        import xgboost as xgb
        from sklearn.model_selection import train_test_split

        X = benchmark_data_1k[['numeric_1', 'numeric_2', 'numeric_3']]
        y = benchmark_data_1k['target']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Train model
        model = xgb.XGBClassifier(n_estimators=50, random_state=42, n_jobs=-1, tree_method='hist')
        model.fit(X_train, y_train, verbose=False)

        # Benchmark prediction
        batch_data = X_test.iloc[:100]

        def predict():
            return model.predict(batch_data)

        result = benchmark(predict)
        assert result is not None

        rows_per_sec = 100 / benchmark.stats['mean']
        print(f"\nXGBoost: {rows_per_sec:.0f} rows/sec")
