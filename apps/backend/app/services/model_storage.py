"""
Model storage service for saving and loading ML models
"""

import asyncio
import io
import json
import logging
import math
import os
import threading
import time
import uuid
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

import joblib
import numpy as np

from app.models.ml_model import MLModel
from app.services.model_training.automl_engine import ModelCandidate
from app.services.model_training.feature_engineer import FeatureEngineer
from app.services.model_versioning_service import (
    capture_environment,
    model_versioning_service,
)
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)

# Model-artifact cache config (issue #265). Bounds memory: entries hold a whole
# deserialized estimator + feature transformer, so keep the count small.
_CACHE_MAX_SIZE = int(os.getenv("MODEL_CACHE_MAX_SIZE", "8"))
_CACHE_TTL_SECONDS = float(os.getenv("MODEL_CACHE_TTL_SECONDS", "900"))


class _ModelArtifactCache:
    """Bounded TTL-LRU of ``(estimator, feature_engineer)`` by ``(model_id, user_id)``.

    Kills the per-prediction S3 download + ``joblib.load`` that dominated serving
    latency (issue #265). Disabled when ``max_size`` or ``ttl`` is non-positive.

    ponytail: single lock over an ``OrderedDict`` — ample for beta request rates
    on one process; swap for Redis if serving ever fans out across workers.
    """

    def __init__(self, max_size: int, ttl: float):
        self._max = max_size
        self._ttl = ttl
        self._data: OrderedDict[tuple[str, str], tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: tuple[str, str]) -> Any | None:
        if self._max <= 0 or self._ttl <= 0:
            return None
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() >= expires_at:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def put(self, key: tuple[str, str], value: Any) -> None:
        if self._max <= 0 or self._ttl <= 0:
            return
        with self._lock:
            self._data[key] = (time.monotonic() + self._ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def invalidate(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_model_cache = _ModelArtifactCache(_CACHE_MAX_SIZE, _CACHE_TTL_SECONDS)

# Per-model inference locks (issue #265). The artifact cache hands out ONE shared
# estimator per (model_id, user_id); some boosters (LightGBM / older XGBoost) are
# not safe for concurrent ``predict`` from multiple ``asyncio.to_thread`` worker
# threads, so serving serializes inference per model. Different models still run in
# parallel. ponytail: locks are tiny and never evicted — negligible at beta model
# counts; bound this map if the served-model population ever explodes.
_inference_locks: dict[tuple[str, str], threading.Lock] = {}
_inference_locks_guard = threading.Lock()


def invalidate_model_cache(model_id: str, user_id: str) -> None:
    """Evict a model's cached artifacts (on retrain/delete/deploy — issue #265)."""
    _model_cache.invalidate((model_id, user_id))


def get_inference_lock(model_id: str, user_id: str) -> threading.Lock:
    """Return the per-model lock that serializes inference on the shared estimator.

    Serving loads one cached estimator per ``(model_id, user_id)`` and runs
    ``predict``/``predict_proba`` off the event loop via ``asyncio.to_thread``;
    holding this lock around those calls prevents concurrent worker threads from
    racing inside a non-thread-safe booster (issue #265).
    """
    key = (model_id, user_id)
    with _inference_locks_guard:
        lock = _inference_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _inference_locks[key] = lock
        return lock


def _to_json_safe(value: Any) -> Any:
    """Recursively convert numpy types to JSON-safe Python builtins.

    Non-finite floats (NaN/inf) become ``None`` so the output is always
    strictly valid JSON (``json.dumps(..., allow_nan=False)`` safe).
    """
    if value is None:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        as_float = float(value)
        return as_float if math.isfinite(as_float) else None
    if isinstance(value, np.ndarray):
        return [_to_json_safe(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_json_safe(val) for key, val in value.items()}
    return str(value) if not isinstance(value, str) else value


def build_evaluation_payload(
    problem_type: str,
    y_test: Any,
    y_pred: Any,
    y_proba: Any | None,
    class_labels: list[str] | None,
    x_test: Any | None = None,
    feature_names: list[str] | None = None,
) -> dict[str, Any]:
    """Build the JSON-safe evaluation-artifact payload persisted to S3.

    Arrays may be numpy arrays, pandas Series, or plain lists; all values are
    converted to JSON-safe builtins (issue #79).

    ``x_test`` (the held-out transformed feature matrix) + ``feature_names`` are
    persisted for error analysis (issue #81); both are optional, so pre-#81
    models simply lack them and the error-analysis endpoint degrades to
    ``partial`` (no segments/clusters/patterns).
    ponytail: full held-out X persisted; sample it if held-out sets ever grow
    large enough to bloat the JSON.
    """
    payload = {
        "problem_type": problem_type,
        "y_test": _to_json_safe(np.asarray(y_test)),
        "y_pred": _to_json_safe(np.asarray(y_pred)),
        "y_proba": _to_json_safe(np.asarray(y_proba)) if y_proba is not None else None,
        "class_labels": (
            [str(label) for label in class_labels] if class_labels is not None else None
        ),
        "created_at": datetime.now(UTC).isoformat(),
    }
    if x_test is not None and feature_names:
        payload["X_test"] = _to_json_safe(np.asarray(x_test))
        payload["feature_names"] = [str(name) for name in feature_names]
    return payload


def build_shap_payload(shap_global: Any) -> dict[str, Any] | None:
    """Build the JSON-safe global-SHAP summary payload persisted to S3 (#80).

    ``shap_global`` is a ``GlobalShapResult`` (from ``InterpretabilityService``)
    or ``None`` — returns ``None`` for unsupported model types so the caller
    skips the upload and leaves ``shap_values_path`` unset.
    """
    if shap_global is None:
        return None
    return {
        "explainer_type": shap_global.explainer_type,
        "shap_importance": _to_json_safe(shap_global.shap_importance),
        "base_value": _to_json_safe(shap_global.base_value),
        "n_samples": int(shap_global.n_samples),
        "created_at": datetime.now(UTC).isoformat(),
    }


class ModelStorageService:
    """Service for storing and retrieving ML models"""
    
    def __init__(self):
        self.s3_service = S3Service()
        self.models_prefix = "models/"
    
    async def save_model(
        self,
        model_candidate: ModelCandidate,
        feature_engineer: FeatureEngineer,
        user_id: str,
        dataset_id: str,
        model_metadata: dict,
        model_id: str | None = None,
        evaluation_data: dict[str, Any] | None = None,
        shap_data: dict[str, Any] | None = None,
    ) -> MLModel:
        """
        Save a trained model and its metadata

        Args:
            model_candidate: Trained model candidate
            feature_engineer: Feature engineer with transformers
            user_id: User who trained the model
            dataset_id: Dataset used for training
            model_metadata: Additional metadata
            model_id: Optional pre-generated model ID (if None, generates new one)
            evaluation_data: Optional JSON-safe evaluation-artifact payload
                (see ``build_evaluation_payload``). Uploaded best-effort: a
                failure is logged and never fails the save (issue #79).
            shap_data: Optional JSON-safe global-SHAP summary payload (see
                ``build_shap_payload``). Uploaded best-effort like
                ``evaluation_data`` (issue #80).

        Returns:
            MLModel document
        """
        # Use provided model ID or generate unique one
        if model_id is None:
            model_id = f"model_{uuid.uuid4().hex[:12]}"
        
        # Serialize model
        model_buffer = io.BytesIO()
        joblib.dump(model_candidate.estimator, model_buffer)
        model_buffer.seek(0)
        model_size = model_buffer.getbuffer().nbytes
        
        # Upload model to S3
        model_key = f"{self.models_prefix}{user_id}/{model_id}/model.pkl"
        await self.s3_service.upload_file_obj(model_buffer, model_key)
        
        # Serialize feature engineer if it has transformers
        feature_transformer_path = None
        if feature_engineer.transformers:
            transformer_buffer = io.BytesIO()
            joblib.dump(feature_engineer, transformer_buffer)
            transformer_buffer.seek(0)
            
            transformer_key = f"{self.models_prefix}{user_id}/{model_id}/feature_transformer.pkl"
            await self.s3_service.upload_file_obj(transformer_buffer, transformer_key)
            feature_transformer_path = f"s3://{self.s3_service.bucket_name}/{transformer_key}"

        # Upload evaluation artifacts (best-effort — issue #79). A failure
        # here must never fail the training job; the evaluation endpoint
        # degrades to partial results when the path is absent.
        evaluation_data_path = None
        if evaluation_data is not None:
            evaluation_key = (
                f"{self.models_prefix}{user_id}/{model_id}/evaluation_data.json"
            )
            try:
                evaluation_buffer = io.BytesIO(
                    json.dumps(evaluation_data, allow_nan=False).encode("utf-8")
                )
                await self.s3_service.upload_file_obj(evaluation_buffer, evaluation_key)
                evaluation_data_path = (
                    f"s3://{self.s3_service.bucket_name}/{evaluation_key}"
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to upload evaluation artifacts for {model_id}: {exc}"
                )

        # Upload the global SHAP summary (best-effort — issue #80). Mirrors the
        # evaluation-artifact path: a failure here must never fail training; the
        # interpretability endpoint reports SHAP as unavailable when absent.
        shap_values_path = None
        if shap_data is not None:
            shap_key = f"{self.models_prefix}{user_id}/{model_id}/shap_data.json"
            try:
                shap_buffer = io.BytesIO(
                    json.dumps(shap_data, allow_nan=False).encode("utf-8")
                )
                await self.s3_service.upload_file_obj(shap_buffer, shap_key)
                shap_values_path = f"s3://{self.s3_service.bucket_name}/{shap_key}"
            except Exception as exc:
                logger.warning(
                    f"Failed to upload SHAP summary for {model_id}: {exc}"
                )

        # Version lineage (issue #78): chain this run onto the previous version
        # in its family (same user/dataset/name) and capture the runtime
        # environment for reproducibility. Best-effort — never fail the save.
        model_name = model_metadata.get("name", f"{model_candidate.name} Model")
        try:
            parent_model_id = await model_versioning_service.resolve_parent(
                user_id, dataset_id, model_name
            )
        except Exception as exc:
            logger.warning(f"Failed to resolve parent version for {model_id}: {exc}")
            parent_model_id = None

        # Link the dataset version this model was trained on (issue #78 AC1).
        # Prefer an explicit id from the caller; otherwise best-effort resolve the
        # latest DatasetVersion for the dataset so the lineage column is populated
        # whenever the dataset-versioning system has tracked it.
        dataset_version_id = model_metadata.get("dataset_version_id")
        if dataset_version_id is None:
            try:
                from app.models.version import DatasetVersion

                latest = (
                    await DatasetVersion.find(
                        DatasetVersion.dataset_id == dataset_id,
                        DatasetVersion.user_id == user_id,
                    )
                    .sort("-version_number")
                    .first_or_none()
                )
                if latest is not None:
                    dataset_version_id = latest.version_id
            except Exception as exc:
                logger.warning(
                    f"Failed to resolve dataset version for {model_id}: {exc}"
                )

        # Create model document
        ml_model = MLModel(
            user_id=user_id,
            dataset_id=dataset_id,
            model_id=model_id,
            name=model_name,
            description=model_metadata.get("description"),
            problem_type=model_metadata["problem_type"],
            algorithm=model_candidate.name,
            target_column=model_metadata["target_column"],
            feature_names=model_metadata["feature_names"],
            cv_score=model_candidate.cv_score,
            test_score=model_candidate.test_score,
            metrics=model_metadata.get("metrics", {}),
            training_time=model_candidate.training_time,
            model_size=model_size,
            n_samples_train=model_metadata["n_samples_train"],
            n_features=len(model_metadata["feature_names"]),
            model_path=f"s3://{self.s3_service.bucket_name}/{model_key}",
            feature_transformer_path=feature_transformer_path,
            evaluation_data_path=evaluation_data_path,
            feature_importance=model_metadata.get("feature_importance"),
            # SHAP interpretability (issue #80).
            shap_values_path=shap_values_path,
            shap_explainer_type=model_metadata.get("shap_explainer_type"),
            # Confidence/uncertainty metadata (issue #83).
            is_calibrated=model_metadata.get("is_calibrated", False),
            calibration_method=model_metadata.get("calibration_method"),
            calibration_score=model_metadata.get("calibration_score"),
            # Honesty flags (issue #201).
            calibration_score_is_insample=model_metadata.get(
                "calibration_score_is_insample", True
            ),
            evaluation_on_calibration_set=model_metadata.get(
                "evaluation_on_calibration_set", False
            ),
            residual_std=model_metadata.get("residual_std"),
            # Hyperparameter tuning (issue #77).
            tuning_strategy=model_metadata.get("tuning_strategy"),
            tuning_time=model_metadata.get("tuning_time"),
            improvement_from_tuning=model_metadata.get("improvement_from_tuning"),
            tuning_results=model_metadata.get("tuning_results"),
            # Versioning & lineage (issue #78).
            parent_model_id=parent_model_id,
            dataset_version_id=dataset_version_id,
            version_notes=model_metadata.get("version_notes"),
            environment_metadata=capture_environment(),
            training_config=model_metadata.get("training_config", {})
        )
        
        # Save to database
        await ml_model.insert()

        # Evict any stale cache entry for this id (defensive; retrain — issue #265).
        _model_cache.invalidate((model_id, user_id))

        logger.info(f"Saved model {model_id} for user {user_id}")
        return ml_model
    
    async def load_model(self, model_id: str, user_id: str) -> tuple[Any, FeatureEngineer | None]:
        """
        Load a model and its feature transformer
        
        Args:
            model_id: Model ID to load
            user_id: User ID for authorization
            
        Returns:
            Tuple of (model, feature_engineer)
        """
        # Serve hot artifacts from the cache: the key encodes user_id, so a hit is
        # already ownership-scoped and needs no S3/Mongo round trip (issue #265).
        cache_key = (model_id, user_id)
        cached = _model_cache.get(cache_key)
        if cached is not None:
            return cached

        # Get model metadata
        ml_model = await MLModel.find_one(
            MLModel.model_id == model_id,
            MLModel.user_id == user_id
        )

        if not ml_model:
            raise ValueError(f"Model {model_id} not found for user {user_id}")

        # Extract S3 key from path
        model_key = ml_model.model_path.replace(f"s3://{self.s3_service.bucket_name}/", "")

        # Download model. joblib.load unpickles CPU-bound → run it off the loop.
        model_data = await self.s3_service.download_file_obj(model_key)
        model = await asyncio.to_thread(joblib.load, io.BytesIO(model_data))

        # Load feature transformer if exists
        feature_engineer = None
        if ml_model.feature_transformer_path:
            transformer_key = ml_model.feature_transformer_path.replace(
                f"s3://{self.s3_service.bucket_name}/", ""
            )
            transformer_data = await self.s3_service.download_file_obj(transformer_key)
            feature_engineer = await asyncio.to_thread(
                joblib.load, io.BytesIO(transformer_data)
            )

        # Update last used timestamp. ponytail: only stamped on a cache miss —
        # the production serving path also updates it per-prediction via the
        # monitoring service, so the hot path stays free of a DB write.
        ml_model.last_used_at = datetime.now(UTC)
        await ml_model.save()

        result = (model, feature_engineer)
        _model_cache.put(cache_key, result)
        return result
    
    async def delete_model(self, model_id: str, user_id: str) -> bool:
        """
        Delete a model and its files
        
        Args:
            model_id: Model ID to delete
            user_id: User ID for authorization
            
        Returns:
            True if deleted successfully
        """
        # Get model metadata
        ml_model = await MLModel.find_one(
            MLModel.model_id == model_id,
            MLModel.user_id == user_id
        )
        
        if not ml_model:
            return False
        
        # Delete S3 files
        try:
            # Delete model file
            model_key = ml_model.model_path.replace(f"s3://{self.s3_service.bucket_name}/", "")
            await self.s3_service.delete_file(model_key)
            
            # Delete transformer file if exists
            if ml_model.feature_transformer_path:
                transformer_key = ml_model.feature_transformer_path.replace(
                    f"s3://{self.s3_service.bucket_name}/", ""
                )
                await self.s3_service.delete_file(transformer_key)

            # Delete evaluation artifacts if present (issue #79)
            if ml_model.evaluation_data_path:
                evaluation_key = ml_model.evaluation_data_path.replace(
                    f"s3://{self.s3_service.bucket_name}/", ""
                )
                await self.s3_service.delete_file(evaluation_key)

            # Delete SHAP summary if present (issue #80)
            shap_values_path = getattr(ml_model, "shap_values_path", None)
            if shap_values_path:
                shap_key = shap_values_path.replace(
                    f"s3://{self.s3_service.bucket_name}/", ""
                )
                await self.s3_service.delete_file(shap_key)
        except Exception as e:
            logger.error(f"Error deleting model files: {str(e)}")
        
        # Delete from database
        await ml_model.delete()

        # Drop cached artifacts so a re-created id can't serve the old model (#265).
        _model_cache.invalidate((model_id, user_id))

        logger.info(f"Deleted model {model_id} for user {user_id}")
        return True
    
    async def list_models(
        self,
        user_id: str,
        dataset_id: str | None = None,
        is_active: bool = True
    ) -> list[MLModel]:
        """
        List models for a user
        
        Args:
            user_id: User ID
            dataset_id: Optional dataset filter
            is_active: Filter by active status
            
        Returns:
            List of MLModel documents
        """
        query = {"user_id": user_id, "is_active": is_active}
        if dataset_id:
            query["dataset_id"] = dataset_id
        
        models = await MLModel.find(query).sort("-created_at").to_list()
        return models