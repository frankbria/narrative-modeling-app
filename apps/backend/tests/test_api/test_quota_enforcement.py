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
from app.models.api_key import APIKey
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


#: The routes a real user's upload actually goes through. The frontend calls
#: `/upload/chunked/*`, `/upload/secure` and `/upload/confirm-pii-upload`; it never
#: calls `/datasets/upload`, which was the only route these tests used to exercise —
#: so metering coverage looked healthy while the user-facing paths were unguarded
#: (#459 AC4). `/datasets/upload` stays in the list: dropping it to fix the aim would
#: trade one blind spot for another.
_UPLOAD_ROUTES = [
    "/api/v1/upload/secure",
    "/api/v1/upload/confirm-pii-upload",
    "/api/v1/upload/",
    "/api/v1/datasets/upload",
]


class TestUploadQuota:
    @pytest.mark.parametrize("route", _UPLOAD_ROUTES)
    async def test_every_upload_route_is_refused_at_the_free_limit(
        self, async_authorized_client, setup_database, route
    ):
        """Parametrized over the real upload surface, not one route of four."""
        await _fill(TEST_USER, "uploads", FREE_UPLOADS)

        response = await async_authorized_client.post(
            route,
            files={"file": ("d.csv", b"a,b\n1,2\n", "text/csv")},
        )

        assert response.status_code == 402, f"{route}: {response.text}"
        assert response.json()["detail"]["metric"] == "uploads"

    async def test_the_chunked_completion_is_refused_at_the_free_limit(
        self, async_authorized_client, setup_database
    ):
        """The route the UI uses for large files, and the one #582 repaired.

        A session id that does not exist would normally 404 — the 402 has to come
        first, or a tenant at their cap still reaches the work.
        """
        await _fill(TEST_USER, "uploads", FREE_UPLOADS)

        response = await async_authorized_client.post(
            "/api/v1/upload/chunked/nonexistent-session/complete"
        )

        assert response.status_code == 402, response.text

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


class TestSampleDatasetQuota:
    """The onboarding sample loader creates a real dataset (#459, review round 1).

    It was left out of the first cut of this fix on the reasoning that onboarding
    content is ours rather than the tenant's upload. That reasoning was wrong: the
    `insert()` is unconditional — the `sample_datasets_loaded` check afterwards only
    guards a bookkeeping list — so the route mints a new dataset on every call, without
    limit, for a tenant already at their cap.
    """

    LOAD = "/api/v1/onboarding/sample-datasets/sales_data/load"

    async def test_loading_a_sample_is_refused_at_the_free_limit(
        self, async_authorized_client, setup_database
    ):
        await _fill(TEST_USER, "uploads", FREE_UPLOADS)

        response = await async_authorized_client.post(self.LOAD)

        assert response.status_code == 402, response.text
        assert response.json()["detail"]["metric"] == "uploads"


class TestUploadRefunds:
    """AC5 — a failed upload must give the unit back, on every metered route.

    Reserving happens before the work, so without this a free tenant's twenty uploads
    are twenty upload *attempts*, typos included.
    """

    @pytest.mark.parametrize("route", _UPLOAD_ROUTES)
    async def test_a_failed_upload_is_refunded(
        self, async_authorized_client, setup_database, route
    ):
        response = await async_authorized_client.post(
            route,
            files={"file": ("notes.exe", b"MZ\x00", "application/octet-stream")},
        )

        assert response.status_code >= 400, f"{route} unexpectedly succeeded"
        assert await metering.usage_for(TEST_USER, "uploads") == 0, route


class TestAFailedS3WriteIsNotABillableDataset:
    """`upload.py` used to return 200 with a placeholder string as the s3_url.

    **Two** branches did it, and the first fix only caught one — the other is what CI
    then failed on, because the two are reached under opposite conditions and the
    machine running the test decides which:

    * `s3_upload_failed` — S3 configured, the write failed. Needs credentials present
      to reach, so it is what a developer with AWS env vars sees.
    * `s3_not_configured` — no AWS env vars at all, so the write is never attempted.
      That is CI, and it short-circuits before the branch above.

    Either way the row's `s3_url` is a string that is not a URL, every later read of
    that dataset fails, and since #459 metered this route the tenant is charged an
    upload for it. `/upload/secure` already answered 500 for the configured-but-failed
    case. Both are parametrized here so neither environment can hide the other.
    """

    CSV = {"file": ("d.csv", b"a,b\n1,2\n", "text/csv")}

    async def test_a_failed_s3_write_does_not_leave_a_charged_broken_dataset(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """S3 configured, write fails."""
        import app.api.routes.upload as upload_module
        from app.models.user_data import UserData

        for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_BUCKET_NAME"):
            monkeypatch.setenv(var, "present-for-this-test")
        monkeypatch.setattr(
            upload_module, "upload_file_to_s3", lambda *a, **k: (False, None)
        )

        response = await async_authorized_client.post("/api/v1/upload/", files=self.CSV)

        assert response.status_code >= 400, response.text
        assert await metering.usage_for(TEST_USER, "uploads") == 0
        assert await UserData.find_one(UserData.user_id == TEST_USER) is None

    async def test_an_unconfigured_deployment_does_not_charge_for_a_stub_dataset(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """No AWS env at all — the CI case, and the one the first fix missed."""
        from app.models.user_data import UserData

        for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_BUCKET_NAME"):
            monkeypatch.delenv(var, raising=False)

        response = await async_authorized_client.post("/api/v1/upload/", files=self.CSV)

        assert response.status_code == 503, response.text
        assert await metering.usage_for(TEST_USER, "uploads") == 0
        assert await UserData.find_one(UserData.user_id == TEST_USER) is None


class TestPiiConfirmationChargesOnce:
    """The PII flow is two requests and one dataset (#459).

    `/secure` answers **200** with `requires_confirmation` when it finds high-risk PII
    and creates nothing; `/confirm-pii-upload` then creates the dataset. The refund
    middleware only sees >= 400, so without an explicit release the tenant is charged
    at both steps for the one dataset they end up with.
    """

    #: SSN-shaped *values* under a neutral column name. Deliberately not a column
    #: called "ssn": `_check_column_name` matches that, returns confidence exactly
    #: 0.8, and `continue`s past the value check — and "high" requires `> 0.8`, so
    #: the more obvious fixture is rated *medium* and never reaches the branch under
    #: test. (That short-circuit looks like a detector bug, but changing a PII
    #: threshold is not this issue's to make — filed separately.)
    PII_CSV = (
        b"identifier,amount\n"
        b"123-45-6789,10\n"
        b"987-65-4321,20\n"
        b"111-22-3333,30\n"
    )

    async def test_a_pii_detection_does_not_consume_a_unit(
        self, async_authorized_client, setup_database
    ):
        response = await async_authorized_client.post(
            "/api/v1/upload/secure",
            files={"file": ("pii.csv", self.PII_CSV, "text/csv")},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("requires_confirmation") is True, body
        assert await metering.usage_for(TEST_USER, "uploads") == 0


class TestFeatureApplyQuota:
    """`features/{id}/apply` creates a whole new dataset when asked to (#459).

    It reaches the same `DatasetService.create_dataset` as `/datasets/upload`, so a
    tenant at their cap could mint unlimited datasets through it. The charge is
    conditional rather than a route dependency: `create_new_dataset` defaults to
    false, and an in-place apply creates nothing to bill for.

    Both cases are asserted at the cap, where a reserve is unmistakable — it is the
    only thing that can produce a 402. Asserting on usage instead would prove nothing
    *for these two*, since the request fails downstream and the refund middleware
    returns the unit either way — but note that only holds because those failures
    raise. The ones that do not raise are the class below.
    """

    APPLY = "/api/v1/datasets/ds-feat/features/feat-1/apply"

    async def _seed_feature(self) -> None:
        from app.models.feature import (
            ExpressionNode,
            FeatureDefinition,
            NodeType,
        )

        await FeatureDefinition(
            user_id=TEST_USER,
            dataset_id="ds-feat",
            feature_id="feat-1",
            name="doubled",
            expression_tree=ExpressionNode(
                node_id="n1", node_type=NodeType.COLUMN, value="amount"
            ),
            is_valid=True,
        ).insert()

    async def test_creating_a_new_dataset_is_refused_at_the_free_limit(
        self, async_authorized_client, setup_database
    ):
        await self._seed_feature()
        await _fill(TEST_USER, "uploads", FREE_UPLOADS)

        response = await async_authorized_client.post(
            self.APPLY,
            json={
                "feature_id": "feat-1",
                "output_column_name": "doubled",
                "create_new_dataset": True,
            },
        )

        assert response.status_code == 402, response.text
        assert response.json()["detail"]["metric"] == "uploads"

    async def test_applying_in_place_is_not_charged(
        self, async_authorized_client, setup_database
    ):
        """The default. At the cap it must not 402 — an in-place apply adds a column
        to a dataset the tenant already paid for."""
        await self._seed_feature()
        await _fill(TEST_USER, "uploads", FREE_UPLOADS)

        response = await async_authorized_client.post(
            self.APPLY,
            json={
                "feature_id": "feat-1",
                "output_column_name": "doubled",
                "create_new_dataset": False,
            },
        )

        assert response.status_code != 402, response.text


class TestFeatureApplyDoesNotLeakOnASilentFailure:
    """`apply_feature_to_dataset` reports failure by **returning**, not raising.

    Both its failure paths — the S3 write of the new dataframe, and its catch-all —
    `return {"success": False, ...}`, which the route wraps in an
    `ApplyFeatureResponse` and answers **200**. `QuotaRefundMiddleware` refunds on
    >= 400, so the reserved unit is kept for a dataset that was never created.

    This is the `/upload/secure` PII bug in a second place, and it is what `release()`
    exists for: a 2xx that did no billable work has to hand the unit back itself.
    A tenant at 19 of 20 uploads who hits an S3 blip here would otherwise burn their
    last unit, receive nothing, and be 402'd for the rest of the month.
    """

    APPLY = "/api/v1/datasets/ds-feat/features/feat-1/apply"

    async def _seed_feature(self) -> None:
        from app.models.feature import ExpressionNode, FeatureDefinition, NodeType

        await FeatureDefinition(
            user_id=TEST_USER,
            dataset_id="ds-feat",
            feature_id="feat-1",
            name="doubled",
            expression_tree=ExpressionNode(
                node_id="n1", node_type=NodeType.COLUMN, value="amount"
            ),
            is_valid=True,
        ).insert()

    @staticmethod
    def _failing_result():
        async def _apply(**kwargs):
            return {
                "success": False,
                "dataset_id": "ds-feat",
                "column_name": "doubled",
                "rows_computed": 0,
                "null_values": 0,
                "warnings": [],
                "error": "Failed to upload to S3",
                "s3_url": None,
            }

        return _apply

    async def test_a_silent_failure_on_the_create_path_returns_the_unit(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        import app.api.routes.features as features_module

        await self._seed_feature()
        monkeypatch.setattr(
            features_module.feature_builder_service,
            "apply_feature_to_dataset",
            self._failing_result(),
        )

        response = await async_authorized_client.post(
            self.APPLY,
            json={
                "feature_id": "feat-1",
                "output_column_name": "doubled",
                "create_new_dataset": True,
            },
        )

        # The route's own contract: it answers 200 carrying success=false.
        assert response.status_code == 200, response.text
        assert response.json()["success"] is False
        assert await metering.usage_for(TEST_USER, "uploads") == 0

    async def test_a_successful_create_keeps_its_unit(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """The release must be conditional on failure — handing the unit back on a
        successful create would make the limit unenforceable."""
        import app.api.routes.features as features_module

        await self._seed_feature()

        async def _apply(**kwargs):
            return {
                "success": True,
                "dataset_id": "ds-new",
                "column_name": "doubled",
                "rows_computed": 3,
                "null_values": 0,
                "warnings": [],
                "error": None,
                "s3_url": "s3://bucket/ds-new.parquet",
            }

        monkeypatch.setattr(
            features_module.feature_builder_service,
            "apply_feature_to_dataset",
            _apply,
        )

        response = await async_authorized_client.post(
            self.APPLY,
            json={
                "feature_id": "feat-1",
                "output_column_name": "doubled",
                "create_new_dataset": True,
            },
        )

        assert response.status_code == 200, response.text
        assert await metering.usage_for(TEST_USER, "uploads") == 1


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


class TestProductionApiKeySurface:
    """The X-API-Key predict surface, which resolves its tenant differently.

    A distinct code path — the tenant comes off the key, not a session — and the
    one route in this PR that the other tests do not reach. Exactly the #267
    footgun this file exists to avoid: a dependency can be wired and never hit.
    """

    RAW_KEY = "sk_live_quota_enforcement_test_key_01"

    async def _key(self) -> None:
        await APIKey(
            key_id="qk1",
            key_hash=APIKey.hash_key(self.RAW_KEY),
            name="quota-test",
            user_id=TEST_USER,
        ).insert()

    async def test_a_capped_key_owner_is_refused(
        self, async_authorized_client, setup_database
    ):
        await self._key()
        await _fill(TEST_USER, "predictions", PLAN_LIMITS[PlanTier.FREE].predictions)

        response = await async_authorized_client.post(
            "/api/v1/production/v1/models/m1/predict",
            json={"data": [{"x": 1}]},
            headers={"X-API-Key": self.RAW_KEY},
        )

        assert response.status_code == 402
        assert response.json()["detail"]["metric"] == "predictions"

    async def test_the_production_surface_also_charges_per_record(
        self, async_authorized_client, setup_database
    ):
        await self._key()
        limit = PLAN_LIMITS[PlanTier.FREE].predictions
        await _fill(TEST_USER, "predictions", limit - 3)

        response = await async_authorized_client.post(
            "/api/v1/production/v1/models/m1/predict",
            json={"data": [{"x": i} for i in range(4)]},
            headers={"X-API-Key": self.RAW_KEY},
        )

        # Four records do not fit in three. Charging per request would let this
        # through, and this is the highest-volume predict surface there is.
        assert response.status_code == 402


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
