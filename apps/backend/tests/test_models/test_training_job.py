"""
Unit tests for the TrainingJob document lifecycle helpers.

These exercise pure in-memory state transitions (no DB insert), so they run
without MongoDB.
"""

from datetime import timedelta

import pytest

from app.models.batch_job import JobStatus
from app.models.training_job import (
    ModelComparisonEntry,
    TrainingJob,
    TrainingLogEntry,
    TrainingProgress,
    _utcnow,
)

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


class TestTrainingLogEntry:
    def test_defaults(self):
        entry = TrainingLogEntry(level="info", message="hello")
        assert entry.level == "info"
        assert entry.message == "hello"
        assert entry.stage is None
        assert entry.timestamp is not None

    def test_rejects_unknown_level(self):
        with pytest.raises(Exception):
            TrainingLogEntry(level="debug", message="nope")


class TestTrainingJobLogs:
    def test_logs_default_empty(self):
        assert _job().logs == []

    def test_add_log_appends_and_bumps_updated_at(self):
        job = _job()
        before = job.updated_at
        job.add_log("info", "Training started", stage="training")
        assert len(job.logs) == 1
        entry = job.logs[0]
        assert entry.level == "info"
        assert entry.message == "Training started"
        assert entry.stage == "training"
        assert job.updated_at >= before

    def test_add_log_without_stage(self):
        job = _job()
        job.add_log("error", "boom")
        assert job.logs[0].stage is None
        assert job.logs[0].level == "error"


class TestTrainingJobCancellation:
    def test_cancellation_requested_defaults_false(self):
        assert _job().cancellation_requested is False

    def test_mark_cancelled(self):
        job = _job()
        job.mark_started(total_algorithms=3)
        job.update_progress(completed_algorithms=1, current_algorithm="XGBoost")
        job.progress.current_stage = "training"
        job.mark_cancelled()
        assert job.status == JobStatus.CANCELLED
        assert job.completed_at is not None
        assert job.updated_at == job.completed_at
        assert job.progress.current_algorithm is None
        # A cancelled job is not in any pipeline stage.
        assert job.progress.current_stage is None


class TestTrainingProgressStage:
    def test_current_stage_defaults_none(self):
        assert TrainingProgress().current_stage is None

    def test_current_stage_settable(self):
        p = TrainingProgress(current_stage="preprocessing")
        assert p.current_stage == "preprocessing"


class TestTrainingJobTiming:
    def test_elapsed_none_before_start(self):
        assert _job().elapsed_seconds is None

    def test_elapsed_while_running(self):
        job = _job()
        job.mark_started(total_algorithms=4)
        job.started_at = _utcnow() - timedelta(seconds=10)
        elapsed = job.elapsed_seconds
        assert elapsed is not None
        assert 9.0 <= elapsed <= 12.0

    def test_elapsed_frozen_after_completion(self):
        job = _job()
        job.mark_started(total_algorithms=4)
        job.mark_completed()
        job.started_at = job.completed_at - timedelta(seconds=42)
        assert job.elapsed_seconds == pytest.approx(42.0)

    def test_estimated_remaining_none_when_not_started(self):
        assert _job().estimated_remaining_seconds is None

    def test_estimated_remaining_none_at_zero_progress(self):
        job = _job()
        job.mark_started(total_algorithms=4)
        assert job.estimated_remaining_seconds is None

    def test_estimated_remaining_mid_run(self):
        job = _job()
        job.mark_started(total_algorithms=4)
        job.started_at = _utcnow() - timedelta(seconds=30)
        job.update_progress(completed_algorithms=2)  # fraction = 0.5
        remaining = job.estimated_remaining_seconds
        # elapsed ~30s at 50% -> ~30s remaining
        assert remaining == pytest.approx(30.0, abs=3.0)

    def test_estimated_remaining_none_when_terminal(self):
        job = _job()
        job.mark_started(total_algorithms=4)
        job.update_progress(completed_algorithms=2)
        job.mark_failed("boom")
        assert job.estimated_remaining_seconds is None
