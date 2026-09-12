"""#467: a transformation must move BOTH dual-written twins to the new file.

`DatasetMetadata` and legacy `UserData` are linked only by `(user_id, s3_url)`. Writing
the transformed URL into one side severed the join — erasure lost the PII-carrying
twin, and training (which reads `UserData.s3_url`) kept using the pre-transform file.
Real documents in the test database; no S3 involved (the helper only moves pointers).
"""
import pytest

from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData
from app.services.dataset_link import record_new_file

pytestmark = pytest.mark.asyncio

USER = "link_user"
OLD = f"s3://test-bucket/datasets/{USER}/ds_d.csv"
NEW = f"s3://test-bucket/transformed/{USER}/ds_1.parquet"
NEWER = f"s3://test-bucket/transformed/{USER}/ds_2.parquet"


async def _twins(s3_url: str = OLD):
    meta = await DatasetMetadata(
        user_id=USER, dataset_id="ds", filename="d.csv", original_filename="d.csv", file_type="csv",
        file_path=f"datasets/{USER}/ds_d.csv", s3_url=s3_url, num_rows=3, num_columns=2,
    ).insert()
    ud = await UserData(
        user_id=USER, filename="d.csv", original_filename="d.csv", s3_url=s3_url,
        num_rows=3, num_columns=2, data_schema=[], contains_pii=True,
    ).insert()
    return meta, ud


class TestRecordNewFile:
    async def test_moving_the_metadata_moves_its_twin(self, setup_database):
        meta, ud = await _twins()
        await record_new_file(meta, NEW)

        meta2 = await DatasetMetadata.get(meta.id)
        ud2 = await UserData.get(ud.id)
        assert (meta2.file_path, meta2.s3_url) == (NEW, NEW)
        assert (ud2.file_path, ud2.s3_url) == (NEW, NEW), "the twin must follow, or the link is severed"
        # the join is intact: same user, same s3_url
        assert await UserData.find_one(UserData.user_id == USER, UserData.s3_url == meta2.s3_url) is not None

    async def test_moving_the_user_data_moves_its_twin(self, setup_database):
        meta, ud = await _twins()
        await record_new_file(ud, NEW)

        assert (await DatasetMetadata.get(meta.id)).s3_url == NEW
        assert (await UserData.get(ud.id)).s3_url == NEW

    async def test_the_original_upload_is_remembered_once(self, setup_database):
        meta, _ = await _twins()
        await record_new_file(meta, NEW)
        await record_new_file(await DatasetMetadata.get(meta.id), NEWER)

        meta3 = await DatasetMetadata.get(meta.id)
        assert meta3.s3_url == NEWER
        assert meta3.source_s3_url == OLD, "the first move records the upload; later moves keep it"

    async def test_a_dataset_without_a_twin_still_moves(self, setup_database):
        meta = await DatasetMetadata(
            user_id=USER, dataset_id="lonely", filename="d.csv", original_filename="d.csv", file_type="csv",
            file_path=f"datasets/{USER}/lonely.csv", s3_url=f"s3://test-bucket/datasets/{USER}/lonely.csv",
            num_rows=1, num_columns=1,
        ).insert()
        await record_new_file(meta, NEW)
        assert (await DatasetMetadata.get(meta.id)).s3_url == NEW

    async def test_another_users_document_at_the_same_url_is_not_touched(self, setup_database):
        meta, ud = await _twins()
        other = await UserData(
            user_id="someone-else", filename="d.csv", original_filename="d.csv", s3_url=OLD,
            num_rows=3, num_columns=2, data_schema=[],
        ).insert()
        await record_new_file(meta, NEW)
        assert (await UserData.get(other.id)).s3_url == OLD
        assert (await UserData.get(ud.id)).s3_url == NEW

    async def test_overlapping_moves_do_not_re_sever_the_link(self, setup_database):
        """codex: the second of two overlapping transformations holds a stale in-memory
        document; it must find the twin at the CURRENT location, not the stale one."""
        meta, ud = await _twins()
        stale = await DatasetMetadata.get(meta.id)  # loaded before the first move
        await record_new_file(meta, NEW)
        await record_new_file(stale, NEWER)  # still believes s3_url == OLD

        meta3 = await DatasetMetadata.get(meta.id)
        ud3 = await UserData.get(ud.id)
        assert meta3.s3_url == NEWER
        assert ud3.s3_url == NEWER, "the twin was left at the first move's location — link severed"
        assert meta3.source_s3_url == OLD

    async def test_a_half_failure_is_logged_loudly_and_re_raised(self, setup_database, caplog):
        """No transaction spans the two documents: if the second save fails the join is broken
        either way, so the operator must be told which pair to repair."""
        import logging
        from unittest.mock import AsyncMock, patch

        meta, ud = await _twins()
        with patch.object(DatasetMetadata, "save", new_callable=AsyncMock, side_effect=RuntimeError("mongo down")), \
             caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                await record_new_file(meta, NEW)

        assert "half-moved" in caplog.text and "UserData" in caplog.text
        assert (await UserData.get(ud.id)).s3_url == NEW, "the twin moved before the failure"
