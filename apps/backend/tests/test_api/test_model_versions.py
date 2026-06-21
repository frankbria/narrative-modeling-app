"""Tests for model versioning endpoints (issue #78).

Exercise the real version-family logic against a real Mongo (no mocking): the
family is grouped by (user_id, dataset_id, name) and promotion flips the
``is_production`` flag across siblings. ``async_authorized_client`` authenticates
as ``test_user_123``.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.ml_model import MLModel

USER = "test_user_123"


def _model(model_id: str, *, name: str, dataset_id: str, created_offset: int) -> MLModel:
    return MLModel(
        user_id=USER,
        dataset_id=dataset_id,
        model_id=model_id,
        name=name,
        problem_type="binary_classification",
        algorithm="Random Forest",
        target_column="target",
        feature_names=["f1", "f2"],
        cv_score=0.8 + created_offset / 100,
        test_score=0.78 + created_offset / 100,
        training_time=1.0,
        model_size=10,
        n_samples_train=100,
        n_features=2,
        model_path="s3://bucket/model.pkl",
        created_at=datetime.now(UTC) + timedelta(seconds=created_offset),
    )


@pytest.fixture
async def family():
    """Two-version family + an unrelated model; cleaned up after."""
    models = [
        _model("ver-v1", name="Churn", dataset_id="ds-1", created_offset=0),
        _model("ver-v2", name="Churn", dataset_id="ds-1", created_offset=10),
        _model("other", name="Other", dataset_id="ds-1", created_offset=5),
    ]
    for m in models:
        await m.insert()
    yield models
    await MLModel.find(MLModel.user_id == USER).delete()


class TestListVersions:
    @pytest.mark.asyncio
    async def test_lists_family_oldest_first_with_version_numbers(
        self, async_authorized_client, family
    ):
        resp = await async_authorized_client.get("/api/v1/ml/ver-v2/versions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Churn"
        assert body["total"] == 2  # excludes the unrelated "Other" model
        ids = [v["model_id"] for v in body["versions"]]
        assert ids == ["ver-v1", "ver-v2"]  # oldest first
        assert [v["version_number"] for v in body["versions"]] == [1, 2]
        # Lineage data is present per row.
        assert body["versions"][0]["feature_names"] == ["f1", "f2"]
        assert body["versions"][0]["dataset_id"] == "ds-1"

    @pytest.mark.asyncio
    async def test_unknown_model_returns_404(self, async_authorized_client):
        resp = await async_authorized_client.get("/api/v1/ml/nope/versions")
        assert resp.status_code == 404


class TestPromoteAndRollback:
    @pytest.mark.asyncio
    async def test_promote_then_rollback(self, async_authorized_client, family):
        # Promote v2 → production.
        resp = await async_authorized_client.post("/api/v1/ml/ver-v2/promote")
        assert resp.status_code == 200
        assert resp.json()["is_production"] is True
        assert resp.json()["promoted_at"] is not None

        listing = (
            await async_authorized_client.get("/api/v1/ml/ver-v1/versions")
        ).json()
        assert listing["production_model_id"] == "ver-v2"

        # Roll back: promote the older v1; v2 must be demoted.
        resp = await async_authorized_client.post("/api/v1/ml/ver-v1/promote")
        assert resp.status_code == 200
        assert resp.json()["demoted_model_ids"] == ["ver-v2"]

        listing = (
            await async_authorized_client.get("/api/v1/ml/ver-v2/versions")
        ).json()
        assert listing["production_model_id"] == "ver-v1"
        prod_flags = {v["model_id"]: v["is_production"] for v in listing["versions"]}
        assert prod_flags == {"ver-v1": True, "ver-v2": False}

    @pytest.mark.asyncio
    async def test_promote_unknown_returns_404(self, async_authorized_client):
        resp = await async_authorized_client.post("/api/v1/ml/nope/promote")
        assert resp.status_code == 404
