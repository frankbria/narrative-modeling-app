"""#661: the dataset cascade (erase_dataset -> _erase_models) must also delete a
model's batch jobs and their S3 objects.

BatchJob's model id lives inside the ``config`` dict, not a top-level field, so the
cascade queries the ``config.model_id`` dot-path. The localstack test covers the
``user_id`` sweep; this covers the dot-path branch hermetically (S3 mocked): it spies
on ``_delete_s3`` to prove the two batch keys are handed to the S3 core, and asserts
the BatchJob document is deleted.
"""

from unittest.mock import AsyncMock

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "erase_cascade_batch_user"
DATASET_ID = "dataset_cascade_batch01"
MODEL_ID = "model_cascade_batch01"


async def test_dataset_cascade_deletes_batch_job_s3_via_config_model_id(
    setup_database, monkeypatch
):
    from app.models.batch_job import BatchJob, JobStatus, JobType
    from app.models.dataset import DatasetMetadata
    from app.models.ml_model import MLModel
    from app.services.erasure_service import DatasetErasureService

    input_key = f"batch-jobs/{USER}/{MODEL_ID}/job1/input.csv"
    output_key = f"batch-jobs/{USER}/{MODEL_ID}/job1/results.csv"

    await DatasetMetadata(
        user_id=USER, dataset_id=DATASET_ID, filename="d.csv", original_filename="d.csv",
        file_type="csv", file_path=f"datasets/{USER}/{DATASET_ID}.csv",
        s3_url=f"s3://b/datasets/{USER}/{DATASET_ID}.csv", num_rows=1, num_columns=1,
    ).insert()
    await MLModel(
        user_id=USER, dataset_id=DATASET_ID, model_id=MODEL_ID, name="m",
        problem_type="classification", algorithm="rf", target_column="y",
        feature_names=["id"], cv_score=0.9, test_score=0.9, training_time=1.0,
        model_size=1, n_samples_train=1, n_features=1,
        model_path=f"s3://b/models/{USER}/{MODEL_ID}/model.pkl",
    ).insert()
    await BatchJob(
        job_id="job1", job_type=JobType.BATCH_PREDICTION, user_id=USER,
        config={"model_id": MODEL_ID, "output_format": "csv"},
        input_path=input_key, output_path=output_key, status=JobStatus.COMPLETED,
    ).insert()

    service = DatasetErasureService()
    # Isolate the batch-job branch: mock the model's own artifact delete, and capture
    # the S3 keys the cascade hands to the one delete core (S3 itself is not exercised).
    service.model_storage.delete_model = AsyncMock(return_value=None)
    deleted_keys: list[str] = []
    orig_delete_s3 = service._delete_s3

    async def spy(key, manifest):
        if key:
            deleted_keys.append(key)
        return await orig_delete_s3(key, manifest)

    monkeypatch.setattr(service, "_delete_s3", spy)

    await service.erase_dataset(DATASET_ID, USER, actor_id=USER, reason="gdpr_request")

    # The config.model_id dot-path matched: the batch job document is gone...
    assert await BatchJob.find(BatchJob.job_id == "job1").count() == 0
    # ...and both its S3 objects were routed to the delete core.
    assert input_key in deleted_keys
    assert output_key in deleted_keys
