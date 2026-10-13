"""#781 AC1: rows written before #768 carry no `file_size`, so the storage ceiling
counts them as nothing. The backfill reads each object's size; dry run by default."""

import importlib.util
from pathlib import Path

import pytest

from app.models.user_data import UserData

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backfill_dataset_file_sizes.py"
SIZES = {"s3://b/datasets/u/old.csv": 5000, "s3://b/datasets/u/other.csv": 700}

pytestmark = pytest.mark.asyncio


def _load():
    spec = importlib.util.spec_from_file_location("backfill_dataset_file_sizes", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.object_size = SIZES.get  # the one HEAD the script makes
    return module


async def _row(url: str, size: int | None) -> UserData:
    return await UserData(
        user_id="u", filename="d.csv", original_filename="d.csv", s3_url=url,
        num_rows=1, num_columns=1, data_schema=[], file_size=size,
    ).insert()


async def test_a_dry_run_counts_what_it_would_write_and_writes_nothing(setup_database):
    old = await _row("s3://b/datasets/u/old.csv", None)
    await _row("s3://b/datasets/u/other.csv", None)
    await _row("s3://b/datasets/u/new.csv", 123)  # written since #768: not a candidate

    counts = await _load().backfill(apply=False)

    assert counts == {"missing": 2, "sized": 2, "bytes": 5700, "written": 0, "unreadable": 0}
    assert (await UserData.get(old.id)).file_size is None


async def test_apply_writes_each_size_and_only_that_field(setup_database):
    old = await _row("s3://b/datasets/u/old.csv", None)
    kept = await _row("s3://b/datasets/u/new.csv", 123)
    await old.set({"num_rows": 42})  # another writer's field, changed after the insert

    counts = await _load().backfill(apply=True)

    assert counts["written"] == 1
    after = await UserData.get(old.id)
    assert (after.file_size, after.num_rows) == (5000, 42)
    assert (await UserData.get(kept.id)).file_size == 123


async def test_an_object_that_cannot_be_read_is_counted_and_left_alone(setup_database):
    gone = await _row("s3://b/datasets/u/deleted.csv", None)

    counts = await _load().backfill(apply=True)

    assert counts == {"missing": 1, "sized": 0, "bytes": 0, "written": 0, "unreadable": 1}
    assert (await UserData.get(gone.id)).file_size is None


async def test_a_row_sized_by_someone_else_since_the_scan_is_not_counted_as_written(setup_database):
    """A transformation that lands mid-run records the size of the file the dataset
    moved to. The backfill must not overwrite it, nor claim the write."""
    row = await _row("s3://b/datasets/u/old.csv", None)
    module = _load()

    def sized_meanwhile(url):
        UserData.get_motor_collection().delegate.update_one({"_id": row.id}, {"$set": {"file_size": 999}})
        return SIZES.get(url)

    module.object_size = sized_meanwhile
    counts = await module.backfill(apply=True)

    assert counts["written"] == 0
    assert (await UserData.get(row.id)).file_size == 999


async def test_a_second_run_finds_nothing_left(setup_database):
    await _row("s3://b/datasets/u/old.csv", None)
    module = _load()
    await module.backfill(apply=True)

    assert (await module.backfill(apply=True))["missing"] == 0


async def _run(monkeypatch, capsys, *argv: str) -> tuple[int, str]:
    """The script's own entry point, against the test database the suite is on."""
    import os

    monkeypatch.setattr("sys.argv", ["backfill_dataset_file_sizes.py", *argv])
    monkeypatch.setenv("MONGODB_URI", os.environ["TEST_MONGODB_URI"])
    monkeypatch.setenv("MONGODB_DB", UserData.get_motor_collection().database.name)
    status = await _load().main()
    return status, capsys.readouterr().out.strip()


async def test_the_command_reports_counts_only_and_exits_1_while_rows_remain(setup_database, monkeypatch, capsys):
    await _row("s3://b/datasets/u/old.csv", None)

    status, out = await _run(monkeypatch, capsys)

    assert status == 1, "a dry run that found a row to size"
    assert out == "missing=1 sized=1 bytes=5000 written=0 unreadable=0 applied=False"


async def test_the_command_applies_as_json_and_exits_0_when_nothing_is_left(setup_database, monkeypatch, capsys):
    import json

    await _row("s3://b/datasets/u/old.csv", None)

    status, out = await _run(monkeypatch, capsys, "--apply", "--json")

    # The command closes the connection it opened, so the write itself is asserted where
    # `backfill` is called directly; here it is the report and the exit status.
    assert status == 0
    assert json.loads(out) == {"missing": 1, "sized": 1, "bytes": 5000, "written": 1, "unreadable": 0, "applied": True}


async def test_the_command_refuses_to_guess_a_database(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["backfill_dataset_file_sizes.py"])
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGODB_DB", raising=False)

    assert await _load().main() == 2
    assert "must be set" in capsys.readouterr().err
