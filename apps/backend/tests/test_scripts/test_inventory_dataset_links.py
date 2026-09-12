"""#467 AC4: the inventory counts broken twin links, per side, from real documents."""
import importlib.util
from pathlib import Path

import pytest

from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "inventory_dataset_links.py"


def _load():
    spec = importlib.util.spec_from_file_location("inventory_dataset_links", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


async def _meta(user: str, ds: str, url: str, source: str | None = None) -> DatasetMetadata:
    return await DatasetMetadata(
        user_id=user, dataset_id=ds, filename="d.csv", original_filename="d.csv", file_type="csv",
        file_path=url, s3_url=url, source_s3_url=source, num_rows=1, num_columns=1,
    ).insert()


async def _ud(user: str, url: str) -> UserData:
    return await UserData(
        user_id=user, filename="d.csv", original_filename="d.csv", s3_url=url,
        num_rows=1, num_columns=1, data_schema=[],
    ).insert()


@pytest.mark.asyncio
async def test_counts_linked_moved_and_orphaned_twins(setup_database):
    mod = _load()
    # intact pair, never moved
    await _meta("u1", "a", "s3://b/datasets/u1/a.csv")
    await _ud("u1", "s3://b/datasets/u1/a.csv")
    # intact pair, moved by #467's helper (both sides at the new file)
    await _meta("u1", "b", "s3://b/transformed/u1/b.parquet", source="s3://b/datasets/u1/b.csv")
    await _ud("u1", "s3://b/transformed/u1/b.parquet")
    # pre-#467 severed link: metadata moved alone, twin still at the upload
    await _meta("u1", "c", "s3://b/transformed/u1/c.parquet")
    await _ud("u1", "s3://b/datasets/u1/c.csv")
    # a UserData that never had a metadata twin (legacy /upload/secure path)
    await _ud("u2", "s3://b/datasets/u2/solo.csv")
    # same url, different user: not a pair
    await _meta("u3", "d", "s3://b/datasets/shared.csv")
    await _ud("u4", "s3://b/datasets/shared.csv")

    inv = await mod.inventory()

    assert inv.dataset_metadata_total == 4
    assert inv.user_data_total == 5
    assert inv.linked_pairs == 2
    assert inv.metadata_moved_with_twin_intact == 1
    assert inv.metadata_without_twin == 2  # c (severed) + d (foreign user at same url)
    assert inv.user_data_without_twin == 3  # c's twin, u2 solo, u4 at shared url
