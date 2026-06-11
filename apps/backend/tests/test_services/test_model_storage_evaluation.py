"""Tests for evaluation-artifact persistence in ModelStorageService (issue #79).

The training task serializes the best model's held-out arrays to
``models/{user_id}/{model_id}/evaluation_data.json``; the upload is
best-effort and must never fail the training job.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from app.models.ml_model import MLModel
from app.services.model_storage import ModelStorageService, build_evaluation_payload
from app.services.model_training.automl_engine import ModelCandidate
from app.services.model_training.feature_engineer import FeatureEngineer

pytestmark = [pytest.mark.usefixtures("beanie_models_initialized")]


class TestBuildEvaluationPayload:
    """The JSON payload builder produces JSON-safe output."""

    @pytest.mark.unit
    def test_classification_payload_is_json_safe(self):
        payload = build_evaluation_payload(
            problem_type="binary_classification",
            y_test=np.array(["yes", "no", "yes"]),
            y_pred=np.array(["yes", "yes", "yes"]),
            y_proba=np.array([[0.2, 0.8], [0.6, 0.4], [0.1, 0.9]]),
            class_labels=["no", "yes"],
        )

        # Strict JSON: no NaN/Infinity, no numpy scalar types
        serialized = json.dumps(payload, allow_nan=False)
        round_tripped = json.loads(serialized)

        assert round_tripped["problem_type"] == "binary_classification"
        assert round_tripped["y_test"] == ["yes", "no", "yes"]
        assert round_tripped["y_pred"] == ["yes", "yes", "yes"]
        assert round_tripped["y_proba"] == [[0.2, 0.8], [0.6, 0.4], [0.1, 0.9]]
        assert round_tripped["class_labels"] == ["no", "yes"]
        assert isinstance(round_tripped["created_at"], str)

    @pytest.mark.unit
    def test_numpy_scalars_and_non_finite_values(self):
        payload = build_evaluation_payload(
            problem_type="regression",
            y_test=np.array([np.float64(1.5), np.nan, np.inf]),
            y_pred=np.array([np.int64(2), np.int64(3), np.int64(4)]),
            y_proba=None,
            class_labels=None,
        )

        serialized = json.dumps(payload, allow_nan=False)
        round_tripped = json.loads(serialized)

        assert round_tripped["y_test"] == [1.5, None, None]
        assert round_tripped["y_pred"] == [2, 3, 4]
        assert round_tripped["y_proba"] is None
        assert round_tripped["class_labels"] is None

    @pytest.mark.unit
    def test_numpy_bool_labels(self):
        payload = build_evaluation_payload(
            problem_type="binary_classification",
            y_test=np.array([True, False]),
            y_pred=np.array([False, False]),
            y_proba=None,
            class_labels=["False", "True"],
        )
        round_tripped = json.loads(json.dumps(payload, allow_nan=False))
        assert round_tripped["y_test"] == [True, False]


def _trained_candidate() -> ModelCandidate:
    rng = np.random.RandomState(0)
    X = rng.randn(30, 3)
    y = rng.choice([0, 1], 30)
    estimator = LogisticRegression().fit(X, y)
    return ModelCandidate(
        name="Logistic Regression",
        estimator=estimator,
        hyperparameters={},
        training_time=1.0,
        cv_score=0.8,
        test_score=0.75,
    )


def _metadata() -> dict:
    return {
        "name": "Test Model",
        "problem_type": "binary_classification",
        "target_column": "target",
        "feature_names": ["f1", "f2", "f3"],
        "n_samples_train": 30,
        "metrics": {"cv_score": 0.8, "test_score": 0.75},
    }


def _mock_storage() -> ModelStorageService:
    storage = ModelStorageService()
    storage.s3_service = MagicMock()
    storage.s3_service.bucket_name = "test-bucket"
    storage.s3_service.upload_file_obj = AsyncMock(
        side_effect=lambda obj, key: f"s3://test-bucket/{key}"
    )
    return storage


class TestSaveModelEvaluationData:
    """save_model uploads evaluation_data.json and records its path."""

    @pytest.mark.asyncio
    async def test_uploads_evaluation_data_and_sets_path(self):
        storage = _mock_storage()
        payload = build_evaluation_payload(
            problem_type="binary_classification",
            y_test=np.array([0, 1]),
            y_pred=np.array([0, 0]),
            y_proba=np.array([[0.7, 0.3], [0.6, 0.4]]),
            class_labels=["0", "1"],
        )

        ml_model = await storage.save_model(
            _trained_candidate(),
            FeatureEngineer(),
            user_id="user_1",
            dataset_id="ds_1",
            model_metadata=_metadata(),
            model_id="model_abc",
            evaluation_data=payload,
        )

        expected_key = "models/user_1/model_abc/evaluation_data.json"
        uploaded_keys = [
            call.args[1] for call in storage.s3_service.upload_file_obj.call_args_list
        ]
        assert expected_key in uploaded_keys
        assert ml_model.evaluation_data_path == f"s3://test-bucket/{expected_key}"

        # The uploaded body must be valid JSON matching the payload
        eval_call = next(
            call
            for call in storage.s3_service.upload_file_obj.call_args_list
            if call.args[1] == expected_key
        )
        body = eval_call.args[0].read()
        assert json.loads(body) == payload

        await ml_model.delete()

    @pytest.mark.asyncio
    async def test_no_evaluation_data_keeps_path_none(self):
        storage = _mock_storage()
        ml_model = await storage.save_model(
            _trained_candidate(),
            FeatureEngineer(),
            user_id="user_1",
            dataset_id="ds_1",
            model_metadata=_metadata(),
            model_id="model_no_eval",
        )

        assert ml_model.evaluation_data_path is None
        uploaded_keys = [
            call.args[1] for call in storage.s3_service.upload_file_obj.call_args_list
        ]
        assert not any(key.endswith("evaluation_data.json") for key in uploaded_keys)

        await ml_model.delete()

    @pytest.mark.asyncio
    async def test_evaluation_upload_failure_does_not_fail_save(self):
        storage = _mock_storage()

        async def upload(obj, key):
            if key.endswith("evaluation_data.json"):
                raise RuntimeError("S3 unavailable")
            return f"s3://test-bucket/{key}"

        storage.s3_service.upload_file_obj = AsyncMock(side_effect=upload)

        ml_model = await storage.save_model(
            _trained_candidate(),
            FeatureEngineer(),
            user_id="user_1",
            dataset_id="ds_1",
            model_metadata=_metadata(),
            model_id="model_eval_fail",
            evaluation_data={"problem_type": "binary_classification"},
        )

        # Model is saved; the evaluation path is simply absent
        assert ml_model.model_id == "model_eval_fail"
        assert ml_model.evaluation_data_path is None

        await ml_model.delete()


class TestMLModelBackwardCompatibility:
    @pytest.mark.unit
    def test_old_documents_without_evaluation_path_validate(self):
        """Pre-#79 documents lack evaluation_data_path entirely."""
        model = MLModel(
            user_id="u",
            dataset_id="d",
            model_id="m",
            name="n",
            problem_type="regression",
            algorithm="Ridge",
            target_column="t",
            feature_names=["a"],
            cv_score=0.5,
            test_score=0.5,
            training_time=1.0,
            model_size=10,
            n_samples_train=10,
            n_features=1,
            model_path="s3://b/k",
        )
        assert model.evaluation_data_path is None
