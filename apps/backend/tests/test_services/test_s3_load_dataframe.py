"""Tests for the centralized S3 download+parse+cleanup helper (issue #280).

The core regression these guard: `download_file_from_s3` returns a
NamedTemporaryFile(delete=False) path, and callers used to leak it (never
unlink, or unlink only on success). `load_dataframe_from_s3` must ALWAYS
remove the temp file — on success and on parse error.
"""
import os
import tempfile
from unittest.mock import patch

import pytest

from app.services import s3_service


def _write_temp(content: bytes, suffix: str = "") -> str:
    """Create a real temp file (no auto-delete) and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


def test_temp_file_removed_on_success():
    path = _write_temp(b"a,b\n1,2\n")
    with patch.object(s3_service, "download_file_from_s3", return_value=path):
        df = s3_service.load_dataframe_from_s3("s3://bucket/datasets/u/f.csv", "csv")
    assert list(df.columns) == ["a", "b"]
    assert not os.path.exists(path), "temp file must be cleaned up on success"


def test_temp_file_removed_on_parse_error():
    """The leak the issue is about: a parse failure must still unlink."""
    path = _write_temp(b"not,valid\x00parquet")
    with patch.object(s3_service, "download_file_from_s3", return_value=path):
        with pytest.raises(Exception):
            # force parquet parse on non-parquet bytes → raises
            s3_service.load_dataframe_from_s3("s3://bucket/datasets/u/f.parquet", "parquet")
    assert not os.path.exists(path), "temp file must be cleaned up even on parse error"


@pytest.mark.parametrize("file_type", ["csv", "json"])
def test_parses_by_file_type(file_type):
    if file_type == "csv":
        path = _write_temp(b"x,y\n1,2\n")
    else:
        path = _write_temp(b'[{"x": 1, "y": 2}]')
    with patch.object(s3_service, "download_file_from_s3", return_value=path):
        df = s3_service.load_dataframe_from_s3(f"s3://b/datasets/u/f.{file_type}", file_type)
    assert df.iloc[0]["x"] == 1
    assert not os.path.exists(path)


def test_unknown_file_type_raises_and_cleans_up():
    path = _write_temp(b"x,y\n1,2\n")
    with patch.object(s3_service, "download_file_from_s3", return_value=path):
        with pytest.raises(ValueError, match="Unsupported file type"):
            s3_service.load_dataframe_from_s3("s3://b/datasets/u/f.bin", "bin")
    assert not os.path.exists(path)


def test_infer_path_reads_extensionless_csv():
    """download_file_from_s3 temp files have no suffix; file_type=None must infer."""
    path = _write_temp(b"a,b\n3,4\n")  # no suffix
    with patch.object(s3_service, "download_file_from_s3", return_value=path):
        df = s3_service.load_dataframe_from_s3("s3://b/datasets/u/f", None)
    assert df.iloc[0]["a"] == 3
    assert not os.path.exists(path)


def test_nrows_limits_rows():
    path = _write_temp(b"a\n1\n2\n3\n")
    with patch.object(s3_service, "download_file_from_s3", return_value=path):
        df = s3_service.load_dataframe_from_s3("s3://b/datasets/u/f.csv", "csv", nrows=2)
    assert len(df) == 2
    assert not os.path.exists(path)


def test_download_file_from_s3_cleans_up_on_download_failure(monkeypatch):
    """Root-cause leak (codex review): the temp file is created BEFORE the
    s3 download; a failed download must not leave it (or a partial) behind."""
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    captured = {}

    class FakeClient:
        def head_object(self, Bucket, Key):
            return {"ContentLength": 10}

        def download_file(self, bucket, key, path):
            captured["path"] = path  # temp file exists on disk at this point
            raise RuntimeError("network boom")  # not ClientError → no breaker retry

    monkeypatch.setattr(s3_service, "create_s3_client", lambda: FakeClient())
    with pytest.raises(RuntimeError):
        s3_service.download_file_from_s3("s3://test-bucket/datasets/u/f.csv")

    assert captured.get("path"), "download_file should have been reached"
    assert not os.path.exists(captured["path"]), "temp file must be removed on download failure"


def test_get_dataframe_from_s3_delegates_and_cleans_up():
    """data_utils wrapper (issue's 4th caller) routes through the helper, whose
    finally block guarantees cleanup; verify the infer/nrows API still works."""
    import asyncio

    from app.services.transformation_engine import data_utils

    path = _write_temp(b"a,b\n1,2\n3,4\n")  # extensionless → infer csv
    with patch.object(s3_service, "download_file_from_s3", return_value=path):
        df = asyncio.run(data_utils.get_dataframe_from_s3("s3://b/datasets/u/f", nrows=1))
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 1  # nrows honored
    assert not os.path.exists(path), "get_dataframe_from_s3 must clean up the temp file"
