"""Training-job and monitoring lists name the dataset instead of its raw id (#1175)."""
import pytest

from app.models.user_data import UserData
from tests.test_api.test_model_training import _insert_job
from tests.test_api.test_monitoring import TEST_USER, _make_model


async def _dataset(filename: str, user_id: str = TEST_USER) -> UserData:
    doc = UserData(
        user_id=user_id,
        filename=filename,
        original_filename=filename,
        s3_url=f"s3://test-bucket/datasets/{user_id}/{filename}",
        num_rows=10,
        num_columns=2,
        data_schema=[],
    )
    await doc.insert()
    return doc


@pytest.mark.asyncio
async def test_training_jobs_carry_the_dataset_filename(async_authorized_client, setup_database):
    dataset = await _dataset("churn.csv")
    job = await _insert_job("named_job", dataset_id=str(dataset.id), user_id=TEST_USER)
    orphan = await _insert_job("orphan_job", dataset_id="dataset_123", user_id=TEST_USER)
    try:
        resp = await async_authorized_client.get("/api/v1/ml/jobs")
        assert resp.status_code == 200
        names = {j["model_id"]: j["dataset_name"] for j in resp.json()["jobs"]}
        assert names == {"named_job": "churn.csv", "orphan_job": None}
    finally:
        await job.delete()
        await orphan.delete()
        await dataset.delete()


@pytest.mark.asyncio
async def test_a_foreign_dataset_is_not_named(async_authorized_client, setup_database):
    foreign = await _dataset("secret.csv", user_id="someone_else")
    job = await _insert_job("foreign_job", dataset_id=str(foreign.id), user_id=TEST_USER)
    try:
        resp = await async_authorized_client.get("/api/v1/ml/jobs")
        assert resp.json()["jobs"][0]["dataset_name"] is None
    finally:
        await job.delete()
        await foreign.delete()


@pytest.mark.asyncio
async def test_overview_rows_describe_the_model(async_authorized_client, setup_database):
    dataset = await _dataset("sales.csv")
    model = _make_model(model_id="named_model")
    model.dataset_id = str(dataset.id)
    await model.insert()
    resp = await async_authorized_client.get("/api/v1/monitoring/overview")
    assert resp.status_code == 200
    row = resp.json()["models"][0]
    assert (row["dataset_name"], row["algorithm"], row["target_column"]) == (
        "sales.csv",
        "Random Forest",
        "target",
    )
    assert row["created_at"]
