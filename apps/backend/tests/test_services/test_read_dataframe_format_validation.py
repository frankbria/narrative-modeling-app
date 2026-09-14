"""_read_dataframe validates the object's bytes against its declared file_type (#524).

A transformation that rewrote s3_url to a .parquet object while file_type stayed
'csv' made every reader parse parquet bytes as CSV and fail opaquely. The loader
now raises a clear FormatMismatchError instead.
"""

import tempfile

import pandas as pd
import pytest

from app.services.s3_service import FormatMismatchError, _read_dataframe


def _write_csv(df: pd.DataFrame) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    import os
    os.close(fd)
    df.to_csv(path, index=False)
    return path


def _write_parquet(df: pd.DataFrame) -> str:
    fd, path = tempfile.mkstemp(suffix=".parquet")
    import os
    os.close(fd)
    df.to_parquet(path, index=False)
    return path


_DF = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


@pytest.mark.unit
def test_parquet_object_declared_csv_raises_clear_error():
    """The exact #524 bug: s3_url→.parquet, file_type='csv'."""
    path = _write_parquet(_DF)
    with pytest.raises(FormatMismatchError, match="Parquet"):
        _read_dataframe(path, "csv", None)


@pytest.mark.unit
def test_csv_object_declared_parquet_raises_clear_error():
    path = _write_csv(_DF)
    with pytest.raises(FormatMismatchError, match="not Parquet"):
        _read_dataframe(path, "parquet", None)


@pytest.mark.unit
def test_matching_parquet_loads():
    path = _write_parquet(_DF)
    out = _read_dataframe(path, "parquet", None)
    assert list(out.columns) == ["a", "b"] and len(out) == 3


@pytest.mark.unit
def test_matching_csv_loads():
    path = _write_csv(_DF)
    out = _read_dataframe(path, "csv", None)
    assert list(out.columns) == ["a", "b"] and len(out) == 3


@pytest.mark.unit
def test_csv_starting_with_par1_is_not_rejected():
    """A valid CSV whose first bytes are 'PAR1' (e.g. a column named PAR1) must load
    as csv — the footer check prevents a header-only false positive (#524, codex)."""
    import os
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    pd.DataFrame({"PAR1col": [1, 2], "b": [3, 4]}).to_csv(path, index=False)
    with open(path, "rb") as fh:
        assert fh.read(4) == b"PAR1"  # precondition: header really starts with PAR1
    out = _read_dataframe(path, "csv", None)
    assert list(out.columns) == ["PAR1col", "b"] and len(out) == 2


@pytest.mark.unit
def test_infer_path_still_works_without_declared_type():
    """file_type=None keeps the csv-then-parquet inference (no declared type to check)."""
    csv_path = _write_csv(_DF)
    assert len(_read_dataframe(csv_path, None, None)) == 3
    parquet_path = _write_parquet(_DF)
    assert len(_read_dataframe(parquet_path, None, None)) == 3
