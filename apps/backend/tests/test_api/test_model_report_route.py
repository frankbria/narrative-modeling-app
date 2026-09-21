"""`GET /ml/{model_id}/report` — ownership, degradation, and the download (#795).

Uses `async_authorized_client` (the full app) with real documents rather than the
`mock_async_client`, which mounts only two routers and would make every assertion
here vacuous (#267).
"""

from datetime import UTC, datetime

import pytest

from app.models.ml_model import MLModel

OWNER = "test_user_123"  # matches the async_authorized_client override


def _model(model_id: str, user_id: str = OWNER) -> MLModel:
    return MLModel(
        user_id=user_id,
        dataset_id="ds-1",
        model_id=model_id,
        name="Churn model",
        problem_type="classification",
        algorithm="Random Forest",
        target_column="churned",
        feature_names=["tenure"],
        cv_score=0.9,
        test_score=0.88,
        training_time=3.0,
        model_size=10,
        n_samples_train=100,
        n_features=1,
        model_path="s3://b/m.pkl",
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_report_returns_sections_for_an_owned_model(
    async_authorized_client, setup_database
):
    await _model("rep-1").insert()

    response = await async_authorized_client.get("/api/v1/ml/rep-1/report")

    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == "rep-1"
    assert body["winner"]["algorithm"] == "Random Forest"
    # No training job seeded, so the leaderboard must say so rather than be empty.
    assert body["leaderboard"]["provenance"] == "not_recorded"
    assert body["leaderboard"]["note"]
    assert body["partial"] is True


@pytest.mark.asyncio
async def test_another_tenants_model_is_not_found(
    async_authorized_client, setup_database
):
    await _model("rep-foreign", user_id="someone-else").insert()

    response = await async_authorized_client.get("/api/v1/ml/rep-foreign/report")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unknown_model_is_404_not_500(async_authorized_client, setup_database):
    response = await async_authorized_client.get("/api/v1/ml/nope/report")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_markdown_download_is_attached_with_a_safe_filename(
    async_authorized_client, setup_database
):
    await _model("rep-md").insert()

    response = await async_authorized_client.get("/api/v1/ml/rep-md/report.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert "Model report" in response.text
    # The section that has no data says so in the document itself.
    assert "not recorded" in response.text.lower()
