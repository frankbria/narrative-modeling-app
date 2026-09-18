"""Funnel telemetry (#769 AC1, AC3).

Every event is written server-side, from the code path that already knows it
happened, against real Mongo. A mocked insert would pass no matter which path
forgot to call the recorder.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.billing import enforcement, storage
from app.middleware.metrics import quota_denials
from app.models.product_event import ProductEvent
from app.models.user_data import UserData
from app.services import product_events
from app.services.product_events import (
    ACCOUNT_CREATED,
    CHECKOUT_COMPLETED,
    CHECKOUT_STARTED,
    FIRST_MODEL_TRAINED,
    FIRST_UPLOAD,
    QUOTA_DENIED,
    SUBSCRIPTION_CANCELLED,
    funnel,
)

TEST_USER = "test_user_123"


async def _events(event: str, user_id: str = TEST_USER) -> list[ProductEvent]:
    return await ProductEvent.find(
        ProductEvent.user_id == user_id, ProductEvent.event == event
    ).to_list()


def _dataset(user_id: str = TEST_USER) -> UserData:
    return UserData(
        user_id=user_id, filename="d.csv", original_filename="d.csv",
        s3_url="s3://b/datasets/x/d.csv", num_rows=1, num_columns=1, data_schema=[],
    )


class TestRecorder:
    async def test_a_once_key_records_one_event_however_often_it_fires(self, setup_database):
        for _ in range(3):
            await product_events.record(TEST_USER, CHECKOUT_COMPLETED, once="cs_1")
        await product_events.record(TEST_USER, CHECKOUT_COMPLETED, once="cs_2")

        assert len(await _events(CHECKOUT_COMPLETED)) == 2

    async def test_without_a_once_key_every_occurrence_counts(self, setup_database):
        await product_events.record(TEST_USER, QUOTA_DENIED, metric="uploads", tier="free")
        await product_events.record(TEST_USER, QUOTA_DENIED, metric="uploads", tier="free")

        rows = await _events(QUOTA_DENIED)
        assert len(rows) == 2
        assert rows[0].properties == {"metric": "uploads", "tier": "free"}

    async def test_a_storage_failure_never_reaches_the_caller(self, setup_database):
        """Telemetry must not fail an upload, a training run or a webhook."""
        with patch.object(ProductEvent, "insert", side_effect=RuntimeError("mongo down")):
            await product_events.record(TEST_USER, CHECKOUT_STARTED, tier="pro")

    async def test_the_collection_expires_events(self, setup_database):
        """Retention is bounded (13 months), like every telemetry store here."""
        info = await ProductEvent.get_motor_collection().index_information()
        ttl = [i for i in info.values() if "expireAfterSeconds" in i]
        assert ttl and ttl[0]["expireAfterSeconds"] == 395 * 24 * 3600


class TestHooks:
    async def test_first_upload_fires_once_from_any_dataset_writer(self, setup_database):
        """A model-level hook, so every writer that inserts a UserData — six today —
        is covered, and the seventh cannot forget."""
        await _dataset().insert()
        await _dataset().insert()
        await _dataset("someone-else").insert()

        assert len(await _events(FIRST_UPLOAD)) == 1
        assert len(await _events(FIRST_UPLOAD, "someone-else")) == 1

    async def test_first_upload_fires_for_a_dataset_created_with_save(self, setup_database):
        """/datasets/upload creates its UserData with save(), an upsert that fires no
        Insert event."""
        from app.services.dataset_service import DatasetService

        await DatasetService().create_dataset(
            user_id=TEST_USER, dataset_id="ds-1", filename="d.csv", original_filename="d.csv",
            file_type="csv", file_path=f"datasets/{TEST_USER}/d.csv",
            s3_url=f"s3://bucket/datasets/{TEST_USER}/d.csv", file_size=1,
            num_rows=2, num_columns=2, columns=["a", "b"], data_schema=[],
        )

        assert len(await _events(FIRST_UPLOAD)) == 1

    async def test_saving_an_existing_dataset_does_not_touch_the_events(self, setup_database):
        """Only a creation records first_upload. Every later save (AI summary,
        processing) must not pay an insert attempt, so none is made."""
        dataset = _dataset()
        await dataset.insert()
        await ProductEvent.find_all().delete()

        with patch.object(ProductEvent, "insert") as insert:
            dataset.num_rows = 2
            await dataset.save()

        insert.assert_not_called()

    async def test_quota_denial_is_recorded_and_counted(self, setup_database):
        before = quota_denials.labels(metric="uploads", tier="free")._value.get()
        request = Request({"type": "http", "headers": [], "state": {}})

        with patch("app.billing.plans.PlanLimits.limit_for", return_value=0):
            with pytest.raises(HTTPException) as exc:
                await enforcement.reserve(request, TEST_USER, "uploads")

        assert exc.value.status_code == 402
        rows = await _events(QUOTA_DENIED)
        assert [r.properties for r in rows] == [{"metric": "uploads", "tier": "free"}]
        assert quota_denials.labels(metric="uploads", tier="free")._value.get() == before + 1

    async def test_storage_denial_is_recorded(self, setup_database):
        with pytest.raises(HTTPException):
            await storage.enforce_storage_ceiling(TEST_USER, 10**12)

        rows = await _events(QUOTA_DENIED)
        assert [r.properties for r in rows] == [{"metric": "storage_mb", "tier": "free"}]

    async def test_first_model_trained_fires_when_training_saves_a_model(self, setup_database):
        import pandas as pd

        from app.api.routes.model_training import TrainModelRequest, train_model_task
        from app.services.model_training import ProblemType
        from app.services.model_training.automl_engine import (
            AutoMLResult,
            ModelCandidate,
        )

        df = pd.DataFrame({"a": range(20), "target": [0, 1] * 10})
        dataset = MagicMock(id="ds", user_id=TEST_USER, file_type="csv", num_rows=20,
                            data_schema=[], s3_url="s3://b/datasets/u/d.csv")
        result = AutoMLResult(
            best_model=ModelCandidate(name="RF", estimator=MagicMock(), hyperparameters={},
                                      cv_score=0.8, test_score=0.8, training_time=1.0),
            all_models=[], problem_type=ProblemType.BINARY_CLASSIFICATION,
            feature_names=["a"], feature_importance=None, training_time=1.0, metadata={},
        )
        with patch("app.services.s3_service.S3Service.download_file_bytes",
                   new_callable=AsyncMock, return_value=df.to_csv(index=False).encode()), \
             patch("app.services.model_training.AutoMLEngine.run",
                   new_callable=AsyncMock, return_value=result), \
             patch("app.services.model_storage.ModelStorageService.save_model",
                   new_callable=AsyncMock, return_value=MagicMock(model_id="m1")):
            for _ in range(2):
                await train_model_task(
                    dataset, TrainModelRequest(dataset_id="ds", target_column="target"),
                    TEST_USER, "m1",
                )

        assert len(await _events(FIRST_MODEL_TRAINED)) == 1

    async def test_erasure_sweeps_the_users_events(self, setup_database):
        from app.services.erasure_service import DatasetErasureService

        await product_events.record(TEST_USER, CHECKOUT_STARTED, tier="pro")
        await product_events.record("someone-else", CHECKOUT_STARTED, tier="pro")

        await DatasetErasureService().erase_user(TEST_USER)

        assert await _events(CHECKOUT_STARTED) == []
        assert len(await _events(CHECKOUT_STARTED, "someone-else")) == 1


class TestFunnel:
    async def _at(self, user_id: str, event: str, when: datetime, **props) -> None:
        await ProductEvent(user_id=user_id, event=event, timestamp=when, properties=props).insert()

    async def test_the_readout_counts_the_funnel(self, setup_database):
        now = datetime(2026, 9, 18, 12, tzinfo=UTC)
        day = timedelta(days=1)
        # Matured cohort (>= 7 days old): a activates inside 7 days, b too late, c never.
        await self._at("a", ACCOUNT_CREATED, now - 20 * day)
        await self._at("a", FIRST_MODEL_TRAINED, now - 15 * day)
        await self._at("b", ACCOUNT_CREATED, now - 20 * day)
        await self._at("b", FIRST_MODEL_TRAINED, now - 10 * day)
        await self._at("c", ACCOUNT_CREATED, now - 9 * day)
        # Too young to judge: counted as a signup, not in the cohort.
        await self._at("d", ACCOUNT_CREATED, now - 2 * day)
        # Outside the window entirely.
        await self._at("e", ACCOUNT_CREATED, now - 40 * day)
        await self._at("a", QUOTA_DENIED, now - day, metric="uploads", tier="free")
        await self._at("b", QUOTA_DENIED, now - day, metric="uploads", tier="free")
        await self._at("b", QUOTA_DENIED, now - day, metric="ai_calls", tier="free")
        await self._at("a", CHECKOUT_STARTED, now - day, tier="pro")
        await self._at("b", CHECKOUT_STARTED, now - day, tier="pro")
        await self._at("a", CHECKOUT_COMPLETED, now - day)
        await self._at("a", SUBSCRIPTION_CANCELLED, now - day)

        out = await funnel(days=30, now=now)

        assert out["signups"] == 4
        assert sum(d["count"] for d in out["signups_per_day"]) == 4
        assert {"date": "2026-08-29", "count": 2} in out["signups_per_day"]
        assert out["activation"] == {"cohort": 3, "activated": 1, "rate": pytest.approx(1 / 3)}
        assert out["quota_denials_by_metric"] == {"uploads": 2, "ai_calls": 1}
        assert out["checkout_started"] == 2
        assert out["checkout_completed"] == 1
        assert out["subscriptions_cancelled"] == 1

    async def test_a_short_window_still_judges_activation(self, setup_database):
        """The cohort is the same-length window ending 7 days ago, so ?days=7 is not
        structurally empty: nobody who signed up in the last 7 days can be judged yet."""
        now = datetime(2026, 9, 18, 12, tzinfo=UTC)
        day = timedelta(days=1)
        await self._at("a", ACCOUNT_CREATED, now - 10 * day)
        await self._at("a", FIRST_MODEL_TRAINED, now - 9 * day)
        await self._at("b", ACCOUNT_CREATED, now - 3 * day)
        await self._at("old", ACCOUNT_CREATED, now - 15 * day)  # before the cohort window
        await self._at("a", CHECKOUT_STARTED, now - 9 * day)  # in the look-back, not the window

        out = await funnel(days=7, now=now)

        assert out["signups"] == 1  # only b signed up in the last 7 days
        assert out["checkout_started"] == 0
        assert out["activation"] == {"cohort": 1, "activated": 1, "rate": 1.0}

    async def test_an_empty_window_reports_zeroes_not_errors(self, setup_database):
        out = await funnel(days=7)
        assert out["signups"] == 0
        assert out["activation"] == {"cohort": 0, "activated": 0, "rate": None}


class TestCounterExists:
    def test_quota_denials_are_exported(self):
        from prometheus_client import generate_latest

        from app.middleware.metrics import metrics_registry

        quota_denials.labels(metric="uploads", tier="free")
        assert b"quota_denials_total" in generate_latest(metrics_registry)

