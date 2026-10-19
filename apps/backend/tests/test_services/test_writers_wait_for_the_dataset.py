"""#1022: every writer that moves a dataset holds its lease, and one that cannot get it
says so in its own failure shape and writes nothing.

Real documents and the real lease; the wait is shortened so a held lease is refused
quickly. The race the lease prevents is in
tests/test_integration/test_undo_during_an_apply_localstack.py.
"""

import ast
from pathlib import Path

import pytest

from app.services import dataset_lease
from app.services.dataset_link import DATASET_BUSY, holding_the_dataset

USER = "test_user_123"  # the identity async_authorized_client signs in as
APP = Path(__file__).resolve().parents[2] / "app"


@pytest.fixture
def held(monkeypatch):
    """The lease of a dataset id, held by someone else for the test's duration."""
    monkeypatch.setattr(dataset_lease, "WAIT_SECONDS", 0.2)
    return lambda dataset_id: holding_the_dataset(dataset_id, USER)


@pytest.mark.asyncio
async def test_an_undo_is_refused_while_another_writer_holds_the_dataset(
    setup_database, async_authorized_client, held
):
    async with held("ds_1022"):
        response = await async_authorized_client.post("/api/v1/transformations/datasets/ds_1022/history/undo")

    assert (response.status_code, response.json()["detail"]) == (400, DATASET_BUSY)


def test_a_handler_the_lease_cannot_be_named_for_is_refused_when_decorated():
    from app.services.dataset_link import holds_the_dataset

    with pytest.raises(TypeError, match="current_user_id"):
        holds_the_dataset(lambda a: "d", lambda a: None)(lambda request, user_id: None)


@pytest.mark.asyncio
async def test_a_bulk_job_fails_with_that_reason_while_another_writer_holds_the_dataset(setup_database, held):
    from app.models.bulk_transformation import BulkJobStatus, BulkTransformationJob
    from app.services.bulk_transformation_service import BulkTransformationService

    job = BulkTransformationJob(
        job_id="bulk_1022", user_id=USER, dataset_id="ds_1022", selected_columns=["a"],
        transformation_type="fill_missing", global_parameters={},
    )
    await job.insert()
    async with held("ds_1022"):
        await BulkTransformationService()._process_bulk_job(job)

    stored = await BulkTransformationJob.find_one(BulkTransformationJob.job_id == "bulk_1022")
    assert (stored.status, stored.error_message) == (BulkJobStatus.FAILED, DATASET_BUSY)


#: Each module that moves a dataset through `record_new_file`, or through
#: `TransformationService.record_edit` (an edit recorded as a history step, #923), and the
#: module whose code takes the dataset's lease around that move. A new call site fails
#: here until listed.
LEASE_TAKEN_IN = {
    "services/transformation_service.py": "services/transformation_service.py",
    "services/history_service.py": "services/history_service.py",
    "services/bulk_transformation_service.py": "services/bulk_transformation_service.py",
}


def _calls(path: Path, name: str) -> bool:
    return any(
        isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == name
        for node in ast.walk(ast.parse(path.read_text()))
    )


def test_every_writer_that_moves_a_dataset_takes_its_lease():
    movers = {
        str(path.relative_to(APP))
        for path in APP.rglob("*.py")
        if path.name != "dataset_link.py" and (_calls(path, "record_new_file") or _calls(path, "record_edit"))
    }

    assert movers == set(LEASE_TAKEN_IN), "a new record_new_file call site: list it, with where it takes the lease"
    for taker in set(LEASE_TAKEN_IN.values()):
        path = APP / taker
        assert _calls(path, "holding_the_dataset") or _calls(path, "holds_the_dataset"), taker
