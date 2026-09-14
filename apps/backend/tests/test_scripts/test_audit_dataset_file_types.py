"""#524 AC2: the audit reconciles file_type against the object's extension, on both
twins, from real documents — dry-run reports, --apply corrects, no-extension rows
are left alone."""
import importlib.util
from pathlib import Path

import pytest

from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit_dataset_file_types.py"

pytestmark = pytest.mark.asyncio


def _load():
    spec = importlib.util.spec_from_file_location("audit_dataset_file_types", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


async def _ud(url: str, file_type: str) -> UserData:
    return await UserData(
        user_id="u", filename="d", original_filename="d", s3_url=url, file_path=url,
        file_type=file_type, num_rows=1, num_columns=1, data_schema=[],
    ).insert()


async def test_dry_run_reports_mismatch_without_writing(setup_database):
    mod = _load()
    doc = await _ud("s3://b/transformed/u/d.parquet", "csv")  # mismatch

    result = await mod._audit(UserData, apply=False)

    assert result["mismatched"] == 1 and result["fixed"] == 0
    assert (await UserData.get(doc.id)).file_type == "csv"  # unchanged on a dry run


async def test_apply_corrects_file_type_to_the_extension(setup_database):
    mod = _load()
    doc = await _ud("s3://b/transformed/u/d.parquet", "csv")

    result = await mod._audit(UserData, apply=True)

    assert result["mismatched"] == 1 and result["fixed"] == 1
    assert (await UserData.get(doc.id)).file_type == "parquet"  # corrected to the object's type


async def test_matching_and_extensionless_rows_are_left_alone(setup_database):
    mod = _load()
    ok = await _ud("s3://b/datasets/u/d.csv", "csv")            # matches
    noext = await _ud("s3://b/datasets/u/blob", "csv")          # no extension -> undetermined

    result = await mod._audit(UserData, apply=True)

    assert result["mismatched"] == 0 and result["fixed"] == 0
    assert result["undetermined"] == 1
    assert (await UserData.get(ok.id)).file_type == "csv"
    assert (await UserData.get(noext.id)).file_type == "csv"


async def test_reconciles_dataset_metadata_twin(setup_database):
    mod = _load()
    doc = await DatasetMetadata(
        user_id="u", dataset_id="ds", filename="d", original_filename="d",
        file_type="csv", file_path="s3://b/transformed/u/d.parquet",
        s3_url="s3://b/transformed/u/d.parquet", num_rows=1, num_columns=1,
    ).insert()

    result = await mod._audit(DatasetMetadata, apply=True)

    assert result["fixed"] == 1
    assert (await DatasetMetadata.get(doc.id)).file_type == "parquet"
