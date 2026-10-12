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


# #858: with no declared type the reader tried CSV first, then Parquet. `read_csv` does not
# fail on JSON, it returns junk columns, and a transformation then wrote that junk back
# over the dataset. The untyped path now goes by what the bytes are.


def _write(suffix: str, write) -> str:
    import os

    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    write(path)
    return path


_PEOPLE = pd.DataFrame({"id": [1, 2, 3], "name": ["ann", "bo", "cy"], "score": [1.5, 2.5, 3.5]})


@pytest.mark.unit
class TestTheUntypedReaderGoesByTheBytes:
    def test_a_json_array_of_records_keeps_its_columns(self):
        path = _write(".json", lambda p: _PEOPLE.to_json(p, orient="records"))

        out = _read_dataframe(path, None, None)

        assert list(out.columns) == ["id", "name", "score"] and len(out) == 3

    def test_a_json_object_of_columns_keeps_its_columns(self):
        path = _write(".json", lambda p: _PEOPLE.to_json(p, orient="columns"))

        assert list(_read_dataframe(path, None, None).columns) == ["id", "name", "score"]

    def test_json_with_leading_whitespace_and_a_bom_is_still_json(self):
        body = "﻿ \n" + _PEOPLE.to_json(orient="records")
        path = _write(".json", lambda p: open(p, "w", encoding="utf-8").write(body))

        assert list(_read_dataframe(path, None, None).columns) == ["id", "name", "score"]

    def test_an_excel_workbook_keeps_its_columns(self):
        path = _write(".xlsx", lambda p: _PEOPLE.to_excel(p, index=False))

        out = _read_dataframe(path, None, None)

        assert list(out.columns) == ["id", "name", "score"] and len(out) == 3

    def test_csv_and_parquet_read_as_before(self):
        for path in (_write_csv(_PEOPLE), _write_parquet(_PEOPLE)):
            assert list(_read_dataframe(path, None, None).columns) == ["id", "name", "score"]

    def test_a_csv_whose_header_opens_with_a_bracket_is_still_a_csv(self):
        path = _write(".csv", lambda p: open(p, "w").write("[id],name\n1,ann\n2,bo\n"))

        out = _read_dataframe(path, None, None)

        assert list(out.columns) == ["[id]", "name"] and len(out) == 2

    @pytest.mark.parametrize("suffix, write", [
        (".json", lambda p: _PEOPLE.to_json(p, orient="records")),
        (".xlsx", lambda p: _PEOPLE.to_excel(p, index=False)),
        (".csv", lambda p: _PEOPLE.to_csv(p, index=False)),
        (".parquet", lambda p: _PEOPLE.to_parquet(p, index=False)),
    ])
    def test_a_row_limit_is_honoured_for_every_kind(self, suffix, write):
        assert len(_read_dataframe(_write(suffix, write), None, 2)) == 2

    def test_an_old_binary_excel_file_is_recognised_by_its_header(self):
        from app.services.s3_service import _kind_of

        path = _write(".xls", lambda p: open(p, "wb").write(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 64))

        assert _kind_of(path) == "xls"


@pytest.mark.unit
def test_excel_is_a_declared_type_the_reader_knows():
    """/upload/secure stores "excel" for an .xls or .xlsx file; the typed path answered
    "Unsupported file type: excel" for it."""
    path = _write(".xlsx", lambda p: _PEOPLE.to_excel(p, index=False))

    assert list(_read_dataframe(path, "excel", None).columns) == ["id", "name", "score"]
