# apps/backend/app/services/metrics_collector.py
"""
Metrics collector for ML operations and business metrics.

Tracks:
ML Metrics:
- Training duration histogram
- Prediction latency histogram
- Model accuracy gauge (updated after training)
- Dataset size histogram

Business Metrics:
- Active users gauge (from auth)
- Datasets created counter
- Models trained counter
- Predictions made counter

Usage:
    from app.services.metrics_collector import ml_metrics, business_metrics

    # Track ML operations
    with ml_metrics.track_training_duration(model_type="random_forest"):
        # Training code
        pass

    ml_metrics.record_model_accuracy(
        model_id="model_123",
        model_type="random_forest",
        accuracy=0.95
    )

    # Track business metrics
    business_metrics.increment_datasets_created(user_id="user_123")
    business_metrics.increment_predictions_made(model_id="model_123")
"""

import time
from contextlib import contextmanager
from typing import Optional
from prometheus_client import Histogram, Gauge, Counter
from app.middleware.metrics import metrics_registry


class MLMetricsCollector:
    """Collector for machine learning operation metrics."""

    def __init__(self, registry):
        # Training duration histogram
        self.training_duration = Histogram(
            name="ml_training_duration_seconds",
            documentation="ML model training duration in seconds",
            labelnames=["model_type", "problem_type"],
            buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0),
            registry=registry,
        )

        # Prediction latency histogram
        self.prediction_latency = Histogram(
            name="ml_prediction_latency_seconds",
            documentation="ML model prediction latency in seconds",
            labelnames=["model_type", "model_id"],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
            registry=registry,
        )

        # Model accuracy gauge
        self.model_accuracy = Gauge(
            name="ml_model_accuracy",
            documentation="ML model accuracy score",
            labelnames=["model_id", "model_type", "metric_name"],
            registry=registry,
        )

        # Dataset size histogram
        self.dataset_size = Histogram(
            name="ml_dataset_size_rows",
            documentation="Dataset size in number of rows",
            labelnames=["dataset_id"],
            buckets=(100, 500, 1000, 5000, 10000, 50000, 100000, 500000),
            registry=registry,
        )

    @contextmanager
    def track_training_duration(
        self, model_type: str, problem_type: str = "unknown"
    ):
        """
        Context manager to track training duration.

        Args:
            model_type: Type of model (e.g., "random_forest", "logistic_regression")
            problem_type: Type of problem (e.g., "classification", "regression")

        Usage:
            with ml_metrics.track_training_duration("random_forest", "classification"):
                # Training code here
                pass
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.training_duration.labels(
                model_type=model_type, problem_type=problem_type
            ).observe(duration)

    @contextmanager
    def track_prediction_latency(self, model_type: str, model_id: str):
        """
        Context manager to track prediction latency.

        Args:
            model_type: Type of model
            model_id: Unique model identifier

        Usage:
            with ml_metrics.track_prediction_latency("random_forest", "model_123"):
                # Prediction code here
                pass
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.prediction_latency.labels(
                model_type=model_type, model_id=model_id
            ).observe(duration)

    def record_model_accuracy(
        self,
        model_id: str,
        model_type: str,
        accuracy: float,
        metric_name: str = "accuracy",
    ):
        """
        Record model accuracy or other performance metrics.

        Args:
            model_id: Unique model identifier
            model_type: Type of model
            accuracy: Accuracy score (0.0 to 1.0)
            metric_name: Name of the metric (default: "accuracy")
        """
        self.model_accuracy.labels(
            model_id=model_id, model_type=model_type, metric_name=metric_name
        ).set(accuracy)

    def record_dataset_size(self, dataset_id: str, num_rows: int):
        """
        Record dataset size.

        Args:
            dataset_id: Unique dataset identifier
            num_rows: Number of rows in the dataset
        """
        self.dataset_size.labels(dataset_id=dataset_id).observe(num_rows)


class BusinessMetricsCollector:
    """Collector for business metrics."""

    def __init__(self, registry):
        # Active users gauge
        self.active_users = Gauge(
            name="business_active_users",
            documentation="Number of active users",
            labelnames=["time_window"],
            registry=registry,
        )

        # Datasets created counter
        self.datasets_created = Counter(
            name="business_datasets_created_total",
            documentation="Total number of datasets created",
            labelnames=["user_id"],
            registry=registry,
        )

        # Models trained counter
        self.models_trained = Counter(
            name="business_models_trained_total",
            documentation="Total number of models trained",
            labelnames=["model_type", "user_id"],
            registry=registry,
        )

        # Predictions made counter
        self.predictions_made = Counter(
            name="business_predictions_made_total",
            documentation="Total number of predictions made",
            labelnames=["model_id"],
            registry=registry,
        )

    def set_active_users(self, count: int, time_window: str = "day"):
        """
        Set the number of active users.

        Args:
            count: Number of active users
            time_window: Time window for active users (day, week, month)
        """
        self.active_users.labels(time_window=time_window).set(count)

    def increment_datasets_created(self, user_id: str):
        """
        Increment the datasets created counter.

        Args:
            user_id: User who created the dataset
        """
        self.datasets_created.labels(user_id=user_id).inc()

    def increment_models_trained(self, model_type: str, user_id: str):
        """
        Increment the models trained counter.

        Args:
            model_type: Type of model trained
            user_id: User who trained the model
        """
        self.models_trained.labels(model_type=model_type, user_id=user_id).inc()

    def increment_predictions_made(self, model_id: str):
        """
        Increment the predictions made counter.

        Args:
            model_id: Model used for prediction
        """
        self.predictions_made.labels(model_id=model_id).inc()


# Global instances
ml_metrics = MLMetricsCollector(metrics_registry)
business_metrics = BusinessMetricsCollector(metrics_registry)
