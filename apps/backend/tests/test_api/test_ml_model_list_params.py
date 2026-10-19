"""`GET /ml/` takes `limit` and `deployed`, so the dashboard reads rows, not history (#1085)."""

from datetime import UTC, datetime

import pytest

from app.models.ml_model import MLModel

USER = "test_user_123"


async def _model(day: int, **fields) -> None:
    await MLModel(
        user_id=USER, dataset_id="ds-1", model_id=f"model-{day}", name=f"Model {day}",
        problem_type="binary_classification", algorithm="Random Forest",
        target_column="churn", feature_names=["tenure"], cv_score=0.8, test_score=0.9,
        training_time=1.0, model_size=1, n_samples_train=10, n_features=1,
        model_path=f"models/{USER}/model-{day}.pkl",
        created_at=datetime(2026, 10, day, tzinfo=UTC), **fields,
    ).insert()


async def _ids(client, query: str = "") -> list[str]:
    response = await client.get(f"/api/v1/ml/{query}")
    assert response.status_code == 200
    return [m["model_id"] for m in response.json()]


@pytest.fixture
async def seven_models(setup_database):
    for day in range(1, 8):
        await _model(day, is_deployed=day == 2)


@pytest.mark.asyncio
async def test_limit_returns_the_newest_rows(async_authorized_client, seven_models):
    assert await _ids(async_authorized_client, "?limit=3") == ["model-7", "model-6", "model-5"]


@pytest.mark.asyncio
async def test_deployed_returns_only_deployed_models_however_old(async_authorized_client, seven_models):
    assert await _ids(async_authorized_client, "?deployed=true&limit=1") == ["model-2"]


@pytest.mark.asyncio
async def test_deployed_false_returns_only_undeployed(async_authorized_client, seven_models):
    assert "model-2" not in await _ids(async_authorized_client, "?deployed=false")


@pytest.mark.asyncio
async def test_no_params_returns_everything_newest_first(async_authorized_client, seven_models):
    assert await _ids(async_authorized_client) == [f"model-{d}" for d in range(7, 0, -1)]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, -1, 101])
async def test_limit_out_of_range_is_422(async_authorized_client, setup_database, limit):
    response = await async_authorized_client.get(f"/api/v1/ml/?limit={limit}")
    assert response.status_code == 422
