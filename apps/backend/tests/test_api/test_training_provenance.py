"""#801: training writes down what the model report had to call "not recorded".

A real `train_model_task` with a real `AutoMLEngine` on a small learnable dataset and
real MongoDB documents. Only the S3 boundary is stubbed: the dataset read, and
`save_model`, whose arguments are what the model is stored with.
"""
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.models.dataset import DatasetMetadata
from app.models.training_job import TrainingJob
from app.models.version import DatasetVersion

pytestmark = pytest.mark.asyncio

USER = "provenance_user_801"
S3_URL = f"s3://test-bucket/datasets/{USER}/data.csv"


def _csv() -> bytes:
    rng = np.random.RandomState(801)
    n = 60
    frame = pd.DataFrame({
        "x1": np.concatenate([rng.randn(n) - 2, rng.randn(n) + 2]),
        "x2": np.concatenate([rng.randn(n) - 1, rng.randn(n) + 1]),
        "target": [0] * n + [1] * n,
    })
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False)
    return buffer.getvalue().encode()


async def _train(model_id: str, content: bytes) -> dict:
    """Run the task and return the metadata the model was saved with."""
    from app.api.routes.model_training import TrainModelRequest, train_model_task

    await TrainingJob(
        model_id=model_id, user_id=USER, dataset_id="dataset_801", target_column="target"
    ).insert()
    user_data = MagicMock(s3_url=S3_URL, file_type="csv", filename="data.csv", user_id=USER)
    save_model = AsyncMock(return_value=MagicMock(model_id=model_id))
    with (
        patch("app.services.s3_service.S3Service.download_file_bytes", AsyncMock(return_value=content)),
        patch("app.services.model_storage.ModelStorageService.save_model", save_model),
    ):
        await train_model_task(
            user_data,
            TrainModelRequest(
                dataset_id="dataset_801", target_column="target",
                training_config={"max_models": 1, "cv_folds": 2},
            ),
            USER, model_id,
        )
    save_model.assert_awaited_once()
    return save_model.await_args.args[4]


async def _version_of(content: bytes) -> DatasetVersion:
    """The dataset's twin and a version holding exactly these bytes."""
    await DatasetMetadata(
        user_id=USER, dataset_id="dataset_meta_801", filename="data.csv",
        original_filename="data.csv", file_type="csv", file_path=f"datasets/{USER}/data.csv",
        s3_url=S3_URL, num_rows=120, num_columns=3,
    ).insert()
    return await DatasetVersion(
        version_id="version-801", dataset_id="dataset_meta_801", version_number=1, user_id=USER,
        content_hash=DatasetVersion.compute_content_hash(content), file_size=len(content),
        file_path=f"datasets/{USER}/data.csv", s3_url=S3_URL, num_rows=120, num_columns=3,
        columns=["x1", "x2", "target"], schema_hash="s", is_base_version=True, created_by=USER,
    ).insert()


async def test_the_seed_and_the_winners_hyperparameters_are_saved_with_the_model(setup_database):
    metadata = await _train("model_801_settings", _csv())

    config = metadata["training_config"]
    assert config["random_seed"] == 42, "the engine's effective seed, written down"
    assert isinstance(config["winner_hyperparameters"], dict)
    json.dumps(config["winner_hyperparameters"])  # storable as it is


async def test_the_version_holding_the_bytes_that_were_trained_on_is_recorded(setup_database):
    """`MLModel.dataset_version_id` was resolved by querying the version id-space with a
    `UserData` id, so it never matched. The version is now the one whose content is
    byte for byte what training read."""
    content = _csv()
    version = await _version_of(content)

    metadata = await _train("model_801_version", content)

    assert metadata["dataset_version_id"] == version.version_id
    assert (await DatasetVersion.get(version.id)).used_in_training == ["model_801_version"]


async def test_a_version_of_different_content_is_not_claimed(setup_database):
    """The dataset has a version, but not of these bytes (it was transformed since, or
    the version predates them). Naming it would be the guess the report refuses."""
    await _version_of(b"x1,x2,target\n0,0,0\n")

    metadata = await _train("model_801_other", _csv())

    assert metadata.get("dataset_version_id") is None


async def test_a_dataset_with_no_twin_trains_and_records_no_version(setup_database):
    metadata = await _train("model_801_untracked", _csv())

    assert metadata.get("dataset_version_id") is None
