"""Plan enforcement on the metered endpoints (#368).

These go through `async_authorized_client` — the full app with auth overridden —
because the thing under test is the *wiring*: the dependency being attached to the
right routes, the refund middleware being registered, and the 402 carrying enough
for a client to act on. A test against the dependency function in isolation would
pass with the dependency attached to nothing (see the #267 footgun).

`RateLimitMiddleware` is disabled in the test env, which is what makes the 402s
here unambiguous — a 429 would mean something else entirely.
"""

import pytest

from app.billing import metering
from app.billing.plans import PLAN_LIMITS
from app.models.subscription import PlanTier, Subscription, SubscriptionStatus
from app.models.usage import UsageRecord

pytestmark = pytest.mark.asyncio

#: What `async_authorized_client` overrides the auth dependency to return.
TEST_USER = "test_user_123"
FREE_UPLOADS = PLAN_LIMITS[PlanTier.FREE].uploads


async def _fill(user_id: str, metric: str, units: int) -> None:
    """Put a tenant at `units` used without going through the endpoints."""
    await UsageRecord(
        user_id=user_id,
        period_key=metering.period_key_for(),
        metric=metric,
        units=units,
    ).insert()


class TestUploadQuota:
    async def test_upload_is_refused_at_the_free_limit(
        self, async_authorized_client, setup_database
    ):
        await _fill(TEST_USER, "uploads", FREE_UPLOADS)

        response = await async_authorized_client.post(
            "/api/v1/datasets/upload",
            files={"file": ("d.csv", b"a,b\n1,2\n", "text/csv")},
        )

        assert response.status_code == 402
        body = response.json()["detail"]
        assert body["error"] == "quota_exceeded"
        assert body["metric"] == "uploads"
        assert body["limit"] == FREE_UPLOADS
        # A client cannot render "resets in N days" or an upgrade CTA without
        # these, and a bare 402 would send them to a support ticket instead.
        assert body["resets_at"]
        assert body["upgrade_available"] is True

    async def test_a_refused_upload_does_not_consume_a_unit(
        self, async_authorized_client, setup_database
    ):
        await _fill(TEST_USER, "uploads", FREE_UPLOADS)

        await async_authorized_client.post(
            "/api/v1/datasets/upload",
            files={"file": ("d.csv", b"a,b\n1,2\n", "text/csv")},
        )

        assert await metering.usage_for(TEST_USER, "uploads") == FREE_UPLOADS

    async def test_a_failed_upload_is_refunded(
        self, async_authorized_client, setup_database
    ):
        """The reason the refund middleware exists.

        An unsupported file type 4xxs *after* the dependency has already reserved.
        Without the refund, twenty malformed files exhaust a free tenant's month.
        """
        response = await async_authorized_client.post(
            "/api/v1/datasets/upload",
            files={"file": ("notes.exe", b"MZ\x00", "application/octet-stream")},
        )

        assert response.status_code >= 400
        assert await metering.usage_for(TEST_USER, "uploads") == 0


class TestTrainingQuota:
    async def test_training_is_refused_at_the_free_limit(
        self, async_authorized_client, setup_database
    ):
        await _fill(
            TEST_USER, "training_runs", PLAN_LIMITS[PlanTier.FREE].training_runs
        )

        response = await async_authorized_client.post(
            "/api/v1/ml/train",
            json={"dataset_id": "507f1f77bcf86cd799439011", "target_column": "y"},
        )

        assert response.status_code == 402
        assert response.json()["detail"]["metric"] == "training_runs"

    async def test_a_paid_tier_is_not_stopped_at_the_free_limit(
        self, async_authorized_client, setup_database
    ):
        """Enforcement must read the tenant's actual tier, not a constant.

        Hardcoding the free limits would pass every other test in this file.
        """
        # `plan_tier`, not `tier`. Pydantic drops the unknown keyword silently and
        # you get a FREE subscription that looks right in the test source.
        await Subscription(
            user_id=TEST_USER,
            plan_tier=PlanTier.PRO,
            status=SubscriptionStatus.ACTIVE,
        ).insert()
        await _fill(
            TEST_USER, "training_runs", PLAN_LIMITS[PlanTier.FREE].training_runs
        )

        response = await async_authorized_client.post(
            "/api/v1/ml/train",
            json={"dataset_id": "507f1f77bcf86cd799439011", "target_column": "y"},
        )

        # Past the gate. The dataset does not exist, so it fails downstream — but
        # with a 404, not a 402, which is the distinction being asserted.
        assert response.status_code != 402


class TestPredictionQuota:
    async def test_prediction_is_refused_at_the_free_limit(
        self, async_authorized_client, setup_database
    ):
        await _fill(
            TEST_USER, "predictions", PLAN_LIMITS[PlanTier.FREE].predictions
        )

        response = await async_authorized_client.post(
            "/api/v1/ml/some-model/predict", json={"data": [{"x": 1}]}
        )

        assert response.status_code == 402
        assert response.json()["detail"]["metric"] == "predictions"

    async def test_batch_jobs_are_metered_as_predictions(
        self, async_authorized_client, setup_database
    ):
        await _fill(
            TEST_USER, "predictions", PLAN_LIMITS[PlanTier.FREE].predictions
        )

        response = await async_authorized_client.post(
            "/api/v1/batch/jobs",
            files={"file": ("d.csv", b"x\n1\n", "text/csv")},
            data={"model_id": "m1"},
        )

        assert response.status_code == 402


class TestChargedByRecord:
    async def test_a_batch_that_exactly_fits_is_allowed(
        self, async_authorized_client, setup_database
    ):
        """The permissive half of the boundary.

        Asserted as a pair with the test below: four records fit in four remaining
        but not in three. Either test alone is satisfiable by charging per request —
        together they pin the charge to the record count.
        """
        limit = PLAN_LIMITS[PlanTier.FREE].predictions
        await _fill(TEST_USER, "predictions", limit - 4)

        response = await async_authorized_client.post(
            "/api/v1/ml/some-model/predict",
            json={"data": [{"x": i} for i in range(4)]},
        )

        assert response.status_code != 402

    async def test_a_batch_beyond_the_remaining_quota_is_refused_whole(
        self, async_authorized_client, setup_database
    ):
        limit = PLAN_LIMITS[PlanTier.FREE].predictions
        await _fill(TEST_USER, "predictions", limit - 3)

        response = await async_authorized_client.post(
            "/api/v1/ml/some-model/predict",
            json={"data": [{"x": i} for i in range(5)]},
        )

        assert response.status_code == 402
        # Not partially served — still exactly what it was.
        assert await metering.usage_for(TEST_USER, "predictions") == limit - 3


class TestNonMeteredRoutes:
    async def test_reads_are_not_metered(
        self, async_authorized_client, setup_database
    ):
        """Enforcement must not leak onto the read surface.

        Attaching the dependency at the router rather than the route would meter
        listing your own models, which nobody is paying for.
        """
        await _fill(TEST_USER, "predictions", PLAN_LIMITS[PlanTier.FREE].predictions)
        await _fill(TEST_USER, "uploads", FREE_UPLOADS)

        response = await async_authorized_client.get("/api/v1/ml/models")

        assert response.status_code != 402
