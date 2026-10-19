"""#1102: GET /models?status= validates against the lowercase ModelStatus values.

The `Query` described uppercase values and took a bare string, so `?status=TRAINED`
reached `ModelStatus("TRAINED")` inside the handler's catch-all and answered 500.
"""
import pytest

from app.models.model import (
    DeploymentConfig,
    FeatureConfig,
    ModelConfig,
    ModelStatus,
    PerformanceMetrics,
    ProblemType,
    TrainingConfig,
)

USER = "test_user_123"


async def _model(model_id: str, dataset_id: str, status: ModelStatus) -> None:
    """Insert a ModelConfig in the given state, as a training run would have left it."""
    deployed = status == ModelStatus.DEPLOYED
    await ModelConfig(
        user_id=USER, dataset_id=dataset_id, model_id=model_id, name=model_id,
        problem_type=ProblemType.CLASSIFICATION, algorithm="XGBoost", status=status,
        feature_config=FeatureConfig(feature_names=["f1"], target_column="y"),
        training_config=TrainingConfig(training_time=1.0, n_samples_train=7, n_samples_test=3),
        performance_metrics=PerformanceMetrics(cv_score=0.8, test_score=0.8),
        deployment_config=DeploymentConfig(is_deployed=deployed, deployment_endpoint="/predict" if deployed else None),
        model_path=f"models/{model_id}.pkl", model_size=1,
    ).insert()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["TRAINED", "Trained", "nonsense"])
async def test_a_status_that_is_not_a_lowercase_value_is_a_422(
    setup_database, async_authorized_client, value
):
    response = await async_authorized_client.get("/api/v1/models", params={"status": value})

    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"] == ["query", "status"]


@pytest.mark.asyncio
async def test_each_filter_shape_returns_only_the_requested_status(setup_database, async_authorized_client):
    await _model("m-training", "ds-1", ModelStatus.TRAINING)
    await _model("m-trained", "ds-1", ModelStatus.TRAINED)
    await _model("m-deployed", "ds-1", ModelStatus.DEPLOYED)

    async def ids(**params):
        response = await async_authorized_client.get("/api/v1/models", params=params)
        assert response.status_code == 200, response.text
        return {m["model_id"] for m in response.json()["models"]}, response.json()["total"]

    assert await ids(status="trained") == ({"m-trained"}, 1)
    assert await ids(status="deployed") == ({"m-deployed"}, 1)
    assert await ids(status="trained", dataset_id="ds-1") == ({"m-trained"}, 1)
    assert await ids(status="failed", dataset_id="ds-1") == (set(), 0)
    assert (await ids())[1] == 3


@pytest.mark.asyncio
async def test_a_put_changes_only_the_fields_it_sets_and_answers_what_a_get_does(
    setup_database, async_authorized_client
):
    await _model("m-edit", "ds-1", ModelStatus.TRAINED)
    before = (await async_authorized_client.get("/api/v1/models/m-edit")).json()

    response = await async_authorized_client.put(
        "/api/v1/models/m-edit", json={"name": "Renamed", "tags": ["a"]}
    )

    assert response.status_code == 200, response.text
    after = response.json()
    assert after["name"] == "Renamed" and after["tags"] == ["a"]
    assert after["description"] == before["description"] and after["notes"] == before["notes"]
    assert after["deployment_config"] == before["deployment_config"]
    assert (await async_authorized_client.get("/api/v1/models/m-edit")).json()["name"] == "Renamed"


@pytest.mark.asyncio
async def test_a_put_to_a_model_that_is_not_there_is_a_404(setup_database, async_authorized_client):
    response = await async_authorized_client.put("/api/v1/models/nope", json={"name": "x"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_a_get_of_a_model_that_is_not_there_is_a_404(setup_database, async_authorized_client):
    response = await async_authorized_client.get("/api/v1/models/nope")

    assert response.status_code == 404
