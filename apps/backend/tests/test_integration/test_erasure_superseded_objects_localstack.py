"""#525: erasure must delete the superseded current-file objects a dataset moves
through as transformations rewrite it — not just the current one.

Each transformation writes a new ``transformed/...`` object and repoints s3_url at
it; the previous object is then referenced by nothing (DatasetVersion tracks a
separate ``versions/`` copy). record_new_file now records each superseded url so
erasure can reach it. Proven against real S3 (LocalStack).
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "superseded_erase_user"
DATASET_ID = "ds_superseded_erasetest"


@pytest.fixture
def real_s3_env(monkeypatch, test_s3_bucket):
    import os

    monkeypatch.setenv("AWS_ENDPOINT_URL", os.getenv("S3_ENDPOINT_URL", "http://localhost:4566"))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    for v in ("AWS_BUCKET_NAME", "AWS_S3_BUCKET", "S3_BUCKET_NAME"):
        monkeypatch.setenv(v, test_s3_bucket)
    return test_s3_bucket


async def test_erasure_deletes_every_superseded_transformation_object(
    setup_database, real_s3_env, s3_client
):
    from app.models.dataset import DatasetMetadata
    from app.models.user_data import UserData
    from app.services.dataset_link import record_new_file
    from app.services.erasure_service import DatasetErasureService
    from app.utils.circuit_breaker import get_circuit_breaker

    bucket = real_s3_env
    k0 = f"datasets/{USER}/{DATASET_ID}_orig.csv"        # original upload
    k1 = f"transformed/{USER}/{DATASET_ID}_t1.parquet"   # after transform 1 (superseded)
    k2 = f"transformed/{USER}/{DATASET_ID}_t2.parquet"   # current after transform 2
    for k in (k0, k1, k2):
        s3_client.put_object(Bucket=bucket, Key=k, Body=b"data")

    def url(k: str) -> str:
        return f"s3://{bucket}/{k}"

    meta = await DatasetMetadata(
        user_id=USER, dataset_id=DATASET_ID, filename="d.csv", original_filename="d.csv",
        file_type="csv", file_path=url(k0), s3_url=url(k0), num_rows=1, num_columns=1,
    ).insert()
    await UserData(
        user_id=USER, filename="d.csv", original_filename="d.csv", s3_url=url(k0),
        file_path=url(k0), num_rows=1, num_columns=1, data_schema=[],
    ).insert()

    # Two transformations move the current file: k0 -> k1 -> k2.
    await record_new_file(meta, url(k1))
    await record_new_file(meta, url(k2))

    meta = await DatasetMetadata.find_one(DatasetMetadata.dataset_id == DATASET_ID)
    tracked = set(meta.superseded_s3_urls or []) | {meta.source_s3_url}
    assert url(k0) in tracked and url(k1) in tracked, tracked
    assert meta.s3_url == url(k2)

    get_circuit_breaker("s3").reset()
    manifest = await DatasetErasureService().erase_dataset(
        DATASET_ID, USER, actor_id=USER, reason="gdpr_request"
    )

    remaining = {o["Key"] for o in s3_client.list_objects_v2(Bucket=bucket).get("Contents", [])}
    assert not ({k0, k1, k2} & remaining), (
        f"a superseded/current object survived erasure: remaining={remaining} "
        f"failures={manifest.failures}"
    )
