"""#674: deploying or deactivating a model writes its own fields, not the whole document.

Both handlers read the model, changed a few fields in memory and called `save()`, which
writes every field back from that copy. Anything another writer set in between was
reverted: `last_used_at` is stamped by every prediction with a targeted `$set` (#725)
precisely so that it cannot clobber a deploy, and the deploy clobbered it instead.
"""
from datetime import UTC, datetime

import pytest

from app.models.ml_model import MLModel
from app.utils.datetime import as_utc

USER = "test_user_123"
STAMP = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


async def _model(model_id: str) -> None:
    await MLModel(
        user_id=USER, dataset_id="ds-1", model_id=model_id, name="Churn",
        problem_type="binary_classification", algorithm="Random Forest", target_column="y",
        feature_names=["f1"], cv_score=0.8, test_score=0.8, training_time=1.0, model_size=1,
        n_samples_train=10, n_features=1, model_path="s3://bucket/m.pkl",
    ).insert()


@pytest.fixture
def a_prediction_lands_after_the_read(monkeypatch):
    """The handler's first read returns, and before it writes, another request stamps
    `last_used_at` the way serving does."""
    real = MLModel.find_one
    calls = {"n": 0}

    def racing(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] > 1:
            return real(*args, **kwargs)

        async def read_then_be_overtaken():
            model = await real(*args, **kwargs)
            await MLModel.get_motor_collection().update_one(
                {"model_id": model.model_id}, {"$set": {"last_used_at": STAMP}}
            )
            return model

        return read_then_be_overtaken()

    monkeypatch.setattr(MLModel, "find_one", staticmethod(racing))


@pytest.mark.asyncio
async def test_a_deploy_keeps_what_was_written_while_it_ran(
    setup_database, async_authorized_client, a_prediction_lands_after_the_read
):
    await _model("m-deploy")

    response = await async_authorized_client.put("/api/v1/ml/m-deploy/deploy", json={})

    assert response.status_code == 200, response.text
    stored = await MLModel.find_one(MLModel.model_id == "m-deploy")
    assert stored.is_deployed is True
    assert stored.deployment_endpoint == response.json()["deployment_endpoint"]
    assert stored.deployed_at is not None and stored.updated_at is not None
    assert as_utc(stored.last_used_at) == STAMP


@pytest.mark.asyncio
async def test_a_deactivation_keeps_what_was_written_while_it_ran(
    setup_database, async_authorized_client, a_prediction_lands_after_the_read
):
    await _model("m-off")

    response = await async_authorized_client.put("/api/v1/ml/m-off/deactivate")

    assert response.status_code == 200, response.text
    stored = await MLModel.find_one(MLModel.model_id == "m-off")
    assert stored.is_active is False
    assert as_utc(stored.last_used_at) == STAMP


@pytest.mark.asyncio
async def test_a_model_that_is_not_the_callers_is_not_found(setup_database, async_authorized_client):
    assert (await async_authorized_client.put("/api/v1/ml/nope/deploy", json={})).status_code == 404
    assert (await async_authorized_client.put("/api/v1/ml/nope/deactivate")).status_code == 404
