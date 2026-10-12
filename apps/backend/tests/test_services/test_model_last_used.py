"""#725: a model's `last_used_at` follows its predictions, not its last load from S3.

It was written only on a cache miss, so a model that stayed in the process-local cache
showed the time of its first load after the last restart, and the monitor page showed
that as the time of its last prediction.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.models.ml_model import MLModel
from app.services.model_storage import stamp_last_used
from app.utils.datetime import as_utc

pytestmark = pytest.mark.asyncio


async def _model(last_used_at: datetime | None) -> MLModel:
    return await MLModel(
        user_id="u_725", dataset_id="ds", model_id="model_725", name="m", problem_type="regression",
        algorithm="Random Forest", target_column="y", feature_names=["a"], cv_score=0.8, test_score=0.8,
        training_time=1.0, model_size=10, n_samples_train=3, n_features=1,
        model_path="s3://bucket/models/u_725/model_725/model.pkl", last_used_at=last_used_at,
    ).insert()


async def _stored() -> MLModel:
    return await MLModel.find_one(MLModel.model_id == "model_725")


def _recent(moment: datetime | None) -> bool:
    return moment is not None and datetime.now(UTC) - as_utc(moment) < timedelta(seconds=30)


@pytest.mark.parametrize("before", [None, datetime(2026, 1, 1, tzinfo=UTC)])
async def test_a_prediction_stamps_a_model_never_or_long_ago_used(setup_database, before):
    model = await _model(before)

    await stamp_last_used(model)

    assert _recent((await _stored()).last_used_at)


async def test_a_model_stamped_moments_ago_is_not_written_again(setup_database):
    """One write per model every few minutes, not one per prediction."""
    a_minute_ago = datetime.now(UTC) - timedelta(minutes=1)
    model = await _model(a_minute_ago)

    await stamp_last_used(model)

    assert abs(as_utc((await _stored()).last_used_at) - a_minute_ago) < timedelta(seconds=1)


async def test_the_stamp_touches_nothing_else(setup_database):
    """A targeted $set: the route's copy of the document is not written back over a
    change made since it was read (#520's clobber class)."""
    model = await _model(None)
    await MLModel.find_one(MLModel.model_id == "model_725").update({"$set": {"is_deployed": True, "name": "renamed"}})

    await stamp_last_used(model)

    after = await _stored()
    assert (after.is_deployed, after.name) == (True, "renamed") and _recent(after.last_used_at)


async def test_a_failed_stamp_does_not_fail_the_prediction(setup_database):
    model = await _model(None)

    with patch.object(MLModel, "find_one", side_effect=RuntimeError("mongo is away")):
        await stamp_last_used(model)

    assert (await _stored()).last_used_at is None
