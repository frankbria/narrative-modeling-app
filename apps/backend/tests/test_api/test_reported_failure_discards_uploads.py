"""#898: a route that reports failure in a 200 deletes what it uploaded and nothing owns.

The transformation apply routes write the new file to S3 first
and then move the dataset to it. When the move, or the bookkeeping before it, failed,
they answered 200 with `success: false`, and the cleanup that acts on a 4xx or 5xx
(#735) never ran: the file stayed in the bucket with no row pointing at it.

Real routes and real documents. The S3 put is replaced by one that records what it
writes exactly as the real one does; the LocalStack suite checks a real bucket.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.middleware import upload_cleanup
from app.models.user_data import UserData
from app.utils.s3 import _recorded

pytestmark = pytest.mark.asyncio

USER = "test_user_123"  # what async_authorized_client authenticates as
T = "/api/v1/transformations"


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "id": [1, 2, 2, 4, 5, 6], "age": [25, None, 30, None, 45, 45],
        "color": [" red", "blue", "blue", "green ", "red", "red"],
    })


@pytest.fixture
def written():
    """Every key the request puts; the put records it the way `upload_file_to_s3` does."""
    keys: list[str] = []

    @_recorded
    def put(file_content: bytes, s3_filename: str, content_type: str | None = None):
        keys.append(s3_filename)
        return True, f"s3://test-bucket/{s3_filename}"

    async def read(_url, *args, **kwargs):
        return _frame()

    with patch("app.services.transformation_engine.data_utils.upload_file_to_s3", put), \
         patch("app.services.transformation_engine.data_utils.get_dataframe_from_s3", side_effect=read), \
         patch("app.services.bulk_transformation_service.get_dataframe_from_s3", side_effect=read), \
         patch("app.services.versioning_service.versioning_service.s3_client"):
        yield keys


@pytest.fixture
def deleted(monkeypatch) -> AsyncMock:
    delete = AsyncMock(return_value=True)
    monkeypatch.setattr(upload_cleanup.s3_service, "delete_file", delete)
    return delete


async def _upload() -> UserData:
    url = f"s3://test-bucket/datasets/{USER}/people.csv"
    return await UserData(
        user_id=USER, filename="people.csv", original_filename="people.csv", s3_url=url,
        num_rows=6, num_columns=3, data_schema=[], file_type="csv", is_processed=True,
        columns=["id", "age", "color"],
    ).insert()


def _fails(what: str):
    return patch(what, new_callable=AsyncMock, side_effect=RuntimeError("the database went away"))


# The move is the last write before the apply succeeds (#1060).
STEP = "app.services.transformation_service.record_new_file"


class TestTransformationApply:
    async def test_an_apply_that_fails_after_the_put_deletes_the_file(
        self, async_authorized_client, setup_database, written, deleted
    ):
        upload = await _upload()

        with _fails(STEP):
            response = await async_authorized_client.post(f"{T}/apply", json={
                "dataset_id": str(upload.id), "transformation_type": "remove_duplicates", "parameters": {}})

        assert response.status_code == 200 and response.json()["success"] is False, response.text
        assert len(written) == 1 and written[0].startswith(f"transformed/{USER}/")
        deleted.assert_awaited_once_with(written[0])
        assert (await UserData.get(upload.id)).s3_url == upload.s3_url

    async def test_a_pipeline_that_fails_after_the_put_deletes_the_file(
        self, async_authorized_client, setup_database, written, deleted
    ):
        upload = await _upload()

        with _fails(STEP):
            response = await async_authorized_client.post(f"{T}/pipeline/apply", json={
                "dataset_id": str(upload.id),
                "transformations": [{"type": "trim_whitespace", "parameters": {}}, {"type": "remove_duplicates", "parameters": {}}]})

        assert response.status_code == 200 and response.json()["success"] is False, response.text
        deleted.assert_awaited_once_with(written[0])

    async def test_auto_clean_runs_through_the_same_route(
        self, async_authorized_client, setup_database, written, deleted
    ):
        upload = await _upload()

        with _fails(STEP):
            response = await async_authorized_client.post(f"{T}/auto-clean", json={"dataset_id": str(upload.id)})

        assert response.status_code == 200 and response.json()["success"] is False, response.text
        deleted.assert_awaited_once_with(written[0])

    async def test_a_successful_apply_keeps_its_file(self, async_authorized_client, setup_database, written, deleted):
        upload = await _upload()

        response = await async_authorized_client.post(f"{T}/apply", json={
            "dataset_id": str(upload.id), "transformation_type": "remove_duplicates", "parameters": {}})

        assert response.json()["success"] is True, response.text
        deleted.assert_not_awaited()
        assert (await UserData.get(upload.id)).s3_url.endswith(written[0])

    async def test_a_failure_after_the_dataset_moved_keeps_the_file_it_now_points_at(
        self, async_authorized_client, setup_database, written, deleted
    ):
        """The move landed and something after it failed: the row names the object."""
        upload = await _upload()

        from app.services.dataset_link import record_new_file

        async def move_then_fail(*args, **kwargs):
            await record_new_file(*args, **kwargs)
            raise RuntimeError("something after the move")

        with patch("app.services.transformation_service.record_new_file", move_then_fail):
            response = await async_authorized_client.post(f"{T}/apply", json={
                "dataset_id": str(upload.id), "transformation_type": "remove_duplicates", "parameters": {}})

        assert response.json()["success"] is False, response.text
        deleted.assert_not_awaited()
        assert (await UserData.get(upload.id)).s3_url.endswith(written[0])


class TestBulkJob:
    async def test_a_job_that_fails_after_the_put_deletes_the_file(self, setup_database, written, deleted):
        from app.models.bulk_transformation import BulkJobStatus, BulkTransformationJob
        from app.services.bulk_transformation_service import BulkTransformationService

        upload = await _upload()
        service = BulkTransformationService()

        with _fails(STEP):
            job = await service.apply_bulk_transformation(USER, str(upload.id), ["age"], "fill_missing", {"method": "mean"})
            await asyncio.wait_for(service._active_tasks[job.job_id], timeout=10)

        stored = await BulkTransformationJob.find_one({"job_id": job.job_id})
        assert stored.status == BulkJobStatus.FAILED and stored.output_file_path is None
        assert len(written) == 1 and written[0].startswith(f"transformed/{USER}/")
        deleted.assert_awaited_once_with(written[0])

    async def test_the_file_is_gone_by_the_time_the_job_says_it_failed(self, setup_database, written, monkeypatch):
        """A client polls the job's status; "failed" with the file still there is a
        window in which it looks like nothing cleaned up."""
        from app.models.bulk_transformation import BulkJobStatus, BulkTransformationJob
        from app.services.bulk_transformation_service import BulkTransformationService

        upload = await _upload()
        service = BulkTransformationService()
        status_when_deleted: list[BulkJobStatus] = []

        async def delete(_key: str) -> bool:
            job = await BulkTransformationJob.find_one({"user_id": USER})
            status_when_deleted.append(job.status)
            return True

        monkeypatch.setattr(upload_cleanup.s3_service, "delete_file", delete)
        with _fails(STEP):
            job = await service.apply_bulk_transformation(USER, str(upload.id), ["age"], "fill_missing", {"method": "mean"})
            await asyncio.wait_for(service._active_tasks[job.job_id], timeout=10)

        assert status_when_deleted == [BulkJobStatus.RUNNING]

    async def test_a_job_that_finishes_keeps_its_file(self, setup_database, written, deleted):
        from app.models.bulk_transformation import BulkJobStatus, BulkTransformationJob
        from app.services.bulk_transformation_service import BulkTransformationService

        upload = await _upload()
        service = BulkTransformationService()

        job = await service.apply_bulk_transformation(USER, str(upload.id), ["age"], "fill_missing", {"method": "mean"})
        await asyncio.wait_for(service._active_tasks[job.job_id], timeout=10)

        stored = await BulkTransformationJob.find_one({"job_id": job.job_id})
        assert stored.status == BulkJobStatus.COMPLETED, stored.error_message
        deleted.assert_not_awaited()
