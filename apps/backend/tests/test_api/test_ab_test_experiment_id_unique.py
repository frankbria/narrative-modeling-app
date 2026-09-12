"""`ABTest.experiment_id` is unique and the write side is owner-scoped (#565).

Ids are generated server-side, so the API cannot produce a duplicate; the index
makes the guarantee the database's rather than a helper's, and the service no
longer trusts its caller to have checked ownership.
"""

import pytest
from pymongo.errors import DuplicateKeyError

from app.models.ab_test import ABTest, ExperimentStatus, Variant
from app.services.ab_testing import ABTestingService

pytestmark = pytest.mark.asyncio

OWNER = "owner_565"
INTRUDER = "intruder_565"


def _experiment(user_id: str, experiment_id: str = "exp_565") -> ABTest:
    return ABTest(
        user_id=user_id,
        experiment_id=experiment_id,
        name="e",
        primary_metric="accuracy",
        status=ExperimentStatus.RUNNING,
        variants=[Variant(variant_id="v1", name="control", model_id="m1", traffic_percentage=100.0)],
    )


@pytest.fixture
async def owned(setup_database) -> ABTest:
    doc = await _experiment(OWNER).insert()
    yield doc
    await ABTest.find(ABTest.experiment_id == "exp_565").delete()


async def test_a_second_document_with_the_same_experiment_id_is_rejected(owned):
    with pytest.raises(DuplicateKeyError):
        await _experiment(INTRUDER).insert()  # another tenant, same id
    assert await ABTest.find(ABTest.experiment_id == "exp_565").count() == 1


async def test_the_unique_index_is_declared_on_the_collection(owned):
    info = await ABTest.get_motor_collection().index_information()
    unique = [k for k, v in info.items() if v.get("key") == [("experiment_id", 1)] and v.get("unique")]
    assert unique, info


async def test_service_write_is_scoped_to_the_owner(owned):
    await ABTestingService.track_prediction(
        experiment_id="exp_565", variant_id="v1", latency_ms=10.0, user_id=INTRUDER
    )
    assert (await ABTest.find_one(ABTest.experiment_id == "exp_565")).variants[0].total_predictions == 0

    await ABTestingService.track_prediction(
        experiment_id="exp_565", variant_id="v1", latency_ms=10.0, user_id=OWNER
    )
    assert (await ABTest.find_one(ABTest.experiment_id == "exp_565")).variants[0].total_predictions == 1
