"""Coverage for the #581 reconciliation script, which moves real objects and rewrites
real rows in the production bucket.

The planning logic is pure and tested directly; the end-to-end path runs against a
real S3 (LocalStack) and the real test database — no mocks — because "copied,
verified, row rewritten, original deleted, orphan untouched" is exactly the kind of
sequence a mocked client would rubber-stamp.
"""

import importlib.util
import uuid
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "reconcile_unprefixed_s3_keys.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("reconcile_unprefixed_s3_keys", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


U1 = str(uuid.uuid4())
U2 = str(uuid.uuid4())


class TestClassification:
    def test_bare_uuid_keys_are_unprefixed(self):
        m = _load()
        assert m.is_unprefixed_dataset_key(f"{U1}.csv")
        assert m.is_unprefixed_dataset_key(f"masked_{U1}.csv")
        assert m.is_unprefixed_dataset_key(f"{U1}.xlsx")
        assert m.is_unprefixed_dataset_key(U1)  # no extension

    def test_everything_else_is_left_alone(self):
        m = _load()
        assert not m.is_unprefixed_dataset_key(f"datasets/u/{U1}.csv")
        assert not m.is_unprefixed_dataset_key(f"models/{U1}.joblib")
        assert not m.is_unprefixed_dataset_key("report.csv")
        assert not m.is_unprefixed_dataset_key(f"{U1}.csv/child")
        assert not m.is_unprefixed_dataset_key("")

    def test_new_key_keeps_the_basename_under_the_owner(self):
        m = _load()
        assert m.new_key_for(f"masked_{U1}.csv", "owner-1") == f"datasets/owner-1/masked_{U1}.csv"


class TestPlan:
    def test_partitions_moves_and_orphans(self):
        m = _load()
        plan = m.plan(
            [f"{U1}.csv", f"{U2}.csv", f"masked_{U1}.csv"],
            {f"{U1}.csv": "owner-1", f"masked_{U1}.csv": "owner-1"},
        )
        assert [(mv.old_key, mv.new_key, mv.user_id) for mv in plan.moves] == [
            (f"{U1}.csv", f"datasets/owner-1/{U1}.csv", "owner-1"),
            (f"masked_{U1}.csv", f"datasets/owner-1/masked_{U1}.csv", "owner-1"),
        ]
        assert plan.orphans == [f"{U2}.csv"]

    def test_an_owner_of_none_is_an_orphan_not_a_move(self):
        m = _load()
        plan = m.plan([f"{U1}.csv"], {f"{U1}.csv": None})
        assert plan.moves == [] and plan.orphans == [f"{U1}.csv"]


@pytest.mark.integration
@pytest.mark.asyncio
class TestReconcileAgainstRealS3:
    """LocalStack + real Mongo. Skips (locally) when LocalStack is down."""

    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch, test_s3_bucket):
        # The app's URL parser attributes endpoint-style URLs to a bucket only
        # when it knows the endpoint.
        monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
        monkeypatch.setenv("AWS_BUCKET_NAME", test_s3_bucket)

    async def _seed(self, s3_client, bucket, key, owner, *, with_row=True, with_meta=False):
        from app.models.dataset import DatasetMetadata
        from app.models.user_data import UserData

        body = f"id\n{key}\n".encode()
        s3_client.put_object(Bucket=bucket, Key=key, Body=body)
        url = f"http://localhost:4566/{bucket}/{key}"
        row = None
        if with_row:
            row = await UserData(
                user_id=owner,
                filename="d.csv",
                original_filename="d.csv",
                s3_url=url,
                file_path=key,
                num_rows=1,
                num_columns=1,
                data_schema=[],
            ).insert()
        if with_meta:
            await DatasetMetadata(
                user_id=owner,
                dataset_id=f"ds-{key}",
                filename="d.csv",
                original_filename="d.csv",
                file_type="csv",
                file_path=key,
                s3_url=url,
                num_rows=1,
                num_columns=1,
            ).insert()
        return body, url, row

    def _exists(self, s3_client, bucket, key) -> bool:
        from botocore.exceptions import ClientError

        try:
            s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    async def test_dry_run_changes_nothing_and_reports_the_work(
        self, setup_database, s3_client, test_s3_bucket
    ):
        m = _load()
        from app.models.user_data import UserData

        key = f"{uuid.uuid4()}.csv"
        _, url, row = await self._seed(s3_client, test_s3_bucket, key, "owner-a")

        report = await m.reconcile(
            s3_client, test_s3_bucket, UserData.get_motor_collection().database, apply=False
        )

        assert report.unprefixed == 1 and report.planned == 1 and report.moved == 0
        assert self._exists(s3_client, test_s3_bucket, key)
        assert not self._exists(s3_client, test_s3_bucket, f"datasets/owner-a/{key}")
        assert (await UserData.get(row.id)).s3_url == url

    async def test_apply_copies_verifies_rewrites_then_deletes(
        self, setup_database, s3_client, test_s3_bucket
    ):
        m = _load()
        from app.models.dataset import DatasetMetadata
        from app.models.user_data import UserData

        key = f"masked_{uuid.uuid4()}.csv"
        body, url, row = await self._seed(
            s3_client, test_s3_bucket, key, "owner-b", with_meta=True
        )
        new_key = f"datasets/owner-b/{key}"

        report = await m.reconcile(
            s3_client, test_s3_bucket, UserData.get_motor_collection().database, apply=True
        )

        assert report.moved == 1 and report.orphans == 0 and report.rows_rewritten == 2
        assert self._exists(s3_client, test_s3_bucket, new_key)
        assert not self._exists(s3_client, test_s3_bucket, key)
        assert s3_client.get_object(Bucket=test_s3_bucket, Key=new_key)["Body"].read() == body
        ud = await UserData.get(row.id)
        assert ud.s3_url == f"http://localhost:4566/{test_s3_bucket}/{new_key}"
        assert ud.file_path == new_key
        meta = await DatasetMetadata.find_one(DatasetMetadata.dataset_id == f"ds-{key}")
        assert meta.s3_url.endswith(new_key) and meta.file_path == new_key

    async def test_an_orphan_is_reported_and_never_touched(
        self, setup_database, s3_client, test_s3_bucket
    ):
        m = _load()
        from app.models.user_data import UserData

        key = f"{uuid.uuid4()}.csv"
        await self._seed(s3_client, test_s3_bucket, key, "nobody", with_row=False)

        report = await m.reconcile(
            s3_client, test_s3_bucket, UserData.get_motor_collection().database, apply=True
        )

        assert report.orphans == 1 and report.moved == 0
        assert self._exists(s3_client, test_s3_bucket, key)
        assert report.exit_code == 1  # unreconciled objects remain

    async def test_a_multipart_uploaded_object_is_still_moved(
        self, setup_database, s3_client, test_s3_bucket
    ):
        """Objects over boto3's multipart threshold carry a ``<md5>-N`` ETag that no
        copy reproduces; verification must fall back to the bytes (codex review)."""
        import io

        from boto3.s3.transfer import TransferConfig

        m = _load()
        from app.models.user_data import UserData

        key = f"{uuid.uuid4()}.csv"
        body = b"x" * (3 * 1024 * 1024)
        s3_client.upload_fileobj(
            io.BytesIO(body),
            test_s3_bucket,
            key,
            Config=TransferConfig(multipart_threshold=1024 * 1024, multipart_chunksize=1024 * 1024),
        )
        assert "-" in s3_client.head_object(Bucket=test_s3_bucket, Key=key)["ETag"], "not multipart"
        await UserData(
            user_id="owner-mp",
            filename="d.csv",
            original_filename="d.csv",
            s3_url=f"http://localhost:4566/{test_s3_bucket}/{key}",
            file_path=key,
            num_rows=1,
            num_columns=1,
            data_schema=[],
        ).insert()

        report = await m.reconcile(
            s3_client, test_s3_bucket, UserData.get_motor_collection().database, apply=True
        )

        assert report.copy_failures == 0 and report.moved == 1
        new_key = f"datasets/owner-mp/{key}"
        assert s3_client.get_object(Bucket=test_s3_bucket, Key=new_key)["Body"].read() == body
        assert not self._exists(s3_client, test_s3_bucket, key)

    async def test_prefixed_objects_are_not_candidates(
        self, setup_database, s3_client, test_s3_bucket
    ):
        m = _load()
        from app.models.user_data import UserData

        key = f"datasets/owner-c/{uuid.uuid4()}.csv"
        await self._seed(s3_client, test_s3_bucket, key, "owner-c")

        report = await m.reconcile(
            s3_client, test_s3_bucket, UserData.get_motor_collection().database, apply=True
        )

        assert report.unprefixed == 0 and report.moved == 0
        assert self._exists(s3_client, test_s3_bucket, key)
