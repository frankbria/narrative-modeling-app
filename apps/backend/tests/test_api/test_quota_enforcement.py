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

import app.api.routes.batch_prediction as batch_prediction_routes
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


def _no_op(*args, **kwargs) -> None:
    """Stand-in for `_spawn_processing`, so a test does not leave a background task
    running past its own teardown and re-saving its document into the next test."""


async def _returns_false(*args, **kwargs) -> bool:
    """Stand-in for `retry_job` losing the race, so the route 409s after both
    reservations have landed — the only point at which the refund is observable."""
    return False


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

    async def test_the_whole_two_step_flow_charges_exactly_one_unit(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """The claim this PR actually makes, asserted as a chain rather than as two
        halves.

        `/secure`'s release and `/confirm-pii-upload`'s charge are each pinned
        separately below, and both would still pass if a regression made *both* steps
        charge, or *both* release. What a tenant experiences is the sum, so that is
        what has to be asserted: one dataset, one unit.
        """
        import app.api.routes.secure_upload as secure_module
        from app.models.user_data import UserData

        monkeypatch.setattr(
            secure_module,
            "upload_file_to_s3",
            lambda *a, **k: (True, "s3://bucket/pii.csv"),
        )

        detected = await async_authorized_client.post(
            "/api/v1/upload/secure",
            files={"file": ("pii.csv", self.PII_CSV, "text/csv")},
        )
        assert detected.status_code == 200, detected.text
        assert detected.json().get("requires_confirmation") is True
        assert await metering.usage_for(TEST_USER, "uploads") == 0

        confirmed = await async_authorized_client.post(
            "/api/v1/upload/confirm-pii-upload",
            files={"file": ("pii.csv", self.PII_CSV, "text/csv")},
        )
        assert confirmed.status_code == 200, confirmed.text

        # One dataset, one unit — not two of either.
        assert await metering.usage_for(TEST_USER, "uploads") == 1
        assert await UserData.find(UserData.user_id == TEST_USER).count() == 1

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
                "dataset_committed": False,  # failed before create_dataset()
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

    async def test_a_dataset_that_was_actually_created_is_still_charged(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """The mirror of the leak above, and the reason `success` alone is not enough
        to decide on.

        `apply_feature_to_dataset`'s catch-all wraps the *whole* create-and-save
        sequence: `create_dataset()` persists the new dataset in both id-spaces, and
        `feature.save()` comes after it. If anything between them raises, the service
        returns `success: False` while a real, billable dataset exists — and releasing
        on that hands the tenant a free dataset.
        """
        import app.api.routes.features as features_module

        await self._seed_feature()

        async def _apply(**kwargs):
            return {
                "success": False,
                "dataset_committed": True,  # create_dataset() got through
                "dataset_id": "ds-new",
                "column_name": "doubled",
                "rows_computed": 0,
                "null_values": 0,
                "warnings": [],
                "error": "failed after the dataset was written",
                "s3_url": None,
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
                "dataset_committed": True,
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


class TestBatchRetryQuota:
    """A retry re-runs every prediction, so it must charge like a creation (#460).

    The retry path reset the job and re-spawned processing with no reservation at all,
    so the same N predictions ran again for free. Bounded at 3 by `max_retries` rather
    than unlimited — `mark_failed` increments `retry_count` and `can_retry()` checks it —
    but `MAX_BATCH_PREDICT_RECORDS` is 1,000,000 against a FREE ceiling of 1,000, so three
    free re-runs of one job is still up to 3,000x a monthly plan.

    The input survives in S3 (`batch-jobs/{user}/{model}/{ts}/input.csv`), so this is a
    live path that really does re-execute the work, not a dead one.
    """

    ROWS = 40

    async def _failed_job(
        self,
        *,
        rows: int | None = None,
        retry_count: int = 0,
        job_id: str = "job-retry-1",
        user_id: str = TEST_USER,
    ) -> str:
        """A job in the one state `can_retry()` accepts."""
        from app.models.batch_job import BatchJob, JobProgress, JobStatus, JobType

        job = BatchJob(
            job_id=job_id,
            job_type=JobType.BATCH_PREDICTION,
            user_id=user_id,
            config={"model_id": "m1"},
            input_path="batch-jobs/u/m1/ts/input.csv",
            status=JobStatus.FAILED,
            retry_count=retry_count,
            error_message="original failure",
            progress=JobProgress(total_records=rows if rows is not None else self.ROWS),
        )
        await job.insert()
        return job.job_id

    async def test_a_retry_at_the_limit_is_refused(
        self, async_authorized_client, setup_database
    ):
        job_id = await self._failed_job()
        await _fill(TEST_USER, "predictions", PLAN_LIMITS[PlanTier.FREE].predictions)

        response = await async_authorized_client.post(f"/api/v1/batch/jobs/{job_id}/retry")

        assert response.status_code == 402, response.text
        assert response.json()["detail"]["metric"] == "predictions"

    async def test_a_refused_retry_runs_nothing(
        self, async_authorized_client, setup_database
    ):
        """AC4's second half. A 402 that still restarts the job is the bug with a
        different status code on it — the predictions are what cost money."""
        from app.models.batch_job import BatchJob, JobStatus

        job_id = await self._failed_job()
        await _fill(TEST_USER, "predictions", PLAN_LIMITS[PlanTier.FREE].predictions)

        await async_authorized_client.post(f"/api/v1/batch/jobs/{job_id}/retry")

        job = await BatchJob.find_one(BatchJob.job_id == job_id)
        assert job is not None
        assert job.status == JobStatus.FAILED, "the job was restarted despite the 402"
        assert job.started_at is None

    async def test_a_retry_costs_its_rows_not_one(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """The whole issue: 40 rows fit in 40 remaining and not in 39. Charging one
        unit per retry passes neither half.

        Two **separate** jobs, not one retried twice. Reusing one would need the first
        retry's background task to fail it back to FAILED before the second POST — an
        unsynchronized race that nothing awaits, and which would fail this test with a
        409 pointing nowhere near the cause. Processing is stubbed out for the same
        reason: a live task outliving the test can re-save its document into the next
        test's freshly wiped collection.
        """
        limit = PLAN_LIMITS[PlanTier.FREE].predictions
        monkeypatch.setattr(
            batch_prediction_routes.batch_service, "_spawn_processing", _no_op
        )
        fits_id = await self._failed_job(job_id="job-fits")
        over_id = await self._failed_job(job_id="job-over")

        await _fill(TEST_USER, "predictions", limit - self.ROWS)
        fits = await async_authorized_client.post(f"/api/v1/batch/jobs/{fits_id}/retry")
        assert fits.status_code != 402, fits.text

        await UsageRecord.find(UsageRecord.user_id == TEST_USER).delete()
        await _fill(TEST_USER, "predictions", limit - self.ROWS + 1)
        does_not = await async_authorized_client.post(
            f"/api/v1/batch/jobs/{over_id}/retry"
        )
        assert does_not.status_code == 402, does_not.text

    async def test_another_tenants_job_is_not_retryable(
        self, async_authorized_client, setup_database
    ):
        """Foreign and unknown must answer identically, or the status code is an
        existence oracle — and a refactor to `find_one({"job_id"})` would otherwise
        sail through this suite while letting one tenant restart another's job at
        their expense."""
        from app.models.batch_job import BatchJob, JobStatus

        job_id = await self._failed_job(job_id="job-theirs", user_id="someone-else")

        response = await async_authorized_client.post(f"/api/v1/batch/jobs/{job_id}/retry")

        assert response.status_code == 404, response.text
        assert await metering.usage_for(TEST_USER, "predictions") == 0
        theirs = await BatchJob.find_one(BatchJob.job_id == job_id)
        assert theirs is not None
        assert theirs.status == JobStatus.FAILED, "another tenant's job was restarted"

    async def test_an_accepted_retry_charges_its_rows(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        monkeypatch.setattr(
            batch_prediction_routes.batch_service, "_spawn_processing", _no_op
        )
        job_id = await self._failed_job()

        response = await async_authorized_client.post(f"/api/v1/batch/jobs/{job_id}/retry")

        assert response.status_code == 200, response.text
        assert await metering.usage_for(TEST_USER, "predictions") == self.ROWS

    async def test_two_simultaneous_retries_start_the_job_once(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """A double-click must not run the job twice.

        `retry_job` used to be read-check-write — `find_one`, `can_retry()`, `save()` —
        so both requests could pass the check before either wrote, and both would spawn
        processing: two tasks interleaving per-chunk saves from separate in-memory
        copies, two output uploads, and one `retry_count` increment for two executions.
        The claim is now a single conditional update, so the database picks the winner.
        """
        import asyncio

        spawned: list[str] = []
        monkeypatch.setattr(
            batch_prediction_routes.batch_service,
            "_spawn_processing",
            lambda job: spawned.append(job.job_id),
        )
        job_id = await self._failed_job()

        first, second = await asyncio.gather(
            async_authorized_client.post(f"/api/v1/batch/jobs/{job_id}/retry"),
            async_authorized_client.post(f"/api/v1/batch/jobs/{job_id}/retry"),
        )

        codes = sorted([first.status_code, second.status_code])
        assert codes == [200, 409], f"{codes}: {first.text} / {second.text}"
        assert spawned == [job_id], f"processing started {len(spawned)} times"
        # The loser is refunded in full, so a lost race costs nothing.
        assert await metering.usage_for(TEST_USER, "predictions") == self.ROWS

    async def test_a_claimed_job_is_updated_not_duplicated(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """The claim hands `_spawn_processing` a document rebuilt from a raw motor
        dict, and the spawned task saves it as it goes.

        If that reconstruction lost the `_id`, the first save would **insert** rather
        than update — `job_id` is `Indexed()`, not unique, so there would be no error,
        just a second document while the claimed original sat `pending` forever. It
        does preserve it, verified here rather than argued: every other retry test
        stubs `_spawn_processing`, so nothing else in the suite ever touches the
        rebuilt object. Raised by review as unverifiable from a runner without beanie.
        """
        from app.models.batch_job import BatchJob

        saved_ids: list[object] = []

        async def _process(job):
            saved_ids.append(job.id)
            job.progress.current_chunk = 1
            await job.save()

        monkeypatch.setattr(
            batch_prediction_routes.batch_service, "_process_batch_job", _process
        )
        job_id = await self._failed_job()
        original = await BatchJob.find_one(BatchJob.job_id == job_id)
        assert original is not None

        response = await async_authorized_client.post(f"/api/v1/batch/jobs/{job_id}/retry")
        assert response.status_code == 200, response.text

        # Let the spawned task run to completion before counting.
        for task in list(batch_prediction_routes.batch_service._background_tasks):
            await task

        assert saved_ids == [original.id], "the rebuilt job lost its _id"
        assert await BatchJob.find(BatchJob.job_id == job_id).count() == 1, (
            "the retry inserted a duplicate instead of updating the claimed job"
        )

    async def test_a_failed_retry_refunds_every_reserved_row(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """AC2, stated where it is actually observable.

        A retry reserves twice — 1 at admission, then rows-1 — and `reserve` appends
        rather than replaces. Asserting the *charge* after a successful retry does not
        test that: both `consume()` calls land on the counter either way, so 40 comes
        out right even if the second reservation overwrote the first on
        `request.state`. The difference only shows on the **refund**, where a replaced
        list hands back rows-1 and burns one unit on every failed retry, forever.

        (The first version of this test asserted the charge and passed with
        accumulation removed. The mutation check is the only reason that was caught.)
        """
        job_id = await self._failed_job()
        monkeypatch.setattr(
            batch_prediction_routes.batch_service,
            "retry_job",
            _returns_false,
        )

        response = await async_authorized_client.post(f"/api/v1/batch/jobs/{job_id}/retry")

        assert response.status_code >= 400, response.text
        assert await metering.usage_for(TEST_USER, "predictions") == 0

    async def test_a_denied_retry_leaves_usage_exactly_at_the_cap(
        self, async_authorized_client, setup_database
    ):
        """The admission unit must come back. Otherwise a tenant who is already at
        their cap is pushed *over* it by being refused."""
        limit = PLAN_LIMITS[PlanTier.FREE].predictions
        job_id = await self._failed_job()
        await _fill(TEST_USER, "predictions", limit)

        await async_authorized_client.post(f"/api/v1/batch/jobs/{job_id}/retry")

        assert await metering.usage_for(TEST_USER, "predictions") == limit

    async def test_an_unknown_job_is_not_a_quota_denial(
        self, async_authorized_client, setup_database
    ):
        """A caller with room must not be told they are out of quota because a job id
        was wrong, and the admission unit must be refunded."""
        response = await async_authorized_client.post("/api/v1/batch/jobs/nope/retry")

        assert response.status_code == 404, response.text
        assert await metering.usage_for(TEST_USER, "predictions") == 0

    async def test_a_job_that_is_not_failed_cannot_be_retried(
        self, async_authorized_client, setup_database
    ):
        from app.models.batch_job import BatchJob, JobStatus

        job_id = await self._failed_job()
        job = await BatchJob.find_one(BatchJob.job_id == job_id)
        assert job is not None
        job.status = JobStatus.COMPLETED
        await job.save()

        response = await async_authorized_client.post(f"/api/v1/batch/jobs/{job_id}/retry")

        assert response.status_code == 409, response.text
        assert await metering.usage_for(TEST_USER, "predictions") == 0

    async def test_an_exhausted_retry_budget_says_so(
        self, async_authorized_client, setup_database
    ):
        """`can_retry()` also fails when retry_count has reached max_retries, and a
        single 400 for all three refusal reasons tells the caller nothing."""
        job_id = await self._failed_job(retry_count=3)

        response = await async_authorized_client.post(f"/api/v1/batch/jobs/{job_id}/retry")

        assert response.status_code == 409, response.text
        assert "retr" in response.json()["detail"].lower()


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
