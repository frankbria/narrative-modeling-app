"""Shared fixtures for load tests.

Prerequisites (see apps/backend/docs/TEST_INFRASTRUCTURE.md):
- MongoDB running locally — the dataset-ownership document that
  generate_preview's security check requires is seeded into the test database.
- S3 is stubbed at the get_dataframe_from_s3 seam with a locally generated
  DataFrame, so timings measure the preview pipeline itself rather than
  network throughput.
"""

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from unittest.mock import patch

TEST_USER_ID = "load_test_user_123"
TEST_DATASET_ID = "test_dataset_456"
TEST_S3_PATH = "s3://test-bucket/test-data.csv"

# Columns referenced by the load-test transformation steps
_RNG_ROWS = 1000


def _build_test_dataframe(nrows: int) -> pd.DataFrame:
    """Deterministic synthetic dataset with numeric/categorical/missing data."""
    rng = np.random.default_rng(seed=42)
    n = min(nrows, _RNG_ROWS)
    value = rng.normal(100.0, 15.0, n)
    # Sprinkle missing values so fill_missing has work to do
    value[:: max(n // 20, 1)] = np.nan
    return pd.DataFrame({
        "id": np.arange(n),
        "name": [f"row_{i % 50}" for i in range(n)],
        "value": value,
        "category": [["A", "B", "C"][i % 3] for i in range(n)],
    })


@pytest.fixture
def test_data_config():
    """Test data configuration."""
    return {
        "user_id": TEST_USER_ID,
        "dataset_id": TEST_DATASET_ID,
        "s3_file_path": TEST_S3_PATH,
    }


@pytest_asyncio.fixture
async def seeded_dataset(setup_database):
    """Seed the DatasetMetadata document required by generate_preview's
    ownership/path security checks."""
    from app.models.dataset import DatasetMetadata

    dataset = DatasetMetadata(
        user_id=TEST_USER_ID,
        dataset_id=TEST_DATASET_ID,
        filename="test-data.csv",
        original_filename="test-data.csv",
        file_type="csv",
        file_path=TEST_S3_PATH,
        s3_url=TEST_S3_PATH,
        num_rows=_RNG_ROWS,
        num_columns=4,
        columns=["id", "name", "value", "category"],
    )
    await dataset.insert()
    yield dataset
    # setup_database cleanup removes all documents


@pytest.fixture
def stub_s3_dataframe(seeded_dataset):
    """Stub the S3 download seam with a locally generated DataFrame."""

    async def _fake_get_dataframe_from_s3(s3_file_path, nrows=None, **kwargs):
        return _build_test_dataframe(nrows or _RNG_ROWS)

    with patch(
        "app.services.data_processing.preview_service_integration.get_dataframe_from_s3",
        side_effect=_fake_get_dataframe_from_s3,
    ):
        yield
