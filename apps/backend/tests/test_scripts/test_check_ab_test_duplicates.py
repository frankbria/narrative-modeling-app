"""#565 AC2: the pre-deploy check finds duplicate experiment_ids and drops the legacy index."""

import importlib.util
from pathlib import Path

import pytest

from app.models.ab_test import ABTest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_ab_test_duplicates.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_ab_test_duplicates", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_finds_duplicates_and_drops_the_legacy_index(setup_database):
    mod = _load()
    # A scratch collection stands in for a pre-#565 ab_tests: no unique index yet.
    scratch = ABTest.get_motor_collection().database["ab_tests_pre565_scratch"]
    await scratch.drop()
    await scratch.create_index([("experiment_id", 1)], name=mod.LEGACY_INDEX)
    await scratch.insert_many([
        {"experiment_id": "exp_dup", "user_id": "a"},
        {"experiment_id": "exp_dup", "user_id": "b"},
        {"experiment_id": "exp_dup", "user_id": "c"},
        {"experiment_id": "exp_solo", "user_id": "a"},
    ])
    try:
        assert await mod.find_duplicates(scratch) == [{"experiment_id": "exp_dup", "count": 3}]
        assert await mod.drop_legacy_index(scratch) is True
        assert mod.LEGACY_INDEX not in await scratch.index_information()
        assert await mod.drop_legacy_index(scratch) is False  # idempotent
    finally:
        await scratch.drop()


@pytest.mark.asyncio
async def test_clean_collection_reports_nothing(setup_database):
    mod = _load()
    assert await mod.find_duplicates(ABTest.get_motor_collection()) == []
