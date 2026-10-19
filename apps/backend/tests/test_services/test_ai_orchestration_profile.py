"""build_profile reads a dataset's stored column metadata into a profile (#1088 split).

Unit level: the dataset lookup is the only fake. The route-level behaviour, ownership 404s
and recommendations against real documents are in tests/test_api/test_ai_orchestration.py.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_orchestration_service import AIOrchestrationService

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _field(name, field_type="text", *, missing=0, high=False, constant=False):
    return SimpleNamespace(
        field_name=name, field_type=field_type, missing_values=missing,
        is_high_cardinality=high, is_constant=constant,
    )


def _dataset(schema=(), inferred=None, rows=10):
    return SimpleNamespace(
        num_rows=rows, num_columns=len(schema), is_processed=True, data_schema=list(schema),
        inferred_schema=inferred,
    )


async def _profile(dataset):
    service = AIOrchestrationService.__new__(AIOrchestrationService)
    lookup = MagicMock()
    lookup.find_one = AsyncMock(return_value=dataset)
    with patch("app.services.ai_orchestration_service.DatasetMetadata", lookup):
        return await service.build_profile("ds", "u")


async def test_an_unknown_dataset_has_no_profile():
    assert await _profile(None) is None


async def test_each_stored_field_lands_in_its_bucket_with_its_flags():
    profile = await _profile(_dataset([
        _field("age", "numeric", missing=5),
        _field("when", "datetime"),
        _field("city", "text", high=True),
        _field("flag", "boolean", constant=True),
    ]))

    assert profile.numeric_columns == ["age"]
    assert profile.datetime_columns == ["when"]
    assert profile.categorical_columns == ["city", "flag"]
    assert profile.high_cardinality_columns == ["city"]
    assert profile.constant_columns == ["flag"]
    assert profile.columns_with_missing == {"age": 0.5}
    assert profile.partial is False


async def test_an_empty_schema_falls_back_to_the_inferred_one():
    inferred = {"columns": [{"name": "price", "data_type": "float"}, {"name": "day", "data_type": "date"}]}

    profile = await _profile(_dataset(inferred=inferred))

    assert profile.numeric_columns == ["price"] and profile.datetime_columns == ["day"]


async def test_a_dataset_with_no_column_metadata_is_partial():
    assert (await _profile(_dataset())).partial is True


async def test_missing_values_in_an_empty_dataset_are_not_a_ratio():
    profile = await _profile(_dataset([_field("a", "numeric", missing=3)], rows=0))

    assert profile.columns_with_missing == {}
