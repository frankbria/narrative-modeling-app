"""
Integration test for the async AutoML training workflow (issue #75).

Exercises the real ``train_model_task`` against a real MongoDB ``TrainingJob`` and
a real ``AutoMLEngine`` training on a sample CSV. Only the S3 boundary is stubbed
(reading the dataset bytes and persisting the model artifact), since LocalStack is
not guaranteed to be running; everything else — the ML training, the model
comparison, the algorithm recommendations, and the job lifecycle — is real.
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.models.batch_job import JobStatus
from app.models.training_job import TrainingJob


@pytest.fixture
def sample_classification_csv() -> bytes:
    """A small but learnable binary-classification dataset as CSV bytes."""
    rng = np.random.RandomState(42)
    n = 150
    # Two separable-ish clusters so models actually learn something.
    x1 = np.concatenate([rng.randn(n) - 1.5, rng.randn(n) + 1.5])
    x2 = np.concatenate([rng.randn(n) - 1.0, rng.randn(n) + 1.0])
    cat = rng.choice(["A", "B", "C"], size=2 * n)
    target = np.array([0] * n + [1] * n)
    df = pd.DataFrame({"x1": x1, "x2": x2, "category": cat, "target": target})
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_train_workflow_completes_with_comparison(
    setup_database, sample_classification_csv
):
    """POST-style training task trains a real model and records full results."""
    from app.api.routes.model_training import TrainModelRequest, train_model_task

    model_id = "model_integration_workflow"
    user_id = "integration_user"

    # Pending job, as POST /ml/train would create.
    job = TrainingJob(
        model_id=model_id,
        user_id=user_id,
        dataset_id="dataset_integration",
        target_column="target",
    )
    await job.insert()

    user_data = MagicMock()
    user_data.s3_url = "s3://bucket/datasets/integration/data.csv"
    user_data.file_type = "csv"
    user_data.filename = "data.csv"

    request = TrainModelRequest(
        dataset_id="dataset_integration",
        target_column="target",
        training_config={"max_models": 3, "cv_folds": 3},
    )

    # Stub only the S3 boundaries: dataset read and model artifact write.
    saved_model = MagicMock(model_id=model_id)

    try:
        with patch(
            "app.api.routes.model_training.get_file_from_s3",
            new_callable=AsyncMock,
            return_value=sample_classification_csv,
        ), patch(
            "app.services.model_storage.ModelStorageService.save_model",
            new_callable=AsyncMock,
            return_value=saved_model,
        ):
            await train_model_task(user_data, request, user_id, model_id)

        refreshed = await TrainingJob.find_one(TrainingJob.model_id == model_id)

        # Job reached COMPLETED with a real trained best model.
        assert refreshed.status == JobStatus.COMPLETED
        assert refreshed.best_algorithm is not None
        assert refreshed.best_model_id == model_id

        # Model comparison populated and ranked by CV score (descending).
        assert len(refreshed.model_comparison) >= 1
        cv_scores = [
            row.cv_score
            for row in refreshed.model_comparison
            if row.cv_score is not None
        ]
        assert cv_scores == sorted(cv_scores, reverse=True)

        # Plain-language explanation and algorithm recommendations present.
        assert refreshed.best_model_explanation
        assert refreshed.best_algorithm in refreshed.best_model_explanation
        assert len(refreshed.algorithm_recommendations) >= 1
        assert "algorithm_name" in refreshed.algorithm_recommendations[0]

        # Progress shows full completion.
        assert refreshed.progress.fraction == 1.0

        # Live monitoring (issue #76): logs were recorded throughout the run...
        assert len(refreshed.logs) >= 3
        messages = [entry.message for entry in refreshed.logs]
        assert any("Training task started" in m for m in messages)
        assert any("Dataset downloaded" in m for m in messages)
        assert any("Training completed" in m for m in messages)

        # ...covering every pipeline stage...
        stages_seen = {entry.stage for entry in refreshed.logs if entry.stage}
        assert {"preprocessing", "training", "finalizing"} <= stages_seen
        assert refreshed.progress.current_stage == "finalizing"

        # ...with one per-candidate completion log per comparison row (these are
        # the incremental model_comparison appends, later replaced by the final
        # ranked list on completion).
        candidate_logs = [
            entry
            for entry in refreshed.logs
            if entry.stage == "training" and "cv_score" in entry.message
        ]
        assert len(candidate_logs) == len(refreshed.model_comparison)
    finally:
        await job.delete()
