"""#1088, #1103: rows in collections whose feature was removed are still erased.

The data-issues, feature-store and feature-definition routes and their models are gone, so no
model class maps `data_issues`, `feature_definitions`, `feature_store`, `feature_versions` or
`feature_collections` any more. Rows
written before the removal still hold a tenant's data, so erasure reaches them by name:
a dataset erase takes its `data_issues` and `feature_definitions`; a user erase takes every row they own, and pulls
their id from co-tenants' `shared_with` without deleting the co-tenant's rows (#662).

Requires real MongoDB (setup_database); no S3 object is seeded.
"""

import pytest

from app.models.dataset import DatasetMetadata
from app.services.erasure_service import DatasetErasureService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

ERASED = "erase_retired_user"
OTHER = "other_retired_tenant"
_NAMES = ("data_issues", "feature_definitions", "feature_store", "feature_versions", "feature_collections")


def _coll(name: str):
    return DatasetMetadata.get_motor_collection().database[name]


@pytest.fixture
async def retired(setup_database):
    for name in _NAMES:
        await _coll(name).delete_many({})
    yield
    for name in _NAMES:
        await _coll(name).delete_many({})


async def _count(name: str, query: dict) -> int:
    return await _coll(name).count_documents(query)


async def _dataset(dataset_id: str) -> None:
    await DatasetMetadata(
        user_id=ERASED, dataset_id=dataset_id, filename="d.csv", original_filename="d.csv",
        file_type="csv", file_path=f"datasets/{ERASED}/d.csv",
        s3_url=f"s3://nma-test/datasets/{ERASED}/d.csv", num_rows=1, num_columns=1,
    ).insert()


async def test_a_dataset_erase_takes_its_retired_rows(retired):
    await _dataset("ds-retired")
    for name in ("data_issues", "feature_definitions"):
        await _coll(name).insert_many([
            {"dataset_id": "ds-retired", "user_id": ERASED},
            {"dataset_id": "ds-kept", "user_id": ERASED},
        ])

    manifest = await DatasetErasureService().erase_dataset("ds-retired", ERASED)

    for name in ("data_issues", "feature_definitions"):
        assert await _count(name, {"dataset_id": "ds-retired"}) == 0
        assert await _count(name, {"dataset_id": "ds-kept"}) == 1
        assert manifest.documents_deleted[name] == 1
    assert manifest.failures == [], manifest.failures


async def test_a_user_erase_takes_everything_they_own_and_nothing_else(retired):
    await _coll("data_issues").insert_many([{"dataset_id": "x", "user_id": ERASED}, {"dataset_id": "y", "user_id": OTHER}])
    await _coll("feature_definitions").insert_many([
        {"feature_id": "def-mine", "dataset_id": "x", "user_id": ERASED},
        {"feature_id": "def-theirs", "dataset_id": "y", "user_id": OTHER},
    ])
    await _coll("feature_store").insert_many([
        {"feature_id": "feat-mine", "user_id": ERASED, "shared_with": []},
        {"feature_id": "feat-theirs", "user_id": OTHER, "shared_with": []},
    ])
    await _coll("feature_versions").insert_many([
        {"version_id": "v1", "feature_id": "feat-mine"}, {"version_id": "v2", "feature_id": "feat-theirs"},
    ])
    await _coll("feature_collections").insert_many([
        {"collection_id": "c-mine", "user_id": ERASED}, {"collection_id": "c-theirs", "user_id": OTHER},
    ])

    manifest = await DatasetErasureService().erase_user(ERASED, actor_id=ERASED)

    assert await _count("data_issues", {"user_id": ERASED}) == 0
    assert await _count("feature_definitions", {"user_id": ERASED}) == 0
    assert await _count("feature_store", {"user_id": ERASED}) == 0
    assert await _count("feature_versions", {"feature_id": "feat-mine"}) == 0
    assert await _count("feature_collections", {"user_id": ERASED}) == 0
    assert await _count("data_issues", {"user_id": OTHER}) == 1
    assert await _count("feature_definitions", {"user_id": OTHER}) == 1
    assert await _count("feature_store", {"user_id": OTHER}) == 1
    assert await _count("feature_versions", {"feature_id": "feat-theirs"}) == 1
    assert await _count("feature_collections", {"user_id": OTHER}) == 1
    assert manifest.failures == [], manifest.failures


async def test_a_user_erase_pulls_their_id_from_a_co_tenants_shared_with(retired):
    await _coll("feature_store").insert_one(
        {"feature_id": "feat-other", "user_id": OTHER, "shared_with": [ERASED, "third_user"]}
    )
    await _coll("feature_collections").insert_one(
        {"collection_id": "coll-other", "user_id": OTHER, "shared_with": [ERASED, "third_user"]}
    )

    manifest = await DatasetErasureService().erase_user(ERASED, actor_id=ERASED)

    feature = await _coll("feature_store").find_one({"feature_id": "feat-other"})
    collection = await _coll("feature_collections").find_one({"collection_id": "coll-other"})
    assert feature["shared_with"] == ["third_user"]
    assert collection["shared_with"] == ["third_user"]
    assert manifest.failures == [], manifest.failures
    assert sum("shared_with" in n for n in manifest.notes) == 2, manifest.notes


async def test_a_failing_retired_delete_is_recorded_not_raised(retired, monkeypatch):
    class _Broken:
        async def delete_many(self, *_):
            raise RuntimeError("mongo down")

    monkeypatch.setattr(DatasetErasureService, "_retired", staticmethod(lambda name: _Broken()))
    await _dataset("ds-broken")
    manifest = await DatasetErasureService().erase_dataset("ds-broken", ERASED)

    assert any(f.startswith("delete data_issues:") for f in manifest.failures), manifest.failures
