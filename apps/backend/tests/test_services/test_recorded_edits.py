"""#923: an edit made outside the engine is recorded as a history step.

Real documents in the test database; S3 is replaced at the two data_utils calls the
service makes. The full flow against a real bucket, with undo, is
tests/test_integration/test_every_edit_is_in_the_history_localstack.py.
"""
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from app.models.dataset import DatasetMetadata
from app.models.feature import ExpressionNode, FeatureDefinition, NodeType
from app.models.transformation import TransformationConfig
from app.services import feature_builder_service as fbs
from app.services.feature_builder_service import FeatureBuilderService

pytestmark = pytest.mark.asyncio

USER, DATASET = "edit-user", "ds-edit"
FRAME = pd.DataFrame({"amount": [1, 2, 3]})


@pytest.fixture
async def feature(setup_database, monkeypatch):
    from app.services.transformation_engine import data_utils

    await DatasetMetadata(
        dataset_id=DATASET, user_id=USER, filename="d.csv", original_filename="d.csv", file_type="csv",
        file_path=f"datasets/{USER}/d.csv", s3_url=f"s3://bucket/datasets/{USER}/d.csv",
        num_rows=3, num_columns=1, columns=["amount"],
    ).insert()
    await FeatureDefinition(
        user_id=USER, dataset_id=DATASET, feature_id="feat-edit", name="amount_copy",
        expression_tree=ExpressionNode(node_id="n1", node_type=NodeType.COLUMN, value="amount"), is_valid=True,
    ).insert()

    async def load(_url):
        return FRAME.copy()

    async def upload(_df, key):
        return f"s3://bucket/{key}"

    monkeypatch.setattr(fbs, "get_dataframe_from_s3", load)
    monkeypatch.setattr(data_utils, "upload_dataframe_to_s3", upload)
    return "feat-edit"


async def test_a_column_added_in_place_is_a_history_step(feature):
    from app.services.history_service import HistoryService
    from app.services.transformation_service import TransformationService
    from app.services.versioning_service import versioning_service

    result = await FeatureBuilderService().apply_feature_to_dataset(feature_id=feature, user_id=USER)

    assert (result["success"], result["dataset_committed"]) == (True, False), result
    assert result["s3_url"].startswith(f"s3://bucket/transformed/{USER}/{DATASET}_")
    config = await TransformationConfig.find_one(TransformationConfig.dataset_id == DATASET)
    (step,) = config.transformation_steps
    assert (step.transformation_type, step.columns, step.parameters["feature_id"]) == (
        "feature_column", ["amount_copy"], feature)
    stored = await DatasetMetadata.find_one(DatasetMetadata.dataset_id == DATASET)
    assert stored.s3_url == result["s3_url"]
    assert (stored.columns, stored.num_columns) == (["amount", "amount_copy"], 2)
    assert [f.field_name for f in stored.data_schema] == ["amount_copy"]

    history = await HistoryService(versioning_service, TransformationService()).get_history(DATASET, USER)
    assert history["history"][0]["description"] == "Added feature column amount_copy"


async def test_a_new_dataset_whose_upload_fails_is_not_committed(feature, monkeypatch):
    monkeypatch.setattr(fbs, "upload_parquet_bytes", AsyncMock(side_effect=RuntimeError("no bucket")))

    result = await FeatureBuilderService().apply_feature_to_dataset(
        feature_id=feature, user_id=USER, create_new_dataset=True)

    assert (result["success"], result["dataset_committed"]) == (False, False)
    assert result["error"] == "Failed to upload to S3: no bucket"


async def test_a_new_dataset_that_fails_after_it_was_created_is_committed(feature, monkeypatch):
    """The route keeps the unit for a dataset that exists, whatever failed after it (#459)."""
    async def upload(_content, key):
        return f"s3://bucket/{key}"

    monkeypatch.setattr(fbs, "upload_parquet_bytes", upload)
    monkeypatch.setattr(FeatureDefinition, "save", AsyncMock(side_effect=RuntimeError("database went away")))

    result = await FeatureBuilderService().apply_feature_to_dataset(
        feature_id=feature, user_id=USER, create_new_dataset=True)

    assert (result["success"], result["dataset_committed"]) == (False, True)
    assert result["dataset_id"] != DATASET
    assert await DatasetMetadata.find_one(DatasetMetadata.dataset_id == result["dataset_id"])


async def test_a_failure_before_anything_is_written_is_not_committed(feature, monkeypatch):
    monkeypatch.setattr(fbs, "get_dataframe_from_s3", AsyncMock(side_effect=RuntimeError("unreadable")))

    result = await FeatureBuilderService().apply_feature_to_dataset(feature_id=feature, user_id=USER)

    assert (result["success"], result["dataset_committed"], result["error"]) == (False, False, "unreadable")
