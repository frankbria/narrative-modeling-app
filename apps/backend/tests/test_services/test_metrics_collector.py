# apps/backend/tests/test_services/test_metrics_collector.py
"""
Tests for ML and business metrics collector.

Tests:
- ML training duration tracking
- ML prediction latency tracking
- Model accuracy recording
- Dataset size recording
- Business metrics (users, datasets, models, predictions)
"""

import pytest
import time
from app.services.metrics_collector import (
    MLMetricsCollector,
    BusinessMetricsCollector,
    ml_metrics,
    business_metrics,
)
from prometheus_client import CollectorRegistry


@pytest.fixture
def ml_collector():
    """Create a fresh ML metrics collector for testing."""
    registry = CollectorRegistry()
    return MLMetricsCollector(registry)


@pytest.fixture
def business_collector():
    """Create a fresh business metrics collector for testing."""
    registry = CollectorRegistry()
    return BusinessMetricsCollector(registry)


class TestMLMetricsCollector:
    """Test suite for MLMetricsCollector."""

    def test_track_training_duration(self, ml_collector):
        """Test tracking of model training duration."""
        # Track a training operation
        with ml_collector.track_training_duration(
            model_type="random_forest", problem_type="classification"
        ):
            time.sleep(0.1)  # Simulate training

        # Verify metric was recorded
        metric_families = list(ml_collector.training_duration.collect())
        assert len(metric_families) > 0

        # Find the sample with our labels
        found = False
        for family in metric_families:
            for sample in family.samples:
                if (
                    sample.labels.get("model_type") == "random_forest"
                    and sample.labels.get("problem_type") == "classification"
                ):
                    if "_count" in sample.name:
                        assert sample.value >= 1
                        found = True
        assert found, "Training duration metric not found"

    def test_track_training_duration_context_manager(self, ml_collector):
        """Test that training duration context manager works correctly."""
        # Should not raise an error
        with ml_collector.track_training_duration("xgboost", "regression"):
            pass

        # Verify metric exists
        metric_families = list(ml_collector.training_duration.collect())
        assert len(metric_families) > 0

    def test_track_prediction_latency(self, ml_collector):
        """Test tracking of prediction latency."""
        # Track a prediction operation
        with ml_collector.track_prediction_latency(
            model_type="logistic_regression", model_id="model_123"
        ):
            time.sleep(0.01)  # Simulate prediction

        # Verify metric was recorded
        metric_families = list(ml_collector.prediction_latency.collect())
        assert len(metric_families) > 0

        found = False
        for family in metric_families:
            for sample in family.samples:
                if (
                    sample.labels.get("model_type") == "logistic_regression"
                    and sample.labels.get("model_id") == "model_123"
                ):
                    if "_count" in sample.name:
                        assert sample.value >= 1
                        found = True
        assert found, "Prediction latency metric not found"

    def test_record_model_accuracy(self, ml_collector):
        """Test recording model accuracy."""
        # Record accuracy
        ml_collector.record_model_accuracy(
            model_id="model_456",
            model_type="random_forest",
            accuracy=0.95,
            metric_name="accuracy",
        )

        # Verify metric was recorded
        metric_families = list(ml_collector.model_accuracy.collect())
        assert len(metric_families) > 0

        found = False
        for family in metric_families:
            for sample in family.samples:
                if (
                    sample.labels.get("model_id") == "model_456"
                    and sample.labels.get("model_type") == "random_forest"
                    and sample.labels.get("metric_name") == "accuracy"
                ):
                    assert sample.value == 0.95
                    found = True
        assert found, "Model accuracy metric not found"

    def test_record_model_accuracy_different_metrics(self, ml_collector):
        """Test recording different model metrics."""
        # Record different metrics
        ml_collector.record_model_accuracy(
            model_id="model_789",
            model_type="xgboost",
            accuracy=0.92,
            metric_name="precision",
        )

        ml_collector.record_model_accuracy(
            model_id="model_789", model_type="xgboost", accuracy=0.89, metric_name="recall"
        )

        # Verify both metrics were recorded
        metric_families = list(ml_collector.model_accuracy.collect())
        precision_found = False
        recall_found = False

        for family in metric_families:
            for sample in family.samples:
                if sample.labels.get("model_id") == "model_789":
                    if sample.labels.get("metric_name") == "precision":
                        assert sample.value == 0.92
                        precision_found = True
                    elif sample.labels.get("metric_name") == "recall":
                        assert sample.value == 0.89
                        recall_found = True

        assert precision_found and recall_found, "Not all metrics found"

    def test_record_dataset_size(self, ml_collector):
        """Test recording dataset size."""
        # Record dataset size
        ml_collector.record_dataset_size(dataset_id="dataset_001", num_rows=10000)

        # Verify metric was recorded
        metric_families = list(ml_collector.dataset_size.collect())
        assert len(metric_families) > 0

        found = False
        for family in metric_families:
            for sample in family.samples:
                if sample.labels.get("dataset_id") == "dataset_001":
                    if "_count" in sample.name:
                        assert sample.value >= 1
                        found = True
        assert found, "Dataset size metric not found"

    def test_training_duration_buckets(self, ml_collector):
        """Test that training duration has correct histogram buckets."""
        with ml_collector.track_training_duration("test_model", "test_problem"):
            pass

        metric_families = list(ml_collector.training_duration.collect())
        for family in metric_families:
            for sample in family.samples:
                if "_bucket" in sample.name:
                    # Should have buckets: 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0
                    # At least verify +Inf bucket exists
                    if sample.labels.get("le") == "+Inf":
                        assert True
                        return
        pytest.fail("No +Inf bucket found in training duration histogram")

    def test_prediction_latency_buckets(self, ml_collector):
        """Test that prediction latency has correct histogram buckets."""
        with ml_collector.track_prediction_latency("test_model", "test_id"):
            pass

        metric_families = list(ml_collector.prediction_latency.collect())
        for family in metric_families:
            for sample in family.samples:
                if "_bucket" in sample.name:
                    # Should have buckets: 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0
                    if sample.labels.get("le") == "+Inf":
                        assert True
                        return
        pytest.fail("No +Inf bucket found in prediction latency histogram")

    def test_dataset_size_buckets(self, ml_collector):
        """Test that dataset size has correct histogram buckets."""
        ml_collector.record_dataset_size("test_dataset", 1000)

        metric_families = list(ml_collector.dataset_size.collect())
        for family in metric_families:
            for sample in family.samples:
                if "_bucket" in sample.name:
                    # Should have buckets for dataset sizes
                    if sample.labels.get("le") == "+Inf":
                        assert True
                        return
        pytest.fail("No +Inf bucket found in dataset size histogram")


class TestBusinessMetricsCollector:
    """Test suite for BusinessMetricsCollector."""

    def test_set_active_users(self, business_collector):
        """Test setting active users count."""
        # Set active users
        business_collector.set_active_users(count=150, time_window="day")

        # Verify metric was recorded
        metric_families = list(business_collector.active_users.collect())
        assert len(metric_families) > 0

        found = False
        for family in metric_families:
            for sample in family.samples:
                if sample.labels.get("time_window") == "day":
                    assert sample.value == 150
                    found = True
        assert found, "Active users metric not found"

    def test_set_active_users_different_windows(self, business_collector):
        """Test setting active users for different time windows."""
        # Set for different windows
        business_collector.set_active_users(count=100, time_window="day")
        business_collector.set_active_users(count=500, time_window="week")
        business_collector.set_active_users(count=1000, time_window="month")

        # Verify all windows tracked
        metric_families = list(business_collector.active_users.collect())
        windows = {"day": 100, "week": 500, "month": 1000}
        found_windows = set()

        for family in metric_families:
            for sample in family.samples:
                window = sample.labels.get("time_window")
                if window in windows:
                    assert sample.value == windows[window]
                    found_windows.add(window)

        assert len(found_windows) == 3, "Not all time windows found"

    def test_increment_datasets_created(self, business_collector):
        """Test incrementing datasets created counter."""
        # Increment counter
        business_collector.increment_datasets_created(user_id="user_123")
        business_collector.increment_datasets_created(user_id="user_123")

        # Verify metric was incremented
        metric_families = list(business_collector.datasets_created.collect())
        assert len(metric_families) > 0

        found = False
        for family in metric_families:
            for sample in family.samples:
                # Look for the _total field (counter total)
                if "_total" in sample.name and sample.labels.get("user_id") == "user_123":
                    assert sample.value == 2
                    found = True
        assert found, "Datasets created metric not found"

    def test_increment_models_trained(self, business_collector):
        """Test incrementing models trained counter."""
        # Increment counter
        business_collector.increment_models_trained(
            model_type="random_forest", user_id="user_456"
        )
        business_collector.increment_models_trained(
            model_type="random_forest", user_id="user_456"
        )
        business_collector.increment_models_trained(
            model_type="xgboost", user_id="user_456"
        )

        # Verify metrics
        metric_families = list(business_collector.models_trained.collect())
        rf_count = 0
        xgb_count = 0

        for family in metric_families:
            for sample in family.samples:
                # Look for the _total field (counter total)
                if "_total" in sample.name and sample.labels.get("user_id") == "user_456":
                    if sample.labels.get("model_type") == "random_forest":
                        rf_count = sample.value
                    elif sample.labels.get("model_type") == "xgboost":
                        xgb_count = sample.value

        assert rf_count == 2, "Random forest count incorrect"
        assert xgb_count == 1, "XGBoost count incorrect"

    def test_increment_predictions_made(self, business_collector):
        """Test incrementing predictions made counter."""
        # Increment counter
        business_collector.increment_predictions_made(model_id="model_789")
        business_collector.increment_predictions_made(model_id="model_789")
        business_collector.increment_predictions_made(model_id="model_789")

        # Verify metric
        metric_families = list(business_collector.predictions_made.collect())
        assert len(metric_families) > 0

        found = False
        for family in metric_families:
            for sample in family.samples:
                # Look for the _total field (counter total)
                if "_total" in sample.name and sample.labels.get("model_id") == "model_789":
                    assert sample.value == 3
                    found = True
        assert found, "Predictions made metric not found"

    def test_multiple_users_tracked_separately(self, business_collector):
        """Test that different users are tracked separately."""
        # Increment for different users
        business_collector.increment_datasets_created(user_id="user_001")
        business_collector.increment_datasets_created(user_id="user_002")
        business_collector.increment_datasets_created(user_id="user_001")

        # Verify separate tracking
        metric_families = list(business_collector.datasets_created.collect())
        user_counts = {}

        for family in metric_families:
            for sample in family.samples:
                # Look for the _total field (counter total)
                if "_total" in sample.name:
                    user_id = sample.labels.get("user_id")
                    if user_id:
                        user_counts[user_id] = sample.value

        assert user_counts.get("user_001") == 2
        assert user_counts.get("user_002") == 1


class TestGlobalInstances:
    """Test suite for global metric collector instances."""

    def test_ml_metrics_instance_exists(self):
        """Test that ml_metrics global instance exists."""
        assert ml_metrics is not None
        assert isinstance(ml_metrics, MLMetricsCollector)

    def test_business_metrics_instance_exists(self):
        """Test that business_metrics global instance exists."""
        assert business_metrics is not None
        assert isinstance(business_metrics, BusinessMetricsCollector)

    def test_ml_metrics_can_track_operations(self):
        """Test that global ml_metrics instance can track operations."""
        # Should not raise an error
        with ml_metrics.track_training_duration("test_model", "test_problem"):
            pass

        ml_metrics.record_model_accuracy("test_id", "test_type", 0.85)

    def test_business_metrics_can_track_operations(self):
        """Test that global business_metrics instance can track operations."""
        # Should not raise an error
        business_metrics.set_active_users(100)
        business_metrics.increment_datasets_created("test_user")
