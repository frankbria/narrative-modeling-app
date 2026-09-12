"""Caller-supplied training config is bounded server-side (#500).

Out-of-bounds values are rejected with a 422 that names the limit — never
clamped, since a clamped run trains a model the caller did not ask for. The
wall clock is a hard kill: a run that outlives its plan's ceiling is marked
FAILED with a clear reason instead of holding RUNNING forever.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.billing.plans import training_ceilings_for
from app.models.batch_job import JobStatus
from app.models.subscription import PlanTier
from app.models.training_job import TrainingJob

FREE = training_ceilings_for(PlanTier.FREE)


def _dataset():
    return MagicMock(id="dataset_123", user_id="test_user_123", file_type="csv")


async def _post(client, **config):
    body = {"dataset_id": "dataset_123", "target_column": "target", **config}
    with (
        patch("app.models.user_data.UserData.find_one", new_callable=AsyncMock) as find,
        patch("app.api.routes.model_training.train_model_task", new_callable=AsyncMock),
    ):
        find.return_value = _dataset()
        return await client.post("/api/v1/ml/train", json=body)


@pytest.mark.asyncio
class TestOverCeilingIs422:
    async def test_max_models_over_plan_ceiling_names_the_limit(self, async_authorized_client):
        resp = await _post(
            async_authorized_client, training_config={"max_models": FREE.max_models + 1}
        )
        assert resp.status_code == 422
        detail = str(resp.json()["detail"])
        assert "max_models" in detail and str(FREE.max_models) in detail

    async def test_tuning_trials_over_plan_ceiling(self, async_authorized_client):
        resp = await _post(
            async_authorized_client,
            training_config={
                "enable_tuning": True,
                "tuning_config": {"n_trials": FREE.tuning_trials + 1},
            },
        )
        assert resp.status_code == 422
        assert "n_trials" in str(resp.json()["detail"])

    async def test_time_limit_over_plan_ceiling(self, async_authorized_client):
        resp = await _post(
            async_authorized_client,
            training_config={"time_limit": FREE.time_limit_seconds + 1},
        )
        assert resp.status_code == 422
        assert "time_limit" in str(resp.json()["detail"])

    async def test_max_features_over_plan_ceiling(self, async_authorized_client):
        resp = await _post(
            async_authorized_client, feature_config={"max_features": FREE.max_features + 1}
        )
        assert resp.status_code == 422
        assert "max_features" in str(resp.json()["detail"])

    async def test_every_violation_is_reported_at_once(self, async_authorized_client):
        resp = await _post(
            async_authorized_client,
            training_config={
                "max_models": FREE.max_models + 1,
                "time_limit": FREE.time_limit_seconds + 1,
            },
        )
        assert resp.status_code == 422
        detail = str(resp.json()["detail"])
        assert "max_models" in detail and "time_limit" in detail


@pytest.mark.asyncio
class TestMalformedIs422:
    @pytest.mark.parametrize(
        "training_config",
        [
            {"max_models": 0},
            {"cv_folds": 1},
            {"test_size": 1.0},
            {"time_limit": -5},
            {"n_estimators": 100000},  # unknown knob: not a way in
            {"tuning_config": {"strategy": "exhaustive"}},
            {"tuning_config": {"n_jobs": 0}},
            {"tuning_config": {"n_jobs": 4096}},
            {"tuning_config": {"max_depth": 1000}},  # unknown knob under tuning
        ],
    )
    async def test_rejected_at_parse_time(self, async_authorized_client, training_config):
        resp = await _post(async_authorized_client, training_config=training_config)
        assert resp.status_code == 422, resp.text

    async def test_unknown_feature_knob_rejected(self, async_authorized_client):
        resp = await _post(async_authorized_client, feature_config={"n_components": 10**6})
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestWithinBoundsStillTrains:
    async def test_frontend_shaped_request_is_accepted(self, async_authorized_client):
        # Exactly what ModelTrainingButton / the model page send today.
        resp = await _post(
            async_authorized_client,
            training_config={"training_mode": "comprehensive", "cv_folds": 10, "max_models": 10, "test_size": 0.4},
            feature_config={"handle_missing": True, "max_features": 50},
        )
        assert resp.status_code == 200, resp.text
        await TrainingJob.find_one(TrainingJob.model_id == resp.json()["model_id"]).delete()

    async def test_at_the_ceiling_is_accepted(self, async_authorized_client):
        resp = await _post(
            async_authorized_client,
            training_config={
                "max_models": FREE.max_models,
                "time_limit": FREE.time_limit_seconds,
                "enable_tuning": True,
                "tuning_config": {"n_trials": FREE.tuning_trials, "time_budget": FREE.tuning_time_budget_seconds},
            },
        )
        assert resp.status_code == 200, resp.text
        await TrainingJob.find_one(TrainingJob.model_id == resp.json()["model_id"]).delete()


@pytest.mark.asyncio
class TestWallClock:
    async def test_run_past_wall_clock_is_marked_failed(self, setup_database):
        from app.api.routes.model_training import TrainModelRequest, train_model_task

        job = TrainingJob(
            model_id="model_wall_clock",
            user_id="test_user",
            dataset_id="dataset_123",
            target_column="target",
        )
        await job.insert()

        async def never_finishes(*_a, **_k):
            await asyncio.sleep(30)

        dataset = MagicMock(
            id="dataset_123", user_id="test_user", file_type="csv",
            s3_url="s3://test-bucket/uploads/test_user/test_data.csv",
        )
        try:
            with (
                patch(
                    "app.services.s3_service.S3Service.download_file_bytes",
                    new_callable=AsyncMock,
                    return_value=b"a,target\n1,0\n2,1\n",
                ),
                patch("app.api.routes.model_training.AutoMLEngine") as engine_cls,
            ):
                engine_cls.return_value.run = never_finishes
                await train_model_task(
                    dataset,
                    TrainModelRequest(dataset_id="dataset_123", target_column="target"),
                    "test_user",
                    "model_wall_clock",
                    wall_clock_seconds=0.05,
                )
            refreshed = await TrainingJob.find_one(TrainingJob.model_id == "model_wall_clock")
            assert refreshed.status == JobStatus.FAILED
            assert "wall-clock" in refreshed.error and "0.05" in refreshed.error
            assert any(e.level == "error" for e in refreshed.logs)
        finally:
            await job.delete()

    async def test_route_passes_the_tier_wall_clock(self, async_authorized_client):
        with (
            patch("app.models.user_data.UserData.find_one", new_callable=AsyncMock) as find,
            patch("app.api.routes.model_training.train_model_task", new_callable=AsyncMock) as task,
        ):
            find.return_value = _dataset()
            resp = await async_authorized_client.post(
                "/api/v1/ml/train", json={"dataset_id": "dataset_123", "target_column": "target"}
            )
        assert resp.status_code == 200
        assert task.call_args.kwargs["wall_clock_seconds"] == FREE.wall_clock_seconds
        await TrainingJob.find_one(TrainingJob.model_id == resp.json()["model_id"]).delete()
