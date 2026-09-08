"""Coverage for the #455 repair script, which does bulk writes against real data.

`scripts/fix_api_key_rate_limits.py` is what runs against staging/production per
the deploy checklist, so its query logic is worth a test rather than a one-off
manual run. `_audit` takes the collection, so it can be pointed at the test DB.
"""

import importlib.util
from pathlib import Path

import pytest

from app.billing.plans import api_key_rate_limit_ceiling
from app.models.api_key import APIKey
from app.models.subscription import PlanTier

pytestmark = pytest.mark.asyncio

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fix_api_key_rate_limits.py"


def _load_audit():
    spec = importlib.util.spec_from_file_location("fix_api_key_rate_limits", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._audit


FLOOR = api_key_rate_limit_ceiling(PlanTier.FREE)
CEILING = api_key_rate_limit_ceiling(PlanTier.ENTERPRISE)


#: One row per shape the script claims to classify, plus one already in range.
#: `key_hash` is unique-indexed, so every row needs its own.
_SEED = {
    "s-zero": 0,
    "s-negative": -5,
    "s-null": None,
    "s-string": "1000",
    "s-missing": ...,  # the field is absent entirely
    "s-above": CEILING + 1,
    "s-ok": 500,
}


async def _seed(collection) -> None:
    docs = []
    for key_id, rate_limit in _SEED.items():
        doc = {"key_id": key_id, "key_hash": APIKey.hash_key(key_id)}
        if rate_limit is not ...:
            doc["rate_limit"] = rate_limit
        docs.append(doc)
    await collection.insert_many(docs)


class TestAuditScript:
    async def test_read_only_reports_damage_without_writing(
        self, setup_database, capsys
    ):
        collection = APIKey.get_motor_collection()
        await _seed(collection)

        assert await _load_audit()(collection, FLOOR, CEILING, False) == 1

        out = capsys.readouterr().out
        assert "rate_limit <= 0 (UNLIMITED):   2" in out  # 0 and -5
        assert "rate_limit missing/non-numeric: 3" in out  # null, string, absent
        assert f"rate_limit > {CEILING}" in out

        untouched = await collection.find_one({"key_id": "s-zero"})
        assert untouched["rate_limit"] == 0, "read-only mode must not write"

    async def test_apply_corrects_every_row_and_leaves_valid_ones_alone(
        self, setup_database
    ):
        collection = APIKey.get_motor_collection()
        await _seed(collection)

        assert await _load_audit()(collection, FLOOR, CEILING, True) == 0

        for key_id in ("s-zero", "s-negative", "s-null", "s-string", "s-missing"):
            row = await collection.find_one({"key_id": key_id})
            assert row["rate_limit"] == FLOOR, key_id
        above = await collection.find_one({"key_id": "s-above"})
        assert above["rate_limit"] == CEILING
        # A value already inside the range is not "corrected" to the ceiling.
        ok = await collection.find_one({"key_id": "s-ok"})
        assert ok["rate_limit"] == 500

    async def test_clean_database_reports_nothing(self, setup_database):
        collection = APIKey.get_motor_collection()
        await collection.insert_one(
            {
                "key_id": "s-fine",
                "key_hash": APIKey.hash_key("s-fine"),
                "rate_limit": 500,
            }
        )

        assert await _load_audit()(collection, FLOOR, CEILING, False) == 0
