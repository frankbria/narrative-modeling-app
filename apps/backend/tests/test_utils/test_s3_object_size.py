"""#781: the size of a stored object, for bookkeeping. It never raises: a move that
cannot learn the new file's size still happens, and keeps the size it had."""

from botocore.exceptions import ClientError

from app.utils import s3

URL = "s3://test-bucket/transformed/user-1/ds_1.parquet"


class _Client:
    def __init__(self, answer):
        self.answer = answer
        self.asked: list[tuple[str, str]] = []

    def head_object(self, Bucket, Key):  # noqa: N803 (boto3's own argument names)
        self.asked.append((Bucket, Key))
        if isinstance(self.answer, Exception):
            raise self.answer
        return {"ContentLength": self.answer}


def _with(monkeypatch, client):
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    monkeypatch.setattr(s3, "get_s3_client", lambda: client)


def test_it_is_the_objects_content_length(monkeypatch):
    client = _Client(4096)
    _with(monkeypatch, client)

    assert s3.object_size(URL) == 4096
    assert client.asked == [("test-bucket", "transformed/user-1/ds_1.parquet")]


def test_with_no_storage_configured_there_is_no_size(monkeypatch):
    _with(monkeypatch, None)
    assert s3.object_size(URL) is None


def test_an_object_that_cannot_be_read_has_no_size(monkeypatch):
    missing = ClientError({"Error": {"Code": "404"}}, "HeadObject")
    _with(monkeypatch, _Client(missing))
    assert s3.object_size(URL) is None


def test_a_location_outside_the_bucket_is_not_asked_about(monkeypatch):
    client = _Client(4096)
    _with(monkeypatch, client)

    assert s3.object_size("s3://someone-elses-bucket/transformed/user-1/ds_1.parquet") is None
    assert client.asked == []
