"""#497 AC4: erasure must delete a trained model's S3 artifact, not just its Mongo row.

The Mongo/PII zero-residual guarantee is covered hermetically in
``test_erasure_cascade.py`` (S3 forced to mock mode). What that test cannot prove
is the *live* S3 delete: in mock mode ``delete_model`` issues no DeleteObject, so
a real object could survive erasure while the manifest still reports success.

This runs the real cascade against a real S3 (LocalStack): it seeds a dataset
across both id-spaces → a transformation (``DatasetVersion``) → a trained model
with a real artifact object in S3, erases, and asserts **nothing** remains in
Mongo *or* S3. Skips locally when LocalStack is down; ``CI_REQUIRE_SERVICES``
turns that skip into a failure in CI.
"""

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "erasure_model_user"
DATASET_ID = "dataset_model_erasetest01"
MODEL_ID = "model_erasetest01"


@pytest.fixture
def real_s3_env(monkeypatch, test_s3_bucket):
    """Point the app's S3 helpers AND S3Service at LocalStack.

    S3Service treats credentials starting with ``test-`` as mock mode; the
    LocalStack placeholders are ``test``/``test`` (no dash), so it goes live.

    Point the app at the *same* endpoint the ``s3_client`` fixture seeds through
    (``S3_ENDPOINT_URL``, default LocalStack), so the delete and the seeded
    object never land on different services in a non-localhost CI layout.
    """
    import os

    monkeypatch.setenv(
        "AWS_ENDPOINT_URL", os.getenv("S3_ENDPOINT_URL", "http://localhost:4566")
    )
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_BUCKET_NAME", test_s3_bucket)
    monkeypatch.setenv("AWS_S3_BUCKET", test_s3_bucket)
    monkeypatch.setenv("S3_BUCKET_NAME", test_s3_bucket)
    return test_s3_bucket


@pytest_asyncio.fixture
async def seeded(setup_database, real_s3_env, s3_client):
    """Seed both id-spaces + a transformation + a trained model with a live S3 artifact."""
    from app.models.dataset import DatasetMetadata
    from app.models.ml_model import MLModel
    from app.models.training_job import TrainingJob
    from app.models.user_data import UserData
    from app.models.version import DatasetVersion

    bucket = real_s3_env
    dataset_key = f"datasets/{USER}/{DATASET_ID}_d.csv"
    model_key = f"models/{USER}/{MODEL_ID}/model.pkl"
    dataset_url = f"s3://{bucket}/{dataset_key}"

    # Real objects in S3: the dataset source and the model artifact.
    s3_client.put_object(Bucket=bucket, Key=dataset_key, Body=b"id,y\n1,0\n2,1\n")
    s3_client.put_object(Bucket=bucket, Key=model_key, Body=b"\x80\x04pickled-bytes")

    # String id-space parent + its dual-written UserData twin (shared s3_url).
    await DatasetMetadata(
        user_id=USER, dataset_id=DATASET_ID, filename="d.csv", original_filename="d.csv",
        file_type="csv", file_path=dataset_key, s3_url=dataset_url, num_rows=2, num_columns=2,
    ).insert()
    await UserData(
        user_id=USER, filename="d.csv", original_filename="d.csv", s3_url=dataset_url,
        num_rows=2, num_columns=2, data_schema=[], contains_pii=False,
    ).insert()
    # A transformation applied to the dataset.
    await DatasetVersion(
        version_id="v1", dataset_id=DATASET_ID, version_number=1, user_id=USER,
        content_hash="h", file_size=1, file_path="p", s3_url="s3://b/p", num_rows=2,
        num_columns=2, schema_hash="sh", created_by=USER,
    ).insert()
    # A trained model + its training job, artifact at model_key.
    await MLModel(
        user_id=USER, dataset_id=DATASET_ID, model_id=MODEL_ID, name="m",
        problem_type="classification", algorithm="rf", target_column="y",
        feature_names=["id"], cv_score=0.9, test_score=0.9, training_time=1.0,
        model_size=len(b"\x80\x04pickled-bytes"), n_samples_train=2, n_features=1,
        model_path=f"s3://{bucket}/{model_key}",
    ).insert()
    await TrainingJob(
        model_id=MODEL_ID, user_id=USER, dataset_id=DATASET_ID, target_column="y",
    ).insert()
    return {"bucket": bucket, "dataset_key": dataset_key, "model_key": model_key}


def _keys(s3_client, bucket) -> set[str]:
    return {o["Key"] for o in s3_client.list_objects_v2(Bucket=bucket).get("Contents", [])}


async def test_erasure_deletes_trained_model_artifact_from_s3(seeded, s3_client):
    from app.models.dataset import DatasetMetadata
    from app.models.ml_model import MLModel
    from app.models.training_job import TrainingJob
    from app.models.user_data import UserData
    from app.models.version import DatasetVersion
    from app.services.erasure_service import DatasetErasureService
    from app.utils.circuit_breaker import get_circuit_breaker

    bucket = seeded["bucket"]
    assert _keys(s3_client, bucket) == {seeded["dataset_key"], seeded["model_key"]}

    # A fresh service instance picks up the LocalStack env; it must be live, or
    # the S3 assertions below are vacuous (mock mode issues no DeleteObject).
    service = DatasetErasureService()
    assert not service.s3_service.is_mock_mode
    assert not service.model_storage.s3_service.is_mock_mode
    # The "s3" breaker is a process-wide singleton; a prior integration test can
    # leave it open, which erasure would swallow into the manifest as a failure.
    get_circuit_breaker("s3").reset()

    manifest = await service.erase_dataset(DATASET_ID, USER, actor_id=USER, reason="gdpr_request")

    # Mongo: nothing survives in any collection this cascade touches.
    assert await DatasetMetadata.find(DatasetMetadata.dataset_id == DATASET_ID).count() == 0
    assert await UserData.find(UserData.user_id == USER).count() == 0
    assert await MLModel.find(MLModel.dataset_id == DATASET_ID).count() == 0
    assert await TrainingJob.find(TrainingJob.dataset_id == DATASET_ID).count() == 0
    assert await DatasetVersion.find(DatasetVersion.dataset_id == DATASET_ID).count() == 0

    # S3: the dataset source AND the model artifact are gone.
    assert _keys(s3_client, bucket) == set(), (
        "an S3 object survived erasure: "
        f"remaining={_keys(s3_client, bucket)} "
        f"s3_objects_deleted={manifest.s3_objects_deleted} failures={manifest.failures}"
    )
    # The manifest reported the deletes honestly (AC3): no failures, model row counted.
    assert manifest.failures == [], manifest.failures
    assert manifest.documents_deleted.get("ml_models") == 1
    assert seeded["model_key"] not in _keys(s3_client, bucket)
