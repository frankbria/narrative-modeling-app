"""#661 AC3: erasure must delete a batch job's S3 input/output objects, not just its
Mongo row.

Mirrors ``test_erasure_model_artifact_localstack.py``: in mock mode ``_delete_s3``
issues no DeleteObject, so a real object could survive erasure while the manifest
reports success. This runs the real cascade against real S3 (LocalStack): it seeds a
BatchJob whose ``input_path``/``output_path`` point at real objects, erases the user,
and asserts both objects are gone from S3 and the doc from Mongo. Skips locally when
LocalStack is down; ``CI_REQUIRE_SERVICES`` turns that skip into a CI failure.
"""

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "erasure_batch_user"
MODEL_ID = "model_batch_erasetest01"
JOB_ID = "job_batch_erasetest01"


@pytest.fixture
def real_s3_env(monkeypatch, test_s3_bucket):
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
    from app.models.batch_job import BatchJob, JobStatus, JobType

    bucket = real_s3_env
    input_key = f"batch-jobs/{USER}/{MODEL_ID}/{JOB_ID}/input.csv"
    output_key = f"batch-jobs/{USER}/{MODEL_ID}/{JOB_ID}/results.csv"

    s3_client.put_object(Bucket=bucket, Key=input_key, Body=b"id,x\n1,2\n")
    s3_client.put_object(Bucket=bucket, Key=output_key, Body=b"id,prediction\n1,0\n")

    await BatchJob(
        job_id=JOB_ID,
        job_type=JobType.BATCH_PREDICTION,
        user_id=USER,
        config={"model_id": MODEL_ID, "output_format": "csv"},
        input_path=input_key,
        output_path=output_key,
        status=JobStatus.COMPLETED,
    ).insert()
    return {"bucket": bucket, "input_key": input_key, "output_key": output_key}


def _keys(s3_client, bucket) -> set[str]:
    return {o["Key"] for o in s3_client.list_objects_v2(Bucket=bucket).get("Contents", [])}


async def test_erasure_deletes_batch_job_s3_objects(seeded, s3_client):
    from app.models.batch_job import BatchJob
    from app.services.erasure_service import DatasetErasureService
    from app.utils.circuit_breaker import get_circuit_breaker

    bucket = seeded["bucket"]
    assert _keys(s3_client, bucket) == {seeded["input_key"], seeded["output_key"]}

    service = DatasetErasureService()
    assert not service.s3_service.is_mock_mode  # else the S3 asserts are vacuous
    get_circuit_breaker("s3").reset()

    manifest = await service.erase_user(USER, actor_id=USER, reason="gdpr_request")

    # Mongo: the job document is gone.
    assert await BatchJob.find(BatchJob.user_id == USER).count() == 0
    assert manifest.documents_deleted.get("batch_jobs") == 1

    # S3: both the input and the output objects are gone.
    assert _keys(s3_client, bucket) == set(), (
        "a batch-job S3 object survived erasure: "
        f"remaining={_keys(s3_client, bucket)} "
        f"deleted={manifest.s3_objects_deleted} failures={manifest.failures}"
    )
    assert manifest.failures == [], manifest.failures
    assert seeded["input_key"] in manifest.s3_objects_deleted
    assert seeded["output_key"] in manifest.s3_objects_deleted
