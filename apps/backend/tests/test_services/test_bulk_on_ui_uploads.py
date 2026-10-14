"""#856: the bulk routes take a UI upload's id.

The upload page writes only a `UserData` row and hands its ObjectId to every later
stage. The bulk service looked datasets up with `DatasetMetadata.find_one({"dataset_id":
…})`, so select, preview and apply all answered 404 for it, the bug #850 fixed for the
single-step routes. Real documents; only storage is stubbed.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.models.bulk_transformation import (
    BulkJobStatus,
    BulkTransformationJob,
    ColumnSelectionPattern,
    PatternType,
)
from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData
from app.services.bulk_transformation_service import BulkTransformationService
from app.services.exceptions import NotFoundError, OperationError

pytestmark = pytest.mark.asyncio

USER = "test_user_123"  # what async_authorized_client authenticates as
MOVED = f"s3://test-bucket/transformed/{USER}/bulk.parquet"
MODULE = "app.services.bulk_transformation_service"


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"age": [25.0, None, 40.0], "name": [" a", "b ", "c"], "city": ["x", None, "z"]})


async def _upload(user_id: str = USER, file_type: str = "csv") -> UserData:
    url = f"s3://test-bucket/datasets/{user_id}/people.{file_type}"
    return await UserData(
        user_id=user_id, filename=f"people.{file_type}", original_filename=f"people.{file_type}",
        s3_url=url, num_rows=3, num_columns=3, data_schema=[], file_type=file_type,
        columns=["age", "name", "city"],
    ).insert()


@pytest.fixture
def storage():
    """The dataset's file, and where a finished job's result is written."""
    async def read(_url, *args, **kwargs):
        return _frame()

    with patch(f"{MODULE}.get_dataframe_from_s3", side_effect=read), \
         patch(f"{MODULE}.upload_dataframe_to_s3", new_callable=AsyncMock, return_value=MOVED) as written:
        yield written


async def _finished(service: BulkTransformationService, job: BulkTransformationJob) -> BulkTransformationJob:
    await asyncio.wait_for(service._active_tasks[job.job_id], timeout=10)
    return await BulkTransformationJob.find_one({"job_id": job.job_id})


class TestAUiUploadsId:
    async def test_a_bulk_preview_runs_over_the_route(self, async_authorized_client, setup_database, storage):
        upload = await _upload()

        response = await async_authorized_client.post(
            f"/api/v1/transformations/datasets/{upload.id}/bulk-preview",
            json={"selected_columns": ["age", "city"], "transformation_type": "fill_missing",
                  "global_parameters": {"method": "mode"}},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["success"], body["total_columns"], body["successful_previews"]) == (True, 2, 2)
        assert [p["column_name"] for p in body["column_previews"]] == ["age", "city"]

    async def test_selecting_columns_resolves_the_upload(self, setup_database, storage):
        upload = await _upload()
        pattern = ColumnSelectionPattern(pattern_type=PatternType.NAME_PATTERN, criteria={"pattern": "^a"})

        matched = await BulkTransformationService().select_columns_by_pattern(USER, str(upload.id), pattern)

        assert [c["column_name"] for c in matched] == ["age"], "read from the upload's own file (#924)"
        assert await DatasetMetadata.find_one({"dataset_id": str(upload.id), "user_id": USER}) is not None

    async def test_a_bulk_job_runs_and_moves_the_upload(self, setup_database, storage):
        upload = await _upload()
        service = BulkTransformationService()

        job = await service.apply_bulk_transformation(
            USER, str(upload.id), ["age", "city"], "fill_missing", {"method": "mode"}
        )
        done = await _finished(service, job)

        assert done.status == BulkJobStatus.COMPLETED, done.error_message
        assert done.result.successful_columns == ["age", "city"]
        assert (await UserData.get(upload.id)).s3_url == MOVED, "training reads the upload's record"
        written = storage.await_args.args[0]
        assert written["age"].isna().sum() == 0 and written["city"].isna().sum() == 0

    async def test_another_accounts_upload_is_not_found(self, setup_database, storage):
        theirs = await _upload(user_id="someone_else")
        service = BulkTransformationService()

        with pytest.raises(NotFoundError):
            await service.preview_bulk_transformation(USER, str(theirs.id), ["age"], "fill_missing", {})
        with pytest.raises(NotFoundError):
            await service.apply_bulk_transformation(USER, str(theirs.id), ["age"], "fill_missing", {})

    async def test_an_upload_the_reader_cannot_parse_is_refused_by_type(self, setup_database, storage):
        """#857: the transformation reader would read a TSV as one junk column and the
        job would then overwrite the live file with it."""
        tsv = await _upload(file_type="tsv")

        with pytest.raises(NotFoundError, match="tsv"):
            await BulkTransformationService().apply_bulk_transformation(
                USER, str(tsv.id), ["age"], "fill_missing", {}
            )
        assert await BulkTransformationJob.find({"user_id": USER}).count() == 0


class TestABulkJobsOtherEndings:
    """The paths of a job that the validation tests never reached."""

    async def test_a_column_that_fails_leaves_the_job_partially_completed(self, setup_database, storage):
        upload = await _upload()
        service = BulkTransformationService()

        job = await service.apply_bulk_transformation(
            USER, str(upload.id), ["age", "name"], "fill_missing", {"method": "mean"},
            per_column_params={"name": {"method": "no_such_method"}},
        )
        done = await _finished(service, job)

        assert done.status == BulkJobStatus.PARTIALLY_COMPLETED, done.error_message
        assert done.result.successful_columns == ["age"]
        assert [f["column_name"] for f in done.result.failed_columns] == ["name"]
        assert (await UserData.get(upload.id)).s3_url == MOVED, "the column that worked is kept"

    async def test_stop_on_error_fails_the_job_and_writes_nothing(self, setup_database, storage):
        upload = await _upload()
        service = BulkTransformationService()

        job = await service.apply_bulk_transformation(
            USER, str(upload.id), ["name", "age"], "fill_missing", {"method": "mean"},
            per_column_params={"name": {"method": "no_such_method"}}, stop_on_error=True,
        )
        done = await _finished(service, job)

        assert done.status == BulkJobStatus.FAILED and "name" in done.error_message
        storage.assert_not_awaited()
        assert (await UserData.get(upload.id)).s3_url == upload.s3_url

    async def test_a_job_cancelled_while_its_file_loads_writes_nothing(self, setup_database, storage):
        upload = await _upload()
        job = BulkTransformationJob(
            job_id="bulk_cancelled", user_id=USER, dataset_id=str(upload.id),
            selected_columns=["age"], transformation_type="fill_missing", global_parameters={"method": "mean"},
        )
        await job.insert()

        async def read_while_the_user_cancels(_url, *args, **kwargs):
            await BulkTransformationJob.find_one({"job_id": job.job_id}).update(
                {"$set": {"status": BulkJobStatus.CANCELLED.value}}
            )
            return _frame()

        with patch(f"{MODULE}.get_dataframe_from_s3", side_effect=read_while_the_user_cancels):
            await BulkTransformationService()._process_bulk_job(job)

        storage.assert_not_awaited()
        assert (await UserData.get(upload.id)).s3_url == upload.s3_url

    async def test_a_job_deleted_while_its_file_loads_writes_nothing(self, setup_database, storage):
        upload = await _upload()
        job = BulkTransformationJob(
            job_id="bulk_deleted", user_id=USER, dataset_id=str(upload.id),
            selected_columns=["age"], transformation_type="fill_missing", global_parameters={"method": "mean"},
        )
        await job.insert()

        async def read_while_the_job_is_deleted(_url, *args, **kwargs):
            await BulkTransformationJob.find_one({"job_id": job.job_id}).delete()
            return _frame()

        with patch(f"{MODULE}.get_dataframe_from_s3", side_effect=read_while_the_job_is_deleted):
            await BulkTransformationService()._process_bulk_job(job)

        storage.assert_not_awaited()

    async def test_a_job_whose_dataset_is_gone_fails_saying_so(self, setup_database, storage):
        job = BulkTransformationJob(
            job_id="bulk_orphan", user_id=USER, dataset_id="no_such_dataset",
            selected_columns=["age"], transformation_type="fill_missing",
        )
        await job.insert()

        await BulkTransformationService()._process_bulk_job(job)

        stored = await BulkTransformationJob.find_one({"job_id": "bulk_orphan"})
        assert (stored.status, stored.error_message) == (BulkJobStatus.FAILED, "Dataset not found")

    async def test_a_column_the_dataset_does_not_have_fails_the_preview(self, setup_database, storage):
        upload = await _upload()

        with pytest.raises(OperationError):
            await BulkTransformationService().preview_bulk_transformation(
                USER, str(upload.id), ["no_such_column"], "fill_missing", {}
            )


class TestACancelIsNotOverwritten:
    """#925: the job opened with a whole-document save, which wrote RUNNING over a cancel
    that landed before the task started; the job then ran and moved the dataset."""

    async def test_a_job_cancelled_before_it_starts_does_not_run(self, setup_database, storage):
        upload = await _upload()
        job = await BulkTransformationJob(
            job_id="bulk_925", user_id=USER, dataset_id=str(upload.id), selected_columns=["age"],
            transformation_type="fill_missing", global_parameters={"method": "mode"},
            status=BulkJobStatus.PENDING,
        ).insert()
        await BulkTransformationJob.get_motor_collection().update_one(
            {"job_id": "bulk_925"}, {"$set": {"status": BulkJobStatus.CANCELLED.value}}
        )

        await BulkTransformationService()._process_bulk_job(job)  # the copy the task was handed

        stored = await BulkTransformationJob.find_one({"job_id": "bulk_925"})
        assert stored.status == BulkJobStatus.CANCELLED
        storage.assert_not_awaited()
        assert (await UserData.get(upload.id)).s3_url == upload.s3_url, "the dataset did not move"

    async def test_a_cancel_after_the_last_column_stops_the_move(self, setup_database, storage):
        upload = await _upload()
        service = BulkTransformationService()
        transform = service._apply_column_transformation

        async def then_cancelled(*args, **kwargs):
            done = await transform(*args, **kwargs)
            await BulkTransformationJob.get_motor_collection().update_one(
                {"job_id": job.job_id}, {"$set": {"status": BulkJobStatus.CANCELLED.value}}
            )
            return done

        service._apply_column_transformation = then_cancelled
        job = await service.apply_bulk_transformation(
            USER, str(upload.id), ["age"], "fill_missing", {"method": "mode"}
        )
        done = await _finished(service, job)

        assert done.status == BulkJobStatus.CANCELLED
        storage.assert_not_awaited()
        assert (await UserData.get(upload.id)).s3_url == upload.s3_url, "the dataset did not move"
