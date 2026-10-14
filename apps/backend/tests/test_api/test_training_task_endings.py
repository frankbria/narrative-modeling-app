"""How a training task ends, and what it writes when it does (#842).

`train_model_task` re-raises nothing: every ending is recorded on the `TrainingJob`,
or deliberately not recorded. These are the endings the gate's suite did not reach
before the task was split into steps: a cancellation noticed by the engine, a task
with no tracking job at all, and the two payloads that are built best-effort.
"""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes import model_training
from app.api.routes.model_training import TrainModelRequest, train_model_task
from app.models.batch_job import JobStatus
from app.models.training_job import TrainingJob
from app.services.model_training.automl_engine import TrainingCancelledError

CSV = b"a,target\n1,0\n2,1\n"
REQUEST = TrainModelRequest(dataset_id="dataset_123", target_column="target")


def _dataset() -> MagicMock:
    return MagicMock(
        id="dataset_123", user_id="test_user", file_type="csv",
        s3_url="s3://test-bucket/uploads/test_user/test_data.csv",
    )


async def _job(model_id: str) -> TrainingJob:
    job = TrainingJob(model_id=model_id, user_id="test_user", dataset_id="dataset_123", target_column="target")
    await job.insert()
    return job


async def _run_task(model_id: str, engine_run) -> None:
    """The task with the download and the engine replaced; everything else is real."""
    with (
        patch("app.services.s3_service.S3Service.download_file_bytes", new_callable=AsyncMock, return_value=CSV),
        patch("app.api.routes.model_training.AutoMLEngine") as engine_cls,
    ):
        engine_cls.return_value.run = engine_run
        await train_model_task(_dataset(), REQUEST, "test_user", model_id, wall_clock_seconds=30)


async def _cancelled_by_the_engine(*_args, **_kwargs):
    raise TrainingCancelledError("Training cancelled before RandomForest")


async def test_a_cancellation_the_engine_noticed_is_recorded_as_cancelled(setup_database):
    await _job("model_cancelled")

    await _run_task("model_cancelled", _cancelled_by_the_engine)

    job = await TrainingJob.find_one(TrainingJob.model_id == "model_cancelled")
    assert job.status == JobStatus.CANCELLED
    assert job.logs[-1].message == "Training cancelled by user"
    assert job.error is None


async def test_a_cancellation_that_cannot_be_recorded_does_not_escape_the_task(setup_database, caplog):
    await _job("model_cancel_unrecorded")

    with (
        patch.object(TrainingJob, "mark_cancelled", side_effect=RuntimeError("database is down")),
        caplog.at_level(logging.ERROR, logger=model_training.logger.name),
    ):
        await _run_task("model_cancel_unrecorded", _cancelled_by_the_engine)  # no raise

    assert "Failed to persist CANCELLED status for model_cancel_unrecorded" in caplog.text
    job = await TrainingJob.find_one(TrainingJob.model_id == "model_cancel_unrecorded")
    assert job.status == JobStatus.RUNNING, "nothing was written over the row"


@pytest.mark.parametrize(
    "ending",
    [TrainingCancelledError("cancelled"), ValueError("no usable columns")],
    ids=["cancelled", "failed"],
)
async def test_a_task_with_no_tracking_job_ends_quietly(setup_database, ending):
    # A job lookup that FAILS is best effort: the run still trains, and its reporting
    # and its ending have nothing to write to. (A lookup that works and finds no row
    # means the job was erased, and the task does not run: #945, in
    # test_training_job_erased_mid_run.py.)
    ran = []

    async def reports_then_ends(*_args, progress_callback, event_callback, cancel_check, **_kwargs):
        ran.append(True)
        await progress_callback(0, 1, "RandomForest")
        assert await cancel_check() is False
        raise ending

    with patch.object(model_training, "_tracking_job", AsyncMock(return_value=None)):
        await _run_task("model_without_a_job", reports_then_ends)  # no raise

    assert ran, "the untracked run trained"
    assert await TrainingJob.find_one(TrainingJob.model_id == "model_without_a_job") is None


def _result(**overrides):
    base = {
        "y_test": [0, 1], "y_pred": [0, 1], "y_proba": None, "class_labels": ["0", "1"],
        "x_test": [[1], [2]], "feature_names": ["a"], "shap_global": object(),
        "problem_type": SimpleNamespace(value="binary_classification"),
    }
    return SimpleNamespace(**{**base, **overrides})


def test_a_payload_that_cannot_be_built_is_left_out_not_fatal(caplog):
    # Both are for the dashboards. Training has succeeded by the time they are built.
    broken = RuntimeError("shape mismatch")
    with (
        patch("app.api.routes.model_training.build_evaluation_payload", side_effect=broken),
        patch("app.api.routes.model_training.build_shap_payload", side_effect=broken),
        caplog.at_level(logging.WARNING, logger=model_training.logger.name),
    ):
        assert model_training._evaluation_payload(_result(), "model_x") is None
        assert model_training._shap_payload(_result(), "model_x") is None

    assert "Failed to build evaluation payload for model_x" in caplog.text
    assert "Failed to build SHAP payload for model_x" in caplog.text


@pytest.mark.parametrize("missing", ["y_test", "y_pred"])
def test_no_evaluation_payload_without_held_out_predictions(missing):
    with patch("app.api.routes.model_training.build_evaluation_payload") as build:
        assert model_training._evaluation_payload(_result(**{missing: None}), "model_x") is None
    build.assert_not_called()


def test_the_requests_feature_choices_reach_the_engineers_config():
    chosen = TrainModelRequest(
        dataset_id="dataset_123", target_column="target",
        feature_config={"keep_columns": ["order_id"], "exclude_columns": ["notes"]},
    )

    config = model_training._feature_config(chosen)

    assert config.keep_columns == ["order_id"]
    assert config.exclude_columns == ["notes"]
    assert model_training._feature_config(REQUEST) is None
