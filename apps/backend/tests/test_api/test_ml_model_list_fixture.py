"""The dashboard's Recent Models fixture is a real `GET /ml/` answer (#1069).

The dashboard read Recent Models from `/models`, the dead `ModelConfig` surface,
so the list was empty for every user and nothing linked to a trained model's
page. Its jest suite stayed green on a hand-written body. The suite now renders
this fixture, and this test keeps it equal to what the route returns.

Regenerate after a deliberate response change:
    UPDATE_FIXTURES=1 PYTHONPATH=. uv run pytest tests/test_api/test_ml_model_list_fixture.py
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.models.ml_model import MLModel

FIXTURE = (
    Path(__file__).resolve().parents[4] / "apps/frontend/__tests__/fixtures/mlModelList.json"
)
USER = "test_user_123"


async def _model(model_id: str, name: str, day: int, score: float, algorithm: str, **fields) -> None:
    await MLModel(
        user_id=USER, dataset_id="ds-1", model_id=model_id, name=name,
        problem_type="binary_classification", algorithm=algorithm,
        target_column="churn", feature_names=["tenure"], cv_score=0.8, test_score=score,
        training_time=1.0, model_size=1, n_samples_train=10, n_features=1,
        model_path=f"models/{USER}/{model_id}.pkl",
        created_at=datetime(2026, 10, day, tzinfo=UTC), **fields,
    ).insert()


@pytest.mark.asyncio
async def test_the_dashboard_fixture_is_the_real_model_list(
    async_authorized_client, setup_database
):
    await _model("model-1", "Churn Predictor", 1, 0.85, "Random Forest")
    await _model("model-2", "Sales Forecaster", 2, 0.92, "XGBoost", is_deployed=True)

    response = await async_authorized_client.get("/api/v1/ml/")
    assert response.status_code == 200
    body = response.json()

    # Newest first, and the deployed flag the dashboard's Deploy action reads.
    assert [m["model_id"] for m in body] == ["model-2", "model-1"]
    assert [m["is_deployed"] for m in body] == [True, False]

    if os.getenv("UPDATE_FIXTURES"):
        FIXTURE.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    assert json.loads(FIXTURE.read_text()) == body, f"regenerate {FIXTURE.name}"
