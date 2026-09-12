"""Registry: every path that turns a stored URL or key into an S3 download goes
through the one validated core (#531, #567).

Two allowlists and two `get_file_from_s3` implementations is how one of them
ended up without the check; `column_stats.py` bypassed the allowlist for a full
review cycle before anyone noticed. A list of "the download sites" in a test is
stale the day a new one is added, so this test *finds* them: any raw boto3
download call outside the core is a failure, and each public entry point is
shown to refuse a foreign bucket, traversal and an out-of-namespace key before
it touches S3.
"""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
RAW_DOWNLOAD = re.compile(r"\.(download_fileobj|download_file|get_object)\(")

#: The only files allowed to call boto3's download primitives directly.
CORE = {
    "utils/s3.py",  # get_file_from_s3 — the BytesIO reader
    "services/s3_service.py",  # download_file_from_s3 / download_file_bytes
    # Reads keys it wrote itself, in its own bucket, under
    # datasets/{user}/{dataset}/versions/{version}/{file} — a deeper shape than
    # the upload namespaces the core validates. Not a stored-URL reader.
    "services/versioning_service.py",
}


def _py_files():
    return [p for p in APP.rglob("*.py") if "__pycache__" not in p.parts]


class TestOnlyTheCoreDownloads:
    def test_no_raw_download_outside_the_core(self):
        offenders = [
            str(p.relative_to(APP))
            for p in _py_files()
            if RAW_DOWNLOAD.search(p.read_text()) and str(p.relative_to(APP)) not in CORE
        ]
        assert offenders == [], f"raw boto3 download outside the validated core: {offenders}"

    def test_exactly_one_definition_of_each_reader(self):
        defs = {"get_file_from_s3": [], "download_file_from_s3": []}
        for p in _py_files():
            text = p.read_text()
            for name in defs:
                if re.search(rf"^\s*(async\s+)?def {name}\(", text, re.M):
                    defs[name].append(str(p.relative_to(APP)))
        assert defs == {
            "get_file_from_s3": ["utils/s3.py"],
            "download_file_from_s3": ["services/s3_service.py"],
        }

    def test_no_call_site_derives_the_bucket_from_the_environment_itself(self):
        # #567 AC4: resolve_s3_bucket()/allowed_bucket() are the resolvers.
        pattern = re.compile(r"""os\.getenv\(\s*["'](AWS_S3_BUCKET|AWS_BUCKET_NAME|S3_BUCKET_NAME|S3_BUCKET)["']""")
        allowed = {
            "config.py",
            "utils/s3.py",
            "services/s3_service.py",
            # Not download sites: /health/ready reports which bucket is configured,
            # and the upload route checks the variable is present before writing.
            # Neither turns a stored URL into a read.
            "api/routes/health.py",
            "api/routes/upload.py",
        }
        offenders = sorted(
            str(p.relative_to(APP))
            for p in _py_files()
            if pattern.search(p.read_text()) and str(p.relative_to(APP)) not in allowed
        )
        assert offenders == [], offenders


FOREIGN = "https://victim-bucket.s3.amazonaws.com/datasets/user1/file.csv"
TRAVERSAL = "https://test-bucket.s3.amazonaws.com/datasets/../../admin/secrets.csv"
OUTSIDE = "https://test-bucket.s3.amazonaws.com/unauthorized/path/file.csv"


@pytest.fixture
def own_bucket(monkeypatch):
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("AWS_BUCKET_NAME", "test-bucket")
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)


@pytest.mark.parametrize("bad_url", [FOREIGN, TRAVERSAL, OUTSIDE])
class TestEveryEntryPointRefuses:
    def test_utils_get_file_from_s3(self, own_bucket, bad_url):
        from app.utils import s3 as utils_s3

        client = MagicMock()
        with patch.object(utils_s3, "get_s3_client", return_value=client):
            with pytest.raises(ValueError):
                utils_s3.get_file_from_s3(bad_url)
        client.download_fileobj.assert_not_called()
        client.head_object.assert_not_called()

    def test_service_download_file_from_s3(self, own_bucket, bad_url):
        from app.services import s3_service

        client = MagicMock()
        with patch.object(s3_service, "create_s3_client", return_value=client):
            with pytest.raises(Exception):  # noqa: B017 - ValueError, or the breaker's wrapper
                s3_service.download_file_from_s3(bad_url)
        client.download_file.assert_not_called()
        client.head_object.assert_not_called()

    def test_service_load_dataframe_from_s3(self, own_bucket, bad_url):
        from app.services import s3_service

        client = MagicMock()
        with patch.object(s3_service, "create_s3_client", return_value=client):
            with pytest.raises(Exception):  # noqa: B017
                s3_service.load_dataframe_from_s3(bad_url)
        client.download_file.assert_not_called()


@pytest.mark.asyncio
async def test_download_file_bytes_validates_the_key(own_bucket):
    from app.services.s3_service import S3Service

    svc = S3Service.__new__(S3Service)
    svc.bucket_name = "test-bucket"
    svc.is_mock_mode = False
    svc.s3_client = MagicMock()
    for key in ("datasets/../../admin/secrets.csv", "/etc/passwd", "unauthorized/x.csv"):
        with pytest.raises(ValueError):
            await svc.download_file_bytes(key)
    svc.s3_client.get_object.assert_not_called()
