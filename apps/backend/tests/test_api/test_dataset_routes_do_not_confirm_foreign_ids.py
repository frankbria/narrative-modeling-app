"""#751: a dataset that is someone else's answers exactly like one that does not exist.

Seven routes under /datasets/{id} looked the dataset up, then answered 403 "Access denied"
when it belonged to another tenant, which tells any signed-in caller which ids are real.
Every other owned surface answers 404 for both. Real documents, no patched lookups.
"""
import pytest

from app.models.dataset import DatasetMetadata

TEST_USER = "test_user_123"
ROUTES = [
    ("GET", "/api/v1/datasets/{id}", None),
    ("PUT", "/api/v1/datasets/{id}", {"statistics": {"rows": 1}}),
    ("DELETE", "/api/v1/datasets/{id}", None),
    ("GET", "/api/v1/datasets/{id}/schema", None),
    ("GET", "/api/v1/datasets/{id}/preview", None),
    ("POST", "/api/v1/datasets/{id}/process", {"statistics": {"rows": 1}}),
    ("GET", "/api/v1/datasets/{id}/features/selected", None),
]
IDS = [f"{method} {url.rsplit('}', 1)[1] or '/'}" for method, url, _ in ROUTES]


async def _dataset(dataset_id: str, user_id: str) -> DatasetMetadata:
    doc = DatasetMetadata(
        user_id=user_id, dataset_id=dataset_id, filename="a.csv", original_filename="a.csv",
        file_type="csv", file_path=f"datasets/{user_id}/a.csv", s3_url=f"s3://test-bucket/datasets/{user_id}/a.csv",
        num_rows=2, num_columns=2, columns=["a", "b"],
    )
    await doc.insert()
    return doc


@pytest.mark.parametrize("method, url, body", ROUTES, ids=IDS)
@pytest.mark.asyncio
async def test_a_foreign_dataset_is_not_found_like_one_that_does_not_exist(
    setup_database, async_authorized_client, method, url, body
):
    await _dataset("ds-theirs", "someone-else")

    foreign = await async_authorized_client.request(method, url.format(id="ds-theirs"), json=body)
    unknown = await async_authorized_client.request(method, url.format(id="ds-nobody"), json=body)

    assert foreign.status_code == 404, foreign.text
    assert unknown.status_code == 404, unknown.text
    assert foreign.json()["detail"].replace("ds-theirs", "<id>") == unknown.json()["detail"].replace("ds-nobody", "<id>")
    assert await DatasetMetadata.find_one(DatasetMetadata.dataset_id == "ds-theirs") is not None


@pytest.mark.asyncio
async def test_the_owner_still_reads_and_updates_their_dataset(setup_database, async_authorized_client):
    await _dataset("ds-mine", TEST_USER)

    read = await async_authorized_client.get("/api/v1/datasets/ds-mine")
    updated = await async_authorized_client.put("/api/v1/datasets/ds-mine", json={"statistics": {"rows": 2}})
    schema = await async_authorized_client.get("/api/v1/datasets/ds-mine/schema")
    selected = await async_authorized_client.get("/api/v1/datasets/ds-mine/features/selected")
    processed = await async_authorized_client.post("/api/v1/datasets/ds-mine/process", json={"statistics": {"rows": 2}})

    assert read.status_code == 200 and read.json()["dataset_id"] == "ds-mine"
    assert updated.status_code == 200 and updated.json()["statistics"] == {"rows": 2}
    assert updated.json().keys() == read.json().keys()
    assert schema.status_code == 200
    assert selected.status_code == 200
    assert processed.status_code == 200, processed.text
    assert (await DatasetMetadata.find_one(DatasetMetadata.dataset_id == "ds-mine")).is_processed is True
