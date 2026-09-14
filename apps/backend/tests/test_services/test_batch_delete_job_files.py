"""#661: deleting a batch job must also delete its S3 input/output objects.

`delete_job_files` is the cleanup the old `DELETE /jobs/{job_id}` TODO skipped. These
are hermetic (no S3/DB): the S3Service is a stub recording delete_file calls.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.batch_prediction import BatchPredictionService

pytestmark = pytest.mark.asyncio


def _job(input_path, output_path):
    return SimpleNamespace(
        job_id="job-661", input_path=input_path, output_path=output_path
    )


def _live_service():
    svc = BatchPredictionService()
    svc.s3_service = SimpleNamespace(
        is_mock_mode=False, s3_client=object(), delete_file=AsyncMock(return_value=True)
    )
    return svc


async def test_deletes_both_input_and_output():
    svc = _live_service()
    await svc.delete_job_files(
        _job("batch-jobs/u/m/j/input.csv", "batch-jobs/u/m/j/results.csv")
    )
    deleted = {c.args[0] for c in svc.s3_service.delete_file.call_args_list}
    assert deleted == {"batch-jobs/u/m/j/input.csv", "batch-jobs/u/m/j/results.csv"}


async def test_skips_missing_paths():
    svc = _live_service()
    await svc.delete_job_files(_job("batch-jobs/u/m/j/input.csv", None))
    deleted = [c.args[0] for c in svc.s3_service.delete_file.call_args_list]
    assert deleted == ["batch-jobs/u/m/j/input.csv"]


async def test_mock_mode_deletes_nothing():
    svc = BatchPredictionService()
    svc.s3_service = SimpleNamespace(
        is_mock_mode=True, s3_client=None, delete_file=AsyncMock()
    )
    await svc.delete_job_files(_job("batch-jobs/u/m/j/input.csv", "x"))
    svc.s3_service.delete_file.assert_not_called()


async def test_cleanup_failure_does_not_raise():
    svc = _live_service()
    svc.s3_service.delete_file = AsyncMock(side_effect=RuntimeError("s3 down"))
    # Must not propagate — cleanup can't block the job's deletion (#661).
    await svc.delete_job_files(_job("batch-jobs/u/m/j/input.csv", "batch-jobs/u/m/j/out.csv"))
