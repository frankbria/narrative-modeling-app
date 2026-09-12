"""#468 AC2: the export routes serve the caller's own models and 404 on anyone else's.

Real `MLModel` documents through the full app; only the artifact load is stubbed at the
storage seam (`load_model(model_id, user_id)` — the real, tenant-scoped signature).
"""
import pickle
import zipfile
from io import BytesIO
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from app.api.routes import model_export as routes
from app.models.ml_model import MLModel

pytestmark = pytest.mark.asyncio

TEST_USER = "test_user_123"  # what async_authorized_client authenticates as
ROUTES = ["python", "docker", "onnx", "pmml", "custom/python", "custom/docker"]


async def _model(owner: str, model_id: str) -> MLModel:
    return await MLModel(
        user_id=owner, dataset_id="ds-1", model_id=model_id, name="Owned", problem_type="binary_classification",
        algorithm="Logistic Regression", target_column="y", feature_names=["f1", "f2", "f3"], cv_score=0.8,
        test_score=0.8, training_time=1.0, model_size=1, n_samples_train=20, n_features=3,
        model_path=f"s3://bucket/models/{owner}/{model_id}/model.pkl",
    ).insert()


def _url(model_id: str, fmt: str) -> str:
    # "custom/<x>" is the POST catch-all /export/{format_type}; the rest are the GET routes
    return f"/api/v1/models/{model_id}/export/{fmt.split('/')[-1]}"


@pytest.mark.parametrize("fmt", ROUTES)
async def test_another_tenants_model_is_404(async_authorized_client, setup_database, fmt):
    await _model("someone-else", "m-foreign")
    with patch.object(routes.export_service.model_storage, "load_model", new_callable=AsyncMock) as load:
        response = await async_authorized_client.request(
            "POST" if fmt.startswith("custom/") else "GET", _url("m-foreign", fmt)
        )
    assert response.status_code == 404, f"{fmt}: {response.status_code} {response.text}"
    load.assert_not_awaited()


@pytest.mark.parametrize("fmt", ROUTES)
async def test_an_unknown_model_is_404(async_authorized_client, setup_database, fmt):
    response = await async_authorized_client.request(
        "POST" if fmt.startswith("custom/") else "GET", _url("m-nope", fmt)
    )
    assert response.status_code == 404, f"{fmt}: {response.status_code} {response.text}"


async def test_own_model_exports_python_and_docker(async_authorized_client, setup_database):
    await _model(TEST_USER, "m-mine")
    rng = np.random.RandomState(0)
    estimator = LogisticRegression().fit(rng.randn(20, 3), rng.choice([0, 1], 20))
    with patch.object(routes.export_service.model_storage, "load_model",
                      new_callable=AsyncMock, return_value=(estimator, None)) as load:
        py = await async_authorized_client.get(_url("m-mine", "python"))
        dk = await async_authorized_client.get(_url("m-mine", "docker"))
    assert py.status_code == 200 and "class ModelInference:" in py.text
    assert dk.status_code == 200
    with zipfile.ZipFile(BytesIO(dk.content)) as zf:
        assert pickle.loads(zf.read("model.pkl")).predict(np.zeros((1, 3))).shape == (1,)
    # the tenant-scoped signature, with the authenticated caller — never a placeholder
    for call in load.await_args_list:
        assert call.args == ("m-mine", TEST_USER)


async def test_onnx_without_the_converter_is_501(async_authorized_client, setup_database):
    await _model(TEST_USER, "m-onnx")
    with patch("app.services.model_export.ONNX_AVAILABLE", False):
        response = await async_authorized_client.get(_url("m-onnx", "onnx"))
    assert response.status_code == 501, response.text
