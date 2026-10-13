"""#960: a dataset that moves to a new file forgets what was computed from the old one.

Charts are cached per dataset, in Redis and in a collection that never expires, and
nothing cleared them when the dataset changed. After a transformation, an undo or a
data-issue fix the histogram, box plot and correlation matrix kept answering with the
data from before, for as long as the dataset existed.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.models.column_stats import ColumnStats
from app.models.user_data import UserData
from app.models.visualization_cache import VisualizationCache
from app.services import dataset_link

pytestmark = pytest.mark.asyncio

USER = "user_960"
BUCKET = "test-bucket"


async def _upload(name: str) -> UserData:
    return await UserData(
        user_id=USER, filename=f"{name}.csv", original_filename=f"{name}.csv", file_type="csv",
        s3_url=f"s3://{BUCKET}/datasets/{USER}/{name}.csv", num_rows=3, num_columns=1, data_schema=[],
    ).insert()


async def _computed_for(upload: UserData) -> None:
    for kind, column in (("histogram", "spend"), ("boxplot", "spend"), ("correlation", None)):
        await VisualizationCache(dataset_id=upload, visualization_type=kind, column_name=column, data={"median": 1000}).insert()
    await ColumnStats(
        dataset_id=upload, user_id=USER, column_name="spend", data_type="numeric", count=3, missing=0, unique=3
    ).insert()


async def _kept(upload: UserData) -> tuple[int, int]:
    charts = await VisualizationCache.find({"dataset_id.$id": upload.id}).count()
    stats = await ColumnStats.find({"dataset_id.$id": upload.id}).count()
    return charts, stats


async def test_a_move_drops_the_charts_and_statistics_of_that_dataset_only(setup_database):
    moved, untouched = await _upload("visits"), await _upload("orders")
    await _computed_for(moved)
    await _computed_for(untouched)

    with patch.object(dataset_link.cache_service, "delete_pattern", AsyncMock(return_value=0)) as redis:
        await dataset_link.record_new_file(moved, f"s3://{BUCKET}/transformed/{USER}/visits_1.parquet")

    assert await _kept(moved) == (0, 0)
    assert await _kept(untouched) == (3, 1)
    assert {call.args[0] for call in redis.await_args_list} == {f"viz:{moved.id}:*"}


async def test_a_cache_that_cannot_be_cleared_does_not_undo_the_move(setup_database):
    """The file has moved by then. The stale entries are logged, not raised."""
    moved = await _upload("visits")
    new_url = f"s3://{BUCKET}/transformed/{USER}/visits_1.parquet"

    with patch.object(dataset_link.cache_service, "delete_pattern", AsyncMock(side_effect=RuntimeError("redis is away"))):
        await dataset_link.record_new_file(moved, new_url)

    assert (await UserData.get(moved.id)).s3_url == new_url
