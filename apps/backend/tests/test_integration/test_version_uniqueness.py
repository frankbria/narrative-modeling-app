"""Integration test: unique (dataset_id, version_number) index (issue #276).

Proves the correctness backstop for the read-then-increment version-number race
against a real MongoDB — two rows sharing (dataset_id, version_number) are rejected.
"""

import uuid
from types import SimpleNamespace

import pytest
from pymongo.errors import DuplicateKeyError

from app.models.version import DatasetVersion
from app.services.versioning_service import versioning_service


def _make_version(dataset_id: str, version_number: int) -> DatasetVersion:
    return DatasetVersion(
        version_id=str(uuid.uuid4()),
        dataset_id=dataset_id,
        version_number=version_number,
        user_id="user1",
        content_hash=uuid.uuid4().hex,  # distinct content each time
        file_size=10,
        file_path=f"datasets/user1/{dataset_id}/versions/x/f.csv",
        s3_url=f"s3://b/datasets/user1/{dataset_id}/versions/x/f.csv",
        num_rows=1,
        num_columns=1,
        columns=["a"],
        schema_hash="sh",
        created_by="user1",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_dataset_version_number_rejected(setup_database):
    """Second insert with the same (dataset_id, version_number) raises DuplicateKeyError."""
    dataset_id = f"ds_{uuid.uuid4().hex[:8]}"

    await _make_version(dataset_id, 1).insert()

    with pytest.raises(DuplicateKeyError):
        await _make_version(dataset_id, 1).insert()

    # Different number is fine; different dataset with same number is fine.
    await _make_version(dataset_id, 2).insert()
    await _make_version(f"ds_{uuid.uuid4().hex[:8]}", 1).insert()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_base_version_persists_v1(setup_database):
    """Upload creates a queryable base version (#276, AC3: base version at upload)."""
    dataset_id = f"ds_{uuid.uuid4().hex[:8]}"
    dataset = SimpleNamespace(
        dataset_id=dataset_id,
        file_path=f"datasets/user1/{dataset_id}_f.csv",
        s3_url=f"s3://b/datasets/user1/{dataset_id}_f.csv",
        num_rows=3,
        num_columns=1,
        columns=["a"],
        data_schema=[],
    )

    version = await versioning_service.create_base_version(
        dataset_metadata=dataset, file_content=b"a\n1\n2\n3\n", user_id="user1"
    )
    assert version.version_number == 1
    assert version.is_base_version is True

    stored = await DatasetVersion.find_one(
        DatasetVersion.dataset_id == dataset_id,
        DatasetVersion.is_base_version == True,  # noqa: E712
    )
    assert stored is not None and stored.version_id == version.version_id
