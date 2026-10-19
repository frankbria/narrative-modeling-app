"""#1102: GET /batch/stats counts the user's 1000 most recent jobs; the docs say so."""
import pytest

from app.models.batch_job import BatchJob, JobProgress, JobStatus, JobType

USER = "test_user_123"


async def _job(job_id: str, status: JobStatus, processed: int = 0, ok: int = 0, user: str = USER) -> None:
    await BatchJob(
        job_id=job_id, job_type=JobType.BATCH_PREDICTION, user_id=user, config={},
        status=status, progress=JobProgress(total_records=processed, processed_records=processed, success_count=ok),
    ).insert()


@pytest.mark.asyncio
async def test_stats_count_only_the_callers_jobs_by_status(setup_database, async_authorized_client):
    await _job("j1", JobStatus.COMPLETED, processed=10, ok=10)
    await _job("j2", JobStatus.COMPLETED, processed=10, ok=5)
    await _job("j3", JobStatus.FAILED)
    await _job("j4", JobStatus.RUNNING)
    await _job("j5", JobStatus.PENDING)
    await _job("other", JobStatus.COMPLETED, processed=99, ok=99, user="someone-else")

    response = await async_authorized_client.get("/api/v1/batch/stats")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "total_jobs": 5, "completed_jobs": 2, "failed_jobs": 1, "running_jobs": 1, "pending_jobs": 1,
        "total_predictions": 20, "average_success_rate": 75.0, "completion_rate": 40.0,
    }


@pytest.mark.asyncio
async def test_stats_for_a_user_with_no_jobs_are_zero(setup_database, async_authorized_client):
    response = await async_authorized_client.get("/api/v1/batch/stats")

    assert response.status_code == 200, response.text
    assert response.json()["total_jobs"] == 0
    assert response.json()["average_success_rate"] == 0 and response.json()["completion_rate"] == 0
