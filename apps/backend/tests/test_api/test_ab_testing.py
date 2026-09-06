"""Integration tests for the A/B testing route against the real backend (issue #262).

The feature was advertised in the main nav but unreachable: the frontend service
hit a relative URL with a non-existent auth token, so create/list silently 404'd.
These tests exercise the real ``/api/v1/ab-testing`` surface (real Mongo, real
auth dependency) so a working end-to-end path is guaranteed.

``async_authorized_client`` authenticates as ``test_user_123``; ``async_test_client``
sends no credentials.
"""

import pytest
from beanie.odm.operators.find.comparison import In

from app.models.ab_test import ABTest, ExperimentStatus, Variant
from app.models.ml_model import MLModel

USER = "test_user_123"
MODEL_IDS = ["abtest-m1", "abtest-m2"]


def _model(model_id: str) -> MLModel:
    return MLModel(
        user_id=USER,
        dataset_id="ds-abtest",
        model_id=model_id,
        name="AB Model",
        problem_type="binary_classification",
        algorithm="Random Forest",
        target_column="target",
        feature_names=["f1", "f2"],
        cv_score=0.81,
        test_score=0.79,
        training_time=1.0,
        model_size=10,
        n_samples_train=100,
        n_features=2,
        model_path="s3://bucket/model.pkl",
    )


@pytest.fixture
async def two_models():
    models = [_model(mid) for mid in MODEL_IDS]
    for m in models:
        await m.insert()
    yield models
    await MLModel.find(In(MLModel.model_id, MODEL_IDS)).delete()
    await ABTest.find(ABTest.user_id == USER).delete()


class TestABTestingRoundTrip:
    @pytest.mark.asyncio
    async def test_create_then_list_experiment(self, async_authorized_client, two_models):
        create = await async_authorized_client.post(
            "/api/v1/ab-testing/experiments",
            json={
                "name": "Homepage model test",
                "model_ids": MODEL_IDS,
                "primary_metric": "accuracy",
            },
        )
        assert create.status_code == 200, create.text
        body = create.json()
        assert body["name"] == "Homepage model test"
        assert len(body["variants"]) == 2

        listed = await async_authorized_client.get("/api/v1/ab-testing/experiments")
        assert listed.status_code == 200
        ids = [e["experiment_id"] for e in listed.json()]
        assert body["experiment_id"] in ids

    @pytest.mark.asyncio
    async def test_create_rejects_unknown_model(self, async_authorized_client):
        resp = await async_authorized_client.post(
            "/api/v1/ab-testing/experiments",
            json={"name": "Bad", "model_ids": ["does-not-exist"], "primary_metric": "accuracy"},
        )
        assert resp.status_code == 400


class TestABTestingAuth:
    @pytest.mark.asyncio
    async def test_list_requires_auth(self, async_test_client):
        resp = await async_test_client.get("/api/v1/ab-testing/experiments")
        assert resp.status_code in (401, 403)


OTHER_USER = "other_user_450"


@pytest.fixture
async def foreign_running_experiment() -> ABTest:
    """A RUNNING experiment owned by someone other than the test user."""
    experiment = ABTest(
        user_id=OTHER_USER,
        experiment_id="abtest-foreign-450",
        name="Victim's experiment",
        primary_metric="accuracy",
        status=ExperimentStatus.RUNNING,
        variants=[
            Variant(
                variant_id="v1", name="control", model_id="victim-model-1",
                traffic_percentage=50.0,
            ),
            Variant(
                variant_id="v2", name="challenger", model_id="victim-model-2",
                traffic_percentage=50.0,
            ),
        ],
    )
    await experiment.insert()
    yield experiment
    await ABTest.find(ABTest.user_id == OTHER_USER).delete()


class TestABTestingUnauthenticatedEndpoints:
    """Issue #450 (P0.7).

    Eight endpoints on this router carry `Depends(get_current_user_id)`;
    `assign_variant` and `track_prediction` did not, and the router is mounted
    without a router-level dependency. Both were reachable by anyone.

    Note the real paths are under `/api/v1/ab-testing/` — the router declares its
    own `prefix="/ab-testing"` on top of the `include_router` prefix, which the
    issue's write-up missed.
    """

    @pytest.mark.asyncio
    async def test_assign_variant_requires_auth(
        self, async_test_client, foreign_running_experiment
    ):
        """Anonymous callers could read model_id for any experiment id."""
        resp = await async_test_client.get(
            "/api/v1/ab-testing/experiments/abtest-foreign-450/assign-variant",
            params={"user_identifier": "anon"},
        )
        assert resp.status_code in (401, 403)
        assert "victim-model" not in resp.text

    @pytest.mark.asyncio
    async def test_track_prediction_requires_auth(
        self, async_test_client, foreign_running_experiment
    ):
        """Anonymous callers could inject outcomes into any tenant's metrics."""
        resp = await async_test_client.post(
            "/api/v1/ab-testing/track-prediction",
            params={
                "experiment_id": "abtest-foreign-450",
                "variant_id": "v1",
                "latency_ms": 1.0,
                "success": False,
            },
        )
        assert resp.status_code in (401, 403)

        # and nothing was recorded against the victim's experiment
        reloaded = await ABTest.find_one(ABTest.experiment_id == "abtest-foreign-450")
        assert all(v.total_predictions == 0 for v in reloaded.variants)

    @pytest.mark.asyncio
    async def test_assign_variant_of_another_tenant_is_404(
        self, async_authorized_client, foreign_running_experiment
    ):
        """Authenticated is not enough — it must be the caller's experiment."""
        resp = await async_authorized_client.get(
            "/api/v1/ab-testing/experiments/abtest-foreign-450/assign-variant",
            params={"user_identifier": "someone"},
        )
        assert resp.status_code == 404
        assert "victim-model" not in resp.text

    @pytest.mark.asyncio
    async def test_track_prediction_on_another_tenants_experiment_is_404(
        self, async_authorized_client, foreign_running_experiment
    ):
        """The metric-poisoning path, with a session but the wrong tenant."""
        resp = await async_authorized_client.post(
            "/api/v1/ab-testing/track-prediction",
            params={
                "experiment_id": "abtest-foreign-450",
                "variant_id": "v1",
                "latency_ms": 5.0,
                "success": False,
            },
        )
        assert resp.status_code == 404

        reloaded = await ABTest.find_one(ABTest.experiment_id == "abtest-foreign-450")
        assert all(v.total_predictions == 0 for v in reloaded.variants)
        assert all(v.error_count == 0 for v in reloaded.variants)

    @pytest.fixture
    async def own_running_experiment(self) -> ABTest:
        """A RUNNING experiment owned by the authenticated test user."""
        experiment = ABTest(
            user_id=USER,
            experiment_id="abtest-own-450",
            name="My experiment",
            primary_metric="accuracy",
            status=ExperimentStatus.RUNNING,
            variants=[
                Variant(
                    variant_id="v1", name="control", model_id="my-model-1",
                    traffic_percentage=100.0,
                ),
            ],
        )
        await experiment.insert()
        yield experiment
        await ABTest.find(ABTest.experiment_id == "abtest-own-450").delete()

    @pytest.mark.asyncio
    async def test_owner_can_still_assign_a_variant(
        self, async_authorized_client, own_running_experiment
    ):
        """Regression guard: adding the dependency must not break the owner."""
        resp = await async_authorized_client.get(
            "/api/v1/ab-testing/experiments/abtest-own-450/assign-variant",
            params={"user_identifier": "customer-42"},
        )
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "my-model-1"

    @pytest.mark.asyncio
    async def test_owner_can_still_track_a_prediction(
        self, async_authorized_client, own_running_experiment
    ):
        """Regression guard, and proof the write still lands."""
        resp = await async_authorized_client.post(
            "/api/v1/ab-testing/track-prediction",
            params={
                "experiment_id": "abtest-own-450",
                "variant_id": "v1",
                "latency_ms": 12.5,
                "success": True,
            },
        )
        assert resp.status_code == 200

        reloaded = await ABTest.find_one(ABTest.experiment_id == "abtest-own-450")
        assert reloaded.variants[0].total_predictions == 1
        assert reloaded.variants[0].total_latency_ms == 12.5
