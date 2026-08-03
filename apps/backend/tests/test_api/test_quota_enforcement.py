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
from app.models.batch_job import BatchJob
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

    async def test_a_failed_training_run_is_refunded(
        self, async_authorized_client, setup_database
    ):
        # The third metric through the refund middleware. Training is the one where
        # a burned unit costs the most — 10 a month on FREE, so two typo'd dataset
        # ids would be a fifth of the month.
        response = await async_authorized_client.post(
            "/api/v1/ml/train",
            json={"dataset_id": "507f1f77bcf86cd799439011", "target_column": "y"},
        )

        assert response.status_code >= 400
        assert await metering.usage_for(TEST_USER, "training_runs") == 0

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


class TestBatchJobRowCount:
    """A batch job costs its rows, and is refused before any of them run.

    The gap this closes: reserving 1 unit at admission and truing up afterwards
    with an unconditional `record()` is not a limit at all. `MAX_BATCH_PREDICT_
    RECORDS` is 1,000,000 against a FREE ceiling of 1,000, so a tenant with one
    unit left could have a million predictions accepted AND EXECUTED — a compute
    bill, not just a wrong counter. The reservation has to happen before the job is
    created, because creation spawns processing immediately (`auto_start`), and
    unwinding a running job is a race.
    """

    @staticmethod
    def _csv(rows: int) -> bytes:
        body = "\n".join(str(i) for i in range(rows))
        return f"x\n{body}\n".encode()

    async def test_a_batch_larger_than_the_quota_is_refused(
        self, async_authorized_client, setup_database
    ):
        limit = PLAN_LIMITS[PlanTier.FREE].predictions

        response = await async_authorized_client.post(
            "/api/v1/batch/jobs",
            files={"file": ("d.csv", self._csv(limit + 500), "text/csv")},
            data={"model_id": "m1"},
        )

        assert response.status_code == 402
        # Nothing consumed, and — the point — nothing queued to run either.
        assert await metering.usage_for(TEST_USER, "predictions") == 0
        assert await BatchJob.find(BatchJob.user_id == TEST_USER).count() == 0

    async def test_the_charge_is_the_row_count_not_one(
        self, async_authorized_client, setup_database
    ):
        """Boundary pair, for the same reason as the JSON one.

        The job itself fails downstream (no such model) and the middleware refunds,
        so the charge is not observable in the counter afterwards. What *is*
        observable: 40 rows fit in 40 remaining and not in 39. Charging one unit
        per request passes neither half.
        """
        limit = PLAN_LIMITS[PlanTier.FREE].predictions
        await _fill(TEST_USER, "predictions", limit - 40)

        fits = await async_authorized_client.post(
            "/api/v1/batch/jobs",
            files={"file": ("d.csv", self._csv(40), "text/csv")},
            data={"model_id": "m1"},
        )
        assert fits.status_code != 402

        await UsageRecord.find(UsageRecord.user_id == TEST_USER).delete()
        await _fill(TEST_USER, "predictions", limit - 39)

        does_not = await async_authorized_client.post(
            "/api/v1/batch/jobs",
            files={"file": ("d.csv", self._csv(40), "text/csv")},
            data={"model_id": "m1"},
        )
        assert does_not.status_code == 402

    async def test_a_failed_batch_refunds_every_reserved_row(
        self, async_authorized_client, setup_database
    ):
        """Both reservations, not just the last one.

        A batch reserves twice — 1 at admission, then the remaining rows. If the
        second overwrites the first on `request.state` instead of accumulating, the
        refund returns rows-1 and burns one unit per failed job, forever.
        """
        await async_authorized_client.post(
            "/api/v1/batch/jobs",
            files={"file": ("d.csv", self._csv(40), "text/csv")},
            data={"model_id": "m1"},
        )

        assert await metering.usage_for(TEST_USER, "predictions") == 0


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
