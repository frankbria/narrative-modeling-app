"""HTTP route tests for the batch-prediction surface (#516).

Nine endpoints — create, list, get, progress, cancel, retry, download, delete,
stats — handle a paid, quota-metered flow over customer data and downloadable
results, and had no route coverage. These go through ``async_authorized_client``
(the full app, authed as ``TEST_USER``) against **real** ``BatchJob`` documents,
assert **exact** status codes (never ``x in [200, 404, 422]``, which passes
vacuously per CLAUDE.md), and pin per-endpoint tenant isolation — download and
delete most sharply, since download returns customer data.
"""

import io
from unittest.mock import AsyncMock, patch

import pytest

from app.billing import metering
from app.models.batch_job import BatchJob, JobProgress, JobStatus, JobType

pytestmark = pytest.mark.asyncio

TEST_USER = "test_user_123"  # what async_authorized_client authenticates as
OTHER_USER = "other_tenant_999"  # tenant B — never the caller

_BATCH = "/api/v1/batch"


def _csv(rows: int = 3) -> dict:
    body = "age\n" + "\n".join(str(i) for i in range(rows)) + "\n"
    return {"file": ("in.csv", io.BytesIO(body.encode()), "text/csv")}


async def _job(
    job_id: str,
    user_id: str = TEST_USER,
    status: JobStatus = JobStatus.COMPLETED,
    total_records: int = 5,
    output_format: str = "csv",
    **kw,
) -> BatchJob:
    return await BatchJob(
        job_id=job_id,
        job_type=JobType.BATCH_PREDICTION,
        user_id=user_id,
        config={"model_id": "m1", "output_format": output_format},
        input_path=f"batch-jobs/{user_id}/m1/ts/in.csv",
        status=status,
        progress=JobProgress(total_records=total_records, processed_records=total_records),
        **kw,
    ).insert()


class TestCreate:
    async def test_non_csv_is_400(self, async_authorized_client, setup_database):
        resp = await async_authorized_client.post(
            f"{_BATCH}/jobs",
            files={"file": ("x.txt", io.BytesIO(b"nope"), "text/plain")},
            data={"model_id": "m1"},
        )
        assert resp.status_code == 400

    async def test_at_the_predictions_limit_is_402(
        self, async_authorized_client, setup_database
    ):
        from app.billing.plans import PLAN_LIMITS, PlanTier
        from app.models.usage import UsageRecord

        await UsageRecord(
            user_id=TEST_USER, period_key=metering.period_key_for(),
            metric="predictions", units=PLAN_LIMITS[PlanTier.FREE].predictions,
        ).insert()
        resp = await async_authorized_client.post(
            f"{_BATCH}/jobs", files=_csv(3), data={"model_id": "m1"}
        )
        assert resp.status_code == 402
        assert resp.json()["detail"]["metric"] == "predictions"

    async def test_successful_create_reserves_per_record(
        self, async_authorized_client, setup_database
    ):
        before = await metering.usage_for(TEST_USER, "predictions")
        created = BatchJob(
            job_id="created_1", job_type=JobType.BATCH_PREDICTION, user_id=TEST_USER,
            config={"model_id": "m1", "output_format": "csv"},
            input_path="batch-jobs/u/m1/ts/in.csv", status=JobStatus.PENDING,
            progress=JobProgress(total_records=3),
        )
        with patch(
            "app.api.routes.batch_prediction.batch_service.create_batch_prediction_job",
            new_callable=AsyncMock, return_value=created,
        ):
            resp = await async_authorized_client.post(
                f"{_BATCH}/jobs", files=_csv(3), data={"model_id": "m1"}
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["job_id"] == "created_1"
        # 3 rows: 1 reserved by the admission dependency + 2 remainder in the route.
        assert await metering.usage_for(TEST_USER, "predictions") == before + 3


class TestListAndStats:
    async def test_list_returns_only_the_callers_jobs(
        self, async_authorized_client, setup_database
    ):
        await _job("a1", TEST_USER)
        await _job("a2", TEST_USER)
        await _job("b1", OTHER_USER)
        resp = await async_authorized_client.get(f"{_BATCH}/jobs")
        assert resp.status_code == 200
        ids = {j["job_id"] for j in resp.json()}
        assert ids == {"a1", "a2"}  # B's job is not listed

    async def test_stats_count_only_the_callers_jobs(
        self, async_authorized_client, setup_database
    ):
        await _job("a1", TEST_USER, status=JobStatus.COMPLETED)
        await _job("a2", TEST_USER, status=JobStatus.FAILED)
        await _job("b1", OTHER_USER, status=JobStatus.COMPLETED)
        resp = await async_authorized_client.get(f"{_BATCH}/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_jobs"] == 2  # not B's


class TestGetAndProgress:
    async def test_get_own_job_is_200(self, async_authorized_client, setup_database):
        await _job("own", TEST_USER)
        resp = await async_authorized_client.get(f"{_BATCH}/jobs/own")
        assert resp.status_code == 200
        assert resp.json()["job_id"] == "own"

    async def test_get_foreign_job_is_404(self, async_authorized_client, setup_database):
        await _job("foreign", OTHER_USER)
        resp = await async_authorized_client.get(f"{_BATCH}/jobs/foreign")
        assert resp.status_code == 404

    async def test_get_unknown_job_is_404(self, async_authorized_client, setup_database):
        assert (await async_authorized_client.get(f"{_BATCH}/jobs/nope")).status_code == 404

    async def test_progress_own_is_200_foreign_is_404(
        self, async_authorized_client, setup_database
    ):
        await _job("own", TEST_USER)
        await _job("foreign", OTHER_USER)
        assert (await async_authorized_client.get(f"{_BATCH}/jobs/own/progress")).status_code == 200
        assert (await async_authorized_client.get(f"{_BATCH}/jobs/foreign/progress")).status_code == 404


class TestCancel:
    async def test_cancel_own_pending_job_is_200(
        self, async_authorized_client, setup_database
    ):
        await _job("cancelme", TEST_USER, status=JobStatus.PENDING)
        resp = await async_authorized_client.post(f"{_BATCH}/jobs/cancelme/cancel")
        assert resp.status_code == 200
        refetched = await BatchJob.find_one(BatchJob.job_id == "cancelme")
        assert refetched.status == JobStatus.CANCELLED

    async def test_cannot_cancel_a_foreign_job(
        self, async_authorized_client, setup_database
    ):
        await _job("bjob", OTHER_USER, status=JobStatus.PENDING)
        resp = await async_authorized_client.post(f"{_BATCH}/jobs/bjob/cancel")
        assert resp.status_code == 400  # not claimable by A
        # B's job is untouched.
        assert (await BatchJob.find_one(BatchJob.job_id == "bjob")).status == JobStatus.PENDING

    async def test_cannot_cancel_a_completed_job(
        self, async_authorized_client, setup_database
    ):
        await _job("done", TEST_USER, status=JobStatus.COMPLETED)
        assert (await async_authorized_client.post(f"{_BATCH}/jobs/done/cancel")).status_code == 400


class TestRetry:
    async def test_retry_own_failed_job_is_200(
        self, async_authorized_client, setup_database
    ):
        await _job("f1", TEST_USER, status=JobStatus.FAILED, total_records=1)
        with patch(
            "app.api.routes.batch_prediction.batch_service.retry_job",
            new_callable=AsyncMock, return_value=True,
        ):
            resp = await async_authorized_client.post(f"{_BATCH}/jobs/f1/retry")
        assert resp.status_code == 200

    async def test_retry_foreign_failed_job_is_404(
        self, async_authorized_client, setup_database
    ):
        await _job("bf", OTHER_USER, status=JobStatus.FAILED, total_records=1)
        resp = await async_authorized_client.post(f"{_BATCH}/jobs/bf/retry")
        assert resp.status_code == 404

    async def test_retry_a_non_failed_job_is_409(
        self, async_authorized_client, setup_database
    ):
        await _job("run", TEST_USER, status=JobStatus.COMPLETED, total_records=1)
        resp = await async_authorized_client.post(f"{_BATCH}/jobs/run/retry")
        assert resp.status_code == 409
        assert "failed job can be retried" in resp.json()["detail"]

    async def test_retry_a_budget_exhausted_job_is_409(
        self, async_authorized_client, setup_database
    ):
        """A distinct 409 from the not-FAILED one: a FAILED job that has already
        used its retry budget (#460 bounds retries at max_retries)."""
        await _job(
            "spent", TEST_USER, status=JobStatus.FAILED, total_records=1,
            retry_count=3, max_retries=3,
        )
        resp = await async_authorized_client.post(f"{_BATCH}/jobs/spent/retry")
        assert resp.status_code == 409
        assert "Retry limit reached" in resp.json()["detail"]


class TestDownload:
    async def test_download_own_completed_results_is_200(
        self, async_authorized_client, setup_database
    ):
        await _job("dl", TEST_USER, status=JobStatus.COMPLETED)
        with patch(
            "app.api.routes.batch_prediction.batch_service.download_results",
            new_callable=AsyncMock, return_value=b"prediction\n1\n",
        ):
            resp = await async_authorized_client.get(f"{_BATCH}/jobs/dl/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
        assert resp.content == b"prediction\n1\n"

    async def test_cannot_download_a_foreign_jobs_results(
        self, async_authorized_client, setup_database
    ):
        """The sharp one: download returns customer data. A must get 404 for B's
        job, and B's results must never be streamed."""
        await _job("bdl", OTHER_USER, status=JobStatus.COMPLETED)
        # download_results must never be reached; if it were, this would leak.
        with patch(
            "app.api.routes.batch_prediction.batch_service.download_results",
            new_callable=AsyncMock, return_value=b"SECRET-B-DATA\n",
        ) as dl:
            resp = await async_authorized_client.get(f"{_BATCH}/jobs/bdl/download")
        assert resp.status_code == 404
        assert b"SECRET-B-DATA" not in resp.content
        dl.assert_not_awaited()

    async def test_download_an_incomplete_job_is_400(
        self, async_authorized_client, setup_database
    ):
        await _job("running", TEST_USER, status=JobStatus.RUNNING)
        assert (await async_authorized_client.get(f"{_BATCH}/jobs/running/download")).status_code == 400


class TestDelete:
    async def test_delete_own_completed_job_is_200(
        self, async_authorized_client, setup_database
    ):
        await _job("del", TEST_USER, status=JobStatus.COMPLETED)
        resp = await async_authorized_client.delete(f"{_BATCH}/jobs/del")
        assert resp.status_code == 200
        assert await BatchJob.find_one(BatchJob.job_id == "del") is None

    async def test_cannot_delete_a_foreign_job(
        self, async_authorized_client, setup_database
    ):
        await _job("bdel", OTHER_USER, status=JobStatus.COMPLETED)
        resp = await async_authorized_client.delete(f"{_BATCH}/jobs/bdel")
        assert resp.status_code == 404
        assert await BatchJob.find_one(BatchJob.job_id == "bdel") is not None  # still there

    async def test_cannot_delete_an_active_job(
        self, async_authorized_client, setup_database
    ):
        await _job("active", TEST_USER, status=JobStatus.RUNNING)
        assert (await async_authorized_client.delete(f"{_BATCH}/jobs/active")).status_code == 400
