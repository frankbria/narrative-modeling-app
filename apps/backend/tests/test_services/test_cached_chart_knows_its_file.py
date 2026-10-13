"""#964: a cached chart is of one file, and is served only for that file.

#960 clears a dataset's chart caches when the dataset moves. A request that began before
the move can finish after it and write the old chart back; with nothing on the entry to
say which file it came from, that old chart was then served for good.
"""

import pytest

from app.models.user_data import UserData
from app.services.dataset_link import record_new_file
from app.services.visualization_cache import (
    cache_visualization,
    get_cached_visualization,
)

pytestmark = pytest.mark.asyncio

OLD = "s3://test-bucket/datasets/u964/visits.csv"
NEW = "s3://test-bucket/transformed/u964/visits_1.parquet"


async def _upload() -> UserData:
    return await UserData(
        user_id="u964", filename="visits.csv", original_filename="visits.csv", file_type="csv",
        s3_url=OLD, num_rows=3, num_columns=1, data_schema=[],
    ).insert()


async def test_a_request_that_finishes_after_the_move_does_not_poison_the_cache(setup_database):
    upload = await _upload()
    dataset_id = str(upload.id)
    # A box plot request has read the dataset and is computing from the old file...
    await record_new_file(upload, NEW)  # ...the dataset moves, clearing its caches...
    await cache_visualization(dataset_id, "boxplot", {"median": 1000}, "spend", source_url=OLD)  # ...and it finishes.

    served = await get_cached_visualization(dataset_id, "boxplot", "spend", source_url=NEW)

    assert served is None, "a chart of the old file is not a chart of the dataset as it is now"


async def test_a_chart_is_served_for_the_file_it_was_computed_from(setup_database):
    upload = await _upload()
    dataset_id = str(upload.id)
    await cache_visualization(dataset_id, "boxplot", {"median": 10}, "spend", source_url=OLD)

    assert await get_cached_visualization(dataset_id, "boxplot", "spend", source_url=OLD) == {"median": 10}
    assert await get_cached_visualization(dataset_id, "boxplot", "spend", source_url=NEW) is None


async def test_an_entry_written_before_this_change_is_not_trusted_for_any_file(setup_database):
    """It records no file, so nothing says what it is a chart of."""
    upload = await _upload()
    dataset_id = str(upload.id)
    await cache_visualization(dataset_id, "correlation", {"matrix": [[1.0]]})

    assert await get_cached_visualization(dataset_id, "correlation", source_url=OLD) is None
