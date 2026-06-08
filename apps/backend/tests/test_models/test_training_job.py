"""
Unit tests for the TrainingJob document lifecycle helpers.

These exercise pure in-memory state transitions (no DB insert), so they run
without MongoDB.
"""

import pytest

from app.models.training_job import (
    TrainingJob,
    TrainingProgress,
    ModelComparisonEntry,
)
from app.models.batch_job import JobStatus

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("beanie_models_initialized")]


def _job() -> TrainingJob:
    return TrainingJob(
        model_id="model_test_1",
        user_id="user_1",
        dataset_id="dataset_1",
        target_column="target",
    )


class TestTrainingProgress:
    def test_fraction_zero_when_total_unknown(self):
        assert TrainingProgress().fraction == 0.0

    def test_fraction_and_percentage(self):
        p = TrainingProgress(completed_algorithms=2, total_algorithms=4)
        assert p.fraction == 0.5
        assert p.percentage == 50.0

    def test_fraction_capped_at_one(self):
        p = TrainingProgress(completed_algorithms=5, total_algorithms=4)
        assert p.fraction == 1.0


class TestTrainingJobLifecycle:
    def test_defaults_to_pending(self):
        assert _job().status == JobStatus.PENDING

    def test_mark_started(self):
        job = _job()
        job.mark_started(total_algorithms=5)
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None
        assert job.progress.total_algorithms == 5
        assert job.progress.completed_algorithms == 0

    def test_update_progress_partial(self):
        job = _job()
        job.mark_started(total_algorithms=5)
        job.update_progress(completed_algorithms=2, current_algorithm="XGBoost")
        assert job.progress.completed_algorithms == 2
        assert job.progress.current_algorithm == "XGBoost"
        assert job.progress.total_algorithms == 5  # unchanged

    def test_mark_completed_attaches_results(self):
        job = _job()
        job.mark_started(total_algorithms=3)
        comparison = [ModelComparisonEntry(algorithm="XGBoost", cv_score=0.9)]
        job.mark_completed(
            best_model_id="model_test_1",
            best_algorithm="XGBoost",
            best_model_explanation="because",
            model_comparison=comparison,
            algorithm_recommendations=[{"algorithm_name": "XGBoost"}],
            metrics={"cv_score": 0.9},
        )
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert job.best_algorithm == "XGBoost"
        assert job.best_model_explanation == "because"
        assert job.model_comparison[0].algorithm == "XGBoost"
        assert job.metrics["cv_score"] == 0.9
        # Progress is forced to 100% on completion.
        assert job.progress.completed_algorithms == job.progress.total_algorithms
        assert job.progress.current_algorithm is None

    def test_mark_failed_records_error(self):
        job = _job()
        job.mark_started(total_algorithms=3)
        job.mark_failed("boom")
        assert job.status == JobStatus.FAILED
        assert job.error == "boom"
        assert job.completed_at is not None
