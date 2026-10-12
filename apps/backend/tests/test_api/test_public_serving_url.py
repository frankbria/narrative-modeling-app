"""The serving URL handed to customers is the public one, from configuration (#915).

`deploy_model` and the SDK generator built it from `request.base_url`, which says
`http://` behind the TLS-terminating proxy. A generated SDK then posted to http, and
the redirect to https turned its POST into a GET.
"""

from pathlib import Path

import pytest
import yaml
from beanie.odm.operators.find.comparison import In

from app.models.ml_model import MLModel

pytestmark = pytest.mark.asyncio

PUBLIC = "https://ml.example.com/api/v1"
COMPOSE_FILE = Path(__file__).resolve().parents[4] / "docker-compose.staging.yml"
# What a client might send to steer the URL; the proxy's own headers look the same.
STEERING = {"Host": "evil.example", "X-Forwarded-Proto": "http", "X-Forwarded-Host": "evil.example"}


@pytest.fixture
async def model():
    doc = await MLModel(
        user_id="test_user_123", dataset_id="ds", model_id="public-url-1", name="m",
        problem_type="regression", algorithm="Random Forest", target_column="y",
        feature_names=["a"], cv_score=0.8, test_score=0.8, training_time=1.0, model_size=10,
        n_samples_train=100, n_features=1, model_path="s3://bucket/model.pkl",
    ).insert()
    yield doc
    await MLModel.find(In(MLModel.model_id, ["public-url-1"])).delete()


class TestADeployedInstanceIsToldItsPublicUrl:
    @pytest.fixture(autouse=True)
    def configured(self, monkeypatch):
        monkeypatch.setenv("PUBLIC_API_URL", PUBLIC + "/")

    async def test_deploy_stores_the_public_endpoint(self, async_authorized_client, model):
        response = await async_authorized_client.put("/api/v1/ml/public-url-1/deploy", json={}, headers=STEERING)

        assert response.status_code == 200, response.text
        assert response.json()["deployment_endpoint"] == f"{PUBLIC}/production/v1/models/public-url-1"

    async def test_the_sdk_is_compiled_with_the_public_endpoint(self, async_authorized_client, model):
        info = await async_authorized_client.get("/api/v1/ml/public-url-1/sdk", headers=STEERING)
        source = await async_authorized_client.get("/api/v1/ml/public-url-1/sdk/python", headers=STEERING)

        assert info.json()["serving_endpoint"] == f"{PUBLIC}/production/v1/models/public-url-1"
        assert f"{PUBLIC}/production/v1/models/public-url-1" in source.text
        assert "http://" not in source.text and "evil.example" not in source.text


@pytest.mark.parametrize("value", [None, "", "   "])
async def test_without_configuration_the_request_says_where_it_arrived(
    async_authorized_client, model, monkeypatch, value
):
    """Local development: no proxy, so the request's own base is the right one."""
    monkeypatch.delenv("PUBLIC_API_URL", raising=False)
    if value is not None:
        monkeypatch.setenv("PUBLIC_API_URL", value)  # compose passes an absent value as ""

    response = await async_authorized_client.put("/api/v1/ml/public-url-1/deploy", json={})

    assert response.json()["deployment_endpoint"] == "http://test/api/v1/production/v1/models/public-url-1"


async def test_staging_passes_the_backend_the_url_the_frontend_is_built_with():
    backend = yaml.safe_load(COMPOSE_FILE.read_text())["services"]["backend"]["environment"]

    assert backend["PUBLIC_API_URL"] == "${NEXT_PUBLIC_API_URL:-}"
