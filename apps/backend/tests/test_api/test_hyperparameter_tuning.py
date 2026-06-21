"""
API tests for hyperparameter tuning (issue #77): the train-task config plumbing
and the GET /{model_id}/tuning-results endpoint.
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.services.model_training.automl_engine import (
    AutoMLResult,
    ModelCandidate,
)
from app.services.model_training.problem_detector import ProblemType


def _tuned_model_mock():
    model = MagicMock()
    model.model_id = "model_123"
    model.user_id = "test_user"
    model.tuning_strategy = "bayesian"
    model.improvement_from_tuning = 0.042
    model.tuning_results = {
        "Random Forest": {
            "algorithm": "Random Forest",
            "strategy": "bayesian",
            "best_params": {"n_estimators": 220},
            "best_score": 0.91,
            "default_score": 0.87,
            "improvement_over_default": 0.04,
            "parameter_importance": {"n_estimators": 0.6},
            "optimization_history": [{"trial": 0, "score": 0.87, "best_so_far": 0.87}],
            "all_trials": [],
        }
    }
    return model


@pytest.mark.asyncio
class TestTuningResultsEndpoint:
    async def test_partial_for_untuned_model(self, async_authorized_client):
        model = MagicMock()
        model.model_id = "model_123"
        model.tuning_results = None
        model.tuning_strategy = None
        model.improvement_from_tuning = None
        with patch(
            "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
        ) as find_one:
            find_one.return_value = model
            resp = await async_authorized_client.get(
                "/api/v1/ml/model_123/tuning-results"
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is True
        assert body["results"] == {}
        assert "not run" in body["message"]

    async def test_populated_for_tuned_model(self, async_authorized_client):
        with patch(
            "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
        ) as find_one:
            find_one.return_value = _tuned_model_mock()
            resp = await async_authorized_client.get(
                "/api/v1/ml/model_123/tuning-results"
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        assert body["tuning_strategy"] == "bayesian"
        assert body["improvement_from_tuning"] == pytest.approx(0.042)
        rf = body["results"]["Random Forest"]
        assert rf["best_params"] == {"n_estimators": 220}
        assert rf["parameter_importance"] == {"n_estimators": 0.6}
        assert rf["optimization_history"]

    async def test_not_found(self, async_authorized_client):
        with patch(
            "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
        ) as find_one:
            find_one.return_value = None
            resp = await async_authorized_client.get(
                "/api/v1/ml/missing/tuning-results"
            )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestTrainTaskTuningWiring:
    async def test_training_config_builds_tuning_engine(self):
        """enable_tuning in training_config is plumbed into AutoMLEngine + persisted."""
        from app.api.routes.model_training import TrainModelRequest, train_model_task

        sample_dataset = MagicMock()
        sample_dataset.id = "dataset_123"
        sample_dataset.user_id = "test_user"
        sample_dataset.filename = "test.csv"
        sample_dataset.file_type = "csv"
        sample_dataset.s3_url = "s3://test-bucket/uploads/test_user/test.csv"

        df = pd.DataFrame(
            {
                "f1": np.random.randn(100),
                "f2": np.random.randn(100),
                "target": np.random.choice([0, 1], 100),
            }
        )

        result = AutoMLResult(
            best_model=ModelCandidate(
                name="Random Forest",
                estimator=MagicMock(),
                hyperparameters={},
                cv_score=0.9,
                test_score=0.88,
                training_time=5.0,
            ),
            all_models=[],
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            feature_names=["f1", "f2"],
            feature_importance=None,
            training_time=12.0,
            metadata={},
            tuning_results={"Random Forest": {"improvement_over_default": 0.03}},
            tuning_strategy="bayesian",
            improvement_from_tuning=0.03,
        )

        csv = io.BytesIO()
        df.to_csv(csv, index=False)

        with patch(
            "app.api.routes.model_training.get_file_from_s3",
            new_callable=AsyncMock,
            return_value=csv.getvalue(),
        ), patch(
            "app.api.routes.model_training.AutoMLEngine"
        ) as EngineCls, patch(
            "app.models.training_job.TrainingJob.find_one",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.services.model_storage.ModelStorageService.save_model",
            new_callable=AsyncMock,
            return_value=MagicMock(model_id="model_123"),
        ):
            EngineCls.return_value.run = AsyncMock(return_value=result)
            request = TrainModelRequest(
                dataset_id="dataset_123",
                target_column="target",
                name="Tuned",
                training_config={
                    "enable_tuning": True,
                    "tuning_strategy": "bayesian",
                    "tuning_config": {"n_trials": 10},
                },
            )
            await train_model_task(sample_dataset, request, "test_user", "model_123")

        # Engine constructed with tuning enabled and a TuningConfig.
        _, kwargs = EngineCls.call_args
        assert kwargs["enable_tuning"] is True
        assert kwargs["tuning_config"] is not None
        assert kwargs["tuning_config"].strategy == "bayesian"
        assert kwargs["tuning_config"].n_trials == 10
