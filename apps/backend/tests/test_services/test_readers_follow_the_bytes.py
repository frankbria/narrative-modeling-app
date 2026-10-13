"""#733: charts and the feature store read a dataset as what it is, not as CSV.

Five readers parsed every stored dataset with `pd.read_csv` (the feature store also
took Excel). A transformation rewrites the dataset as Parquet, so each of them failed
for any dataset transformed once, and the charts failed for a workbook or JSON upload
from the start. Each reader is given real bytes here at the seam where it downloads.
"""

import io
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest
from beanie import PydanticObjectId

from app.models.dataset import DatasetMetadata
from app.services.s3_service import read_dataframe_from_bytes

FRAME = pd.DataFrame({"visits": [1, 2, 3, 4, 5, 6], "spend": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]})


def _same(frame: pd.DataFrame) -> bool:
    """The stored frame, give or take a dtype: JSON and Excel hand back 10.0 as 10."""
    pd.testing.assert_frame_equal(frame, FRAME, check_dtype=False)
    return True


def _parquet() -> bytes:
    buffer = io.BytesIO()
    FRAME.to_parquet(buffer, index=False)
    return buffer.getvalue()


def _xlsx() -> bytes:
    buffer = io.BytesIO()
    FRAME.to_excel(buffer, index=False)
    return buffer.getvalue()


STORED_AS = {
    "csv": FRAME.to_csv(index=False).encode(),
    "parquet": _parquet(),
    "xlsx": _xlsx(),
    "json": FRAME.to_json(orient="records").encode(),
}


@pytest.mark.parametrize("kind", sorted(STORED_AS))
def test_bytes_with_no_declared_type_are_read_by_what_they_are(kind):
    assert _same(read_dataframe_from_bytes(STORED_AS[kind]))


@pytest.mark.parametrize("kind", sorted(STORED_AS))
def test_bytes_with_a_declared_type_are_read_as_it(kind):
    assert _same(read_dataframe_from_bytes(STORED_AS[kind], kind))


@pytest.mark.asyncio
async def test_a_histogram_of_a_transformed_dataset(setup_database):
    """Parquet is what every dataset is after its first transformation."""
    from app.services import visualization_cache

    dataset = Mock(id=PydanticObjectId(), s3_url="s3://bucket/transformed/u/d.parquet")
    with (
        patch.object(visualization_cache.UserData, "get", AsyncMock(return_value=dataset)),
        patch.object(visualization_cache, "get_cached_visualization", AsyncMock(return_value=None)),
        patch.object(visualization_cache, "cache_visualization", AsyncMock()),
        patch.object(visualization_cache, "get_file_from_s3", return_value=io.BytesIO(_parquet())),
    ):
        histogram = await visualization_cache.generate_and_cache_histogram(str(dataset.id), "visits", num_bins=3)

    assert histogram["counts"] == [2, 2, 2]


@pytest.mark.asyncio
async def test_a_box_plot_and_a_correlation_matrix_of_a_transformed_dataset(setup_database):
    from app.services import visualization_cache

    dataset = Mock(id=PydanticObjectId(), s3_url="s3://bucket/transformed/u/d.parquet")
    with (
        patch.object(visualization_cache.UserData, "get", AsyncMock(return_value=dataset)),
        patch.object(visualization_cache, "get_cached_visualization", AsyncMock(return_value=None)),
        patch.object(visualization_cache, "cache_visualization", AsyncMock()),
        patch.object(visualization_cache, "get_file_from_s3", side_effect=lambda _url: io.BytesIO(_parquet())),
    ):
        box = await visualization_cache.generate_and_cache_boxplot(str(dataset.id), "spend")
        matrix = await visualization_cache.generate_and_cache_correlation_matrix(str(dataset.id))

    assert (box["min"], box["median"], box["max"]) == (10.0, 35.0, 60.0)
    assert matrix["columns"] == ["visits", "spend"] and matrix["matrix"][0][1] == pytest.approx(1.0)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["parquet", "xlsx", "json"])
async def test_the_chart_routes_loader(kind):
    from app.api.routes import visualizations

    with patch.object(visualizations, "get_file_from_s3", return_value=io.BytesIO(STORED_AS[kind])):
        frame = await visualizations._load_dataframe(f"s3://bucket/datasets/u/d.{kind}", set(FRAME.columns))

    assert _same(frame)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["parquet", "json", "csv", "xlsx"])
async def test_the_feature_store(kind):
    from app.services.feature_store_service import FeatureStoreService

    dataset = DatasetMetadata(
        user_id="u", dataset_id="d733", filename=f"d.{kind}", original_filename=f"d.{kind}", file_type=kind,
        file_path=f"datasets/u/d.{kind}", s3_url=f"s3://test-bucket/datasets/u/d.{kind}", num_rows=6, num_columns=2,
    )
    with patch(
        "app.services.feature_store_service.s3_service.download_file_bytes",
        new_callable=AsyncMock, return_value=STORED_AS[kind],
    ):
        frame = await FeatureStoreService._load_dataset_frame(dataset)

    assert _same(frame)
