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
        # The move writes with a targeted set() (#723), so that is where Mongo fails.
        with patch.object(DatasetMetadata, "set", new_callable=AsyncMock, side_effect=RuntimeError("mongo down")), \
             caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                await record_new_file(meta, NEW)

        assert "half-moved" in caplog.text and "UserData" in caplog.text
        assert (await UserData.get(ud.id)).s3_url == NEW, "the twin moved before the failure"

    async def test_the_twin_takes_the_new_shape_too(self, setup_database):
        """codex: the caller updates rows/columns on the document it holds; the twin's legacy
        readers describe the same file, so those follow the move."""
        meta, ud = await _twins()
        meta.num_rows, meta.num_columns, meta.columns = 2, 3, ["a", "b", "c"]
        await record_new_file(meta, NEW)

        ud2 = await UserData.get(ud.id)
        assert (ud2.num_rows, ud2.num_columns, ud2.columns) == (2, 3, ["a", "b", "c"])

    async def test_file_type_follows_the_new_object(self, setup_database):
        """codex/#524: writers upload parquet; a CSV-uploaded dataset must not keep file_type=csv,
        or readers that dispatch on it parse parquet bytes as CSV."""
        meta, ud = await _twins()
        assert (meta.file_type, ud.file_type) == ("csv", None)
        await record_new_file(meta, NEW)  # .parquet

        assert (await DatasetMetadata.get(meta.id)).file_type == "parquet"
        assert (await UserData.get(ud.id)).file_type == "parquet"

    def test_unknown_extensions_leave_the_type_alone(self):
        from app.services.dataset_link import _file_type_of

        assert _file_type_of("s3://b/x/y.parquet?X-Amz-Signature=1") == "parquet"
        assert _file_type_of("s3://b/x/y.PARQUET") == "parquet"
        assert _file_type_of("s3://b/x/no-extension") is None

    async def test_a_failure_before_anything_moved_is_not_a_half_move(self, setup_database, caplog):
        """The ERROR is for the half-moved state only: a failure on the FIRST save raises plainly."""
        import logging
        from unittest.mock import AsyncMock, patch

        meta, ud = await _twins()
        with patch.object(UserData, "set", new_callable=AsyncMock, side_effect=RuntimeError("mongo down")), \
             caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                await record_new_file(meta, NEW)

        assert "half-moved" not in caplog.text
        assert (await DatasetMetadata.get(meta.id)).s3_url == OLD  # nothing moved

    async def test_an_unsaved_document_moves_without_a_twin_lookup_by_id(self, setup_database):
        """`doc.id is None` skips the re-read; the twin is still found through the stored URL."""
        _, ud = await _twins()
        unsaved = DatasetMetadata(
            user_id=USER, dataset_id="unsaved", filename="d.csv", original_filename="d.csv", file_type="csv",
            file_path=f"datasets/{USER}/ds_d.csv", s3_url=OLD, num_rows=3, num_columns=2,
        )
        await record_new_file(unsaved, NEW)
        assert unsaved.s3_url == NEW and unsaved.id is not None  # save() inserted it
        assert (await UserData.get(ud.id)).s3_url == NEW


class TestRevisitedUrlLeavesSuperseded:
    """#629: history undo/redo revisit URLs, so a move BACK to a previously-superseded
    url must not leave the now-current file in `superseded_s3_urls` — erasure sweeps
    that list and would delete the live file."""

    async def test_moving_back_removes_the_current_url_from_superseded(self, setup_database):
        meta, ud = await _twins(OLD)
        await record_new_file(meta, NEW)  # move off OLD -> OLD superseded, current NEW
        meta2 = await DatasetMetadata.get(meta.id)
        assert OLD in (meta2.superseded_s3_urls or [])

        await record_new_file(meta2, OLD)  # revisit OLD (an undo)
        meta3 = await DatasetMetadata.get(meta.id)
        ud3 = await UserData.get(ud.id)

        assert (meta3.file_path, meta3.s3_url) == (OLD, OLD)
        assert OLD not in (meta3.superseded_s3_urls or []), "the current file must not be in superseded"
        assert NEW in (meta3.superseded_s3_urls or []), "the file moved off should be superseded"
        assert ud3.s3_url == OLD, "the twin must follow back too"


class TestAConcurrentWriteSurvivesTheMove:
    """#723: the move used to end in a full-document save() of the in-memory snapshot, so
    any field another writer changed meanwhile was silently reverted (#520's clobber class).
    Only the fields the move owns are written now."""

    async def test_a_field_changed_after_the_caller_loaded_the_dataset_is_kept(self, setup_database):
        meta, ud = await _twins()
        stale = await DatasetMetadata.get(meta.id)  # what a transformation holds while it runs
        # Processing finishes meanwhile and stores statistics on both twins.
        await DatasetMetadata.find_one(DatasetMetadata.id == meta.id).update({"$set": {"statistics": {"rows": 3}}})
        await UserData.find_one(UserData.id == ud.id).update({"$set": {"statistics": {"rows": 3}}})

        stale.num_rows = 2  # the caller's own change still lands
        await record_new_file(stale, NEW)

        meta2, ud2 = await DatasetMetadata.get(meta.id), await UserData.get(ud.id)
        assert meta2.statistics == {"rows": 3}, "the move must not revert another writer's field"
        assert ud2.statistics == {"rows": 3}
        assert (meta2.s3_url, meta2.num_rows, ud2.s3_url, ud2.num_rows) == (NEW, 2, NEW, 2)

    async def test_a_write_to_the_twin_between_its_read_and_the_move_is_kept(self, setup_database):
        from unittest.mock import patch

        meta, ud = await _twins()
        real_find_one = UserData.find_one

        raced = []

        def find_then_race(*args, **kwargs):
            query = real_find_one(*args, **kwargs)
            if raced:  # Beanie's own writes call find_one too; only the twin lookup races
                return query
            raced.append(True)

            async def race():
                twin = await query
                await real_find_one(UserData.id == ud.id).update({"$set": {"pii_masked": True}})
                return twin  # the in-memory twin no longer matches the database

            return race()

        with patch.object(UserData, "find_one", side_effect=find_then_race):
            await record_new_file(meta, NEW)

        ud2 = await UserData.get(ud.id)
        assert ud2.pii_masked is True and ud2.s3_url == NEW

    async def test_a_schema_field_the_caller_appended_is_stored(self, setup_database):
        """The feature builder appends a SchemaField before moving the dataset; the
        targeted set() must encode and persist it (the full save() used to)."""
        from app.models.dataset import SchemaField

        meta, ud = await _twins()
        meta.columns = ["a", "b", "ratio"]
        meta.data_schema.append(SchemaField(
            field_name="ratio", field_type="numeric", inferred_dtype="float64",
            unique_values=3, missing_values=0,
        ))
        await record_new_file(meta, NEW)

        stored = await DatasetMetadata.get(meta.id)
        assert [f.field_name for f in stored.data_schema] == ["ratio"]
        assert stored.columns == ["a", "b", "ratio"]
        assert (await UserData.get(ud.id)).data_schema == [], "the schema is not copied to the twin"


class TestEnsureMetadataTwin:
    """#850: a transformation on a UI upload (a UserData id) runs on its metadata twin."""

    async def test_a_metadata_id_resolves_to_itself(self, setup_database):
        from app.services.dataset_link import ensure_metadata_twin

        meta, _ = await _twins()
        assert (await ensure_metadata_twin("ds", USER)).id == meta.id

    async def test_an_upload_with_a_twin_resolves_to_that_twin(self, setup_database):
        from app.services.dataset_link import ensure_metadata_twin

        meta, ud = await _twins()
        resolved = await ensure_metadata_twin(str(ud.id), USER)
        assert resolved.id == meta.id, "the existing twin is reused, not duplicated"
        assert await DatasetMetadata.find(DatasetMetadata.user_id == USER).count() == 1

    async def test_an_upload_without_a_twin_gets_one_even_if_the_base_version_fails(self, setup_database):
        """The base version is best-effort: S3 is in mock mode here, so it cannot be
        written, and the twin must still exist for the transformation to run on."""
        from app.services.dataset_link import ensure_metadata_twin

        ud = await UserData(
            user_id=USER, filename="u.csv", original_filename="u.csv", s3_url=OLD,
            num_rows=3, num_columns=2, data_schema=[], file_type="csv", columns=["a", "b"],
        ).insert()
        twin = await ensure_metadata_twin(str(ud.id), USER)
        assert (twin.dataset_id, twin.s3_url, twin.num_rows, twin.columns) == (str(ud.id), OLD, 3, ["a", "b"])

    async def test_unknown_or_foreign_ids_resolve_to_nothing(self, setup_database):
        from app.services.dataset_link import ensure_metadata_twin

        _, ud = await _twins()
        assert await ensure_metadata_twin("not-an-id", USER) is None
        assert await ensure_metadata_twin(str(ud.id), "someone_else") is None

    async def test_an_upload_stored_as_txt_still_gets_a_valid_twin(self, setup_database):
        """/upload/ accepts TSV and stores file_type="txt", which DatasetMetadata refuses;
        the twin must not turn a dataset that used to 404 into a 500 (#850 review)."""
        from app.services.dataset_link import ensure_metadata_twin

        ud = await UserData(
            user_id=USER, filename="t.txt", original_filename="t.txt",
            s3_url=f"s3://test-bucket/datasets/{USER}/t.txt",
            num_rows=2, num_columns=2, data_schema=[], file_type="txt",
        ).insert()
        twin = await ensure_metadata_twin(str(ud.id), USER)
        assert twin.file_type == "csv"

    async def test_the_bulk_service_resolves_an_upload_id(self, setup_database):
        """The bulk column operations sit on the same Prepare stage (#850 review)."""
        from app.models.bulk_transformation import ColumnSelectionPattern, PatternType
        from app.services.bulk_transformation_service import BulkTransformationService

        ud = await UserData(
            user_id=USER, filename="b.csv", original_filename="b.csv",
            s3_url=f"s3://test-bucket/datasets/{USER}/b.csv",
            num_rows=2, num_columns=2, data_schema=[], file_type="csv",
        ).insert()
        result = await BulkTransformationService().select_columns_by_pattern(
            user_id=USER, dataset_id=str(ud.id),
            pattern=ColumnSelectionPattern(pattern_type=PatternType.DATA_TYPE, criteria={"types": ["numeric"]}),
        )
        assert result == []  # resolved (no NotFoundError); the new twin has no schema yet
