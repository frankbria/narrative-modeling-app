"""
Batch prediction service for processing large datasets
"""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import socket
import statistics
import tempfile
from collections.abc import AsyncGenerator
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any
from urllib.parse import urlparse

import httpx
import numpy as np
import pandas as pd
from beanie import PydanticObjectId

from app.models.batch_job import BatchJob, BatchPredictionConfig, JobStatus, JobType
from app.models.ml_model import MLModel
from app.services.confidence_service import ConfidenceService
from app.services.interpretability_service import InterpretabilityService
from app.services.model_storage import ModelStorageService
from app.services.prediction_explainer_service import PredictionExplainerService
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)


class BatchPredictionService:
    """Service for managing batch prediction jobs"""

    def __init__(self) -> None:
        self.s3_service = S3Service()
        self.model_storage = ModelStorageService()
        # Confidence / explanation helpers (issue #83 + #80). Share one
        # InterpretabilityService so chunk-level batched SHAP and the explainer
        # reuse a single instance.
        self.confidence = ConfidenceService()
        self.interpretability = InterpretabilityService()
        self.explainer = PredictionExplainerService(self.interpretability)
        # Hold strong references to background tasks: asyncio only keeps a weak
        # reference, so an un-retained task can be garbage-collected mid-run.
        self._background_tasks: set = set()

    def _spawn_processing(self, job: BatchJob) -> None:
        """Schedule background processing, retaining a reference and observing
        the task's outcome so a failure can never be silently lost (#82)."""
        task = asyncio.create_task(self._process_batch_job(job))
        self._background_tasks.add(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: "asyncio.Task") -> None:
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("Unhandled exception in batch job task", exc_info=exc)

    async def create_batch_prediction_job(
        self,
        user_id: str,
        model_id: str,
        input_data: Any,  # Can be file path, DataFrame, or list of dicts
        output_format: str = "csv",
        include_probabilities: bool = True,
        include_metadata: bool = False,
        include_explanations: bool = False,
        chunk_size: int = 1000,
        priority: int = 0,
        auto_start: bool = True,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> BatchJob:
        """Create a new batch prediction job.

        When ``auto_start`` is True (the default, used by the API route) the job
        is processed in a background task. Tests pass ``auto_start=False`` and
        await :meth:`_process_batch_job` directly for deterministic behaviour.
        """

        # Validate model exists and user has access
        model = await MLModel.find_one(
            {"model_id": model_id, "user_id": user_id, "is_active": True}
        )

        if not model:
            raise ValueError("Model not found or not accessible")

        # Prepare input data and upload to S3 if needed
        input_path, total_records = await self._prepare_input_data(
            input_data, user_id, model_id
        )

        # Create job configuration
        config = BatchPredictionConfig(
            model_id=model_id,
            output_format=output_format,
            include_probabilities=include_probabilities,
            include_metadata=include_metadata,
            include_explanations=include_explanations,
            chunk_size=chunk_size,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        ).dict()

        # Create job
        job = BatchJob(
            job_id=f"batch_{PydanticObjectId()}",
            job_type=JobType.BATCH_PREDICTION,
            user_id=user_id,
            config=config,
            input_path=input_path,
            priority=priority,
        )

        # Initialize progress
        job.progress.total_records = total_records
        job.progress.total_chunks = (total_records + chunk_size - 1) // chunk_size

        await job.create()

        # Start processing asynchronously
        if auto_start:
            self._spawn_processing(job)

        return job

    async def _prepare_input_data(
        self, input_data: Any, user_id: str, model_id: str
    ) -> tuple[str, int]:
        """Prepare and upload input data to S3"""

        # Generate unique S3 path
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        s3_key = f"batch-jobs/{user_id}/{model_id}/{timestamp}/input.csv"

        if isinstance(input_data, str):
            # Assume it's a file path
            if not os.path.exists(input_data):
                raise ValueError("Input file not found")

            # Count records
            df = pd.read_csv(input_data)
            total_records = len(df)

            # Upload to S3
            with open(input_data, "rb") as fh:
                await self.s3_service.upload_file_obj(fh, s3_key)

        elif isinstance(input_data, pd.DataFrame):
            # Convert DataFrame to CSV and upload
            csv_buffer = StringIO()
            input_data.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue().encode("utf-8")

            total_records = len(input_data)

            # Upload to S3
            await self.s3_service.upload_file_obj(BytesIO(csv_content), s3_key)

        elif isinstance(input_data, list):
            # Convert list to DataFrame then CSV
            df = pd.DataFrame(input_data)
            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue().encode("utf-8")

            total_records = len(input_data)

            # Upload to S3
            await self.s3_service.upload_file_obj(BytesIO(csv_content), s3_key)

        else:
            raise ValueError("Unsupported input data type")

        return s3_key, total_records

    async def _process_batch_job(self, job: BatchJob) -> None:
        """Process a batch prediction job asynchronously"""

        try:
            # Mark job as started
            job.mark_started()
            await job.save()

            # Load model
            config = BatchPredictionConfig(**job.config)
            model = await MLModel.find_one(
                {
                    "model_id": config.model_id,
                    "user_id": job.user_id,
                }
            )

            if not model:
                raise ValueError("Model not found")

            if not job.input_path:
                raise ValueError("Batch job has no input path")

            # Load model artifacts. load_model returns a (model, feature_engineer)
            # tuple keyed by (model_id, user_id) — issue #82 bugfix.
            trained_model, feature_engineer = await self.model_storage.load_model(
                config.model_id, job.user_id
            )

            # Process data in chunks
            predictions: list[dict[str, Any]] = []
            chunk_num = 0
            total_success = 0
            total_error = 0

            async for chunk_df in self._read_data_chunks(
                job.input_path, config.chunk_size
            ):
                chunk_num += 1

                try:
                    # Make predictions for chunk
                    chunk_predictions = await self._predict_chunk(
                        chunk_df, trained_model, feature_engineer, model, config
                    )

                    predictions.extend(chunk_predictions)
                    total_success += len(
                        [p for p in chunk_predictions if p.get("error") is None]
                    )
                    total_error += len(
                        [p for p in chunk_predictions if p.get("error") is not None]
                    )

                except Exception as e:
                    # Handle chunk processing error
                    error_predictions = [
                        {"error": str(e), "row_index": i} for i in range(len(chunk_df))
                    ]
                    predictions.extend(error_predictions)
                    total_error += len(error_predictions)

                # Update cumulative progress after each chunk
                job.update_progress(
                    processed_records=len(predictions),
                    success_count=total_success,
                    error_count=total_error,
                    current_chunk=chunk_num,
                )
                await job.save()

            # Save results to S3
            output_path = await self._save_results(job, predictions, config)
            job.output_path = output_path

            # Mark job as completed with summary statistics
            summary = self._calculate_summary_statistics(predictions, model)
            summary["output_path"] = output_path
            job.mark_completed(summary)

        except Exception as e:
            job.mark_failed(str(e))

        finally:
            await job.save()
            # Best-effort async-completion webhook (issue #86). Never blocks/raises.
            await self._fire_webhook(job)

    @staticmethod
    async def _is_safe_webhook_url(url: str) -> bool:
        """Reject SSRF-prone webhook targets (#86 hardening).

        Only http(s) to a host that resolves entirely to public addresses —
        blocks loopback/private/link-local/reserved (e.g. ``127.0.0.1``,
        ``169.254.169.254`` cloud-metadata, RFC1918). DNS resolution runs in a
        thread so it never blocks the event loop. ponytail: basic resolve-and-
        check guard, not DNS-rebinding-proof; tighten with an egress proxy or
        allowlist if webhooks graduate past beta.
        """
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                return False
            infos = await asyncio.to_thread(
                socket.getaddrinfo,
                parsed.hostname,
                parsed.port or 0,
                0,
                socket.IPPROTO_TCP,
            )
            for info in infos:
                ip = ipaddress.ip_address(info[4][0])
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                    or ip.is_multicast
                    or ip.is_unspecified
                ):
                    return False
            return bool(infos)
        except Exception:  # noqa: BLE001 - unresolvable/invalid → unsafe
            return False

    async def _fire_webhook(self, job: BatchJob) -> None:
        """POST the job summary to the job's webhook URL on terminal state (#86).

        Best-effort: signs the payload with HMAC-SHA256 when a secret is set
        (header ``X-Signature``), retries once on any failure (including non-2xx
        responses), and swallows every error so a bad/unreachable webhook can
        never affect the prediction job. SSRF-guarded via ``_is_safe_webhook_url``.
        """
        webhook_url = job.config.get("webhook_url")
        if not webhook_url:
            return
        if not await self._is_safe_webhook_url(webhook_url):
            logger.warning(
                "Skipping webhook to unsafe/unresolvable URL: %s", webhook_url
            )
            return

        payload = json.dumps(
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "model_id": job.config.get("model_id"),
                "summary": job.results,
                "completed_at": (
                    job.completed_at.isoformat() if job.completed_at else None
                ),
            }
        ).encode()

        headers = {"Content-Type": "application/json"}
        secret = job.config.get("webhook_secret")
        if secret:
            headers["X-Signature"] = hmac.new(
                secret.encode(), payload, hashlib.sha256
            ).hexdigest()

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        webhook_url, content=payload, headers=headers
                    )
                    # httpx never raises on 4xx/5xx by default — do it explicitly
                    # so a transient receiver failure is retried, not swallowed.
                    response.raise_for_status()
                return
            except Exception as exc:  # noqa: BLE001 - webhook must never break the job
                logger.warning(
                    "Webhook delivery to %s failed (attempt %d): %s",
                    webhook_url,
                    attempt + 1,
                    exc,
                )
                if attempt == 0:
                    await asyncio.sleep(1)  # brief backoff before the single retry

    async def _read_data_chunks(
        self, s3_path: str, chunk_size: int
    ) -> AsyncGenerator[pd.DataFrame]:
        """Read data from S3 in chunks"""

        # Download file from S3 (s3_path is an object key)
        content = await self.s3_service.download_file_obj(s3_path)

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode="w+b", delete=False, suffix=".csv"
        ) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Read in chunks
            for chunk in pd.read_csv(temp_file_path, chunksize=chunk_size):
                yield chunk
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)

    async def _predict_chunk(
        self,
        chunk_df: pd.DataFrame,
        trained_model: Any,
        feature_engineer: Any,
        model: MLModel,
        config: BatchPredictionConfig,
    ) -> list[dict[str, Any]]:
        """Make predictions for a chunk of data"""

        predictions = []
        # Rows needing a per-prediction explanation, explained in one batched
        # pass after the loop (issue #80).
        to_explain: list[dict[str, Any]] = []
        is_classification = str(model.problem_type).endswith("classification")

        for index, row in chunk_df.iterrows():
            try:
                # Prepare input data
                input_data = row.to_dict()

                # Transform data if feature engineer exists. transform() is async.
                if feature_engineer:
                    X_transformed = await feature_engineer.transform(
                        pd.DataFrame([input_data])
                    )
                else:
                    X_transformed = pd.DataFrame([input_data])[model.feature_names]

                # Make prediction
                prediction = trained_model.predict(X_transformed)[0]
                prediction_value = (
                    prediction.item() if hasattr(prediction, "item") else prediction
                )

                # Compute probabilities whenever the (calibrated) classifier
                # supports them; they drive confidence + low-confidence flags
                # even when the caller didn't request the full vectors (#83).
                probabilities = None
                confidence = None
                low_confidence = None
                if is_classification and hasattr(trained_model, "predict_proba"):
                    proba_row = trained_model.predict_proba(X_transformed)[0]
                    proba_list = proba_row.tolist()
                    confidence = self.confidence.confidence_from_proba(proba_list)
                    if confidence is not None:
                        low_confidence = self.confidence.is_low_confidence(confidence)
                    if config.include_probabilities:
                        probabilities = proba_list

                # Create result
                result = {
                    "row_index": index,
                    "prediction": prediction_value,
                    "input_data": input_data,
                }

                if probabilities is not None:
                    result["probabilities"] = probabilities
                if confidence is not None:
                    result["confidence"] = confidence
                if low_confidence is not None:
                    result["low_confidence"] = low_confidence

                # Regression prediction interval from the model's residual std.
                if (
                    not is_classification
                    and getattr(model, "residual_std", None) is not None
                ):
                    interval = self.confidence.regression_interval(
                        prediction_value, model.residual_std
                    )
                    if interval is not None:
                        result["prediction_interval"] = interval

                # Per-prediction explanation (opt-in — issue #83/#80). Collected
                # here and computed in one batched pass after the loop so the
                # TreeExplainer is built once per chunk, not once per row.
                if getattr(config, "include_explanations", False):
                    to_explain.append(
                        {
                            "result": result,
                            "x_row": np.asarray(X_transformed)[0],
                            "prediction": prediction_value,
                        }
                    )

                if config.include_metadata:
                    result["metadata"] = {
                        "model_id": model.model_id,
                        "model_version": model.version,
                        "prediction_time": datetime.utcnow().isoformat(),
                    }

                predictions.append(result)

            except Exception as e:
                # Handle individual prediction error
                predictions.append(
                    {"row_index": index, "error": str(e), "input_data": row.to_dict()}
                )

        await self._attach_explanations(to_explain, trained_model, model)
        return predictions

    async def _attach_explanations(
        self,
        to_explain: list[dict[str, Any]],
        trained_model: Any,
        model: MLModel,
    ) -> None:
        """Attach per-prediction explanations to collected results (issue #80).

        Tree models get per-row SHAP via a single explainer build for the whole
        chunk (``compute_instance_shap_batch``); others fall back to the native
        per-row explainer. The CPU-bound SHAP work is offloaded to a worker
        thread so a large chunk doesn't stall the event loop. Best-effort: a
        failure leaves rows unexplained.
        """
        if not to_explain:
            return

        matrix = np.asarray([item["x_row"] for item in to_explain])
        preds = [item["prediction"] for item in to_explain]
        shap_rows = await asyncio.to_thread(
            self.interpretability.compute_instance_shap_batch,
            trained_model,
            matrix,
            model.feature_names,
            preds,
            model.problem_type,
        )

        for i, item in enumerate(to_explain):
            explanation = None
            if shap_rows is not None and i < len(shap_rows) and shap_rows[i] is not None:
                explanation = self.explainer.assemble(
                    shap_rows[i],
                    model.feature_names,
                    item["x_row"],
                    prediction=item["prediction"],
                    problem_type=model.problem_type,
                    method="shap_tree",
                )
            if explanation is None:
                explanation = self.explainer.explain(
                    trained_model,
                    item["x_row"],
                    model.feature_names,
                    prediction=item["prediction"],
                    problem_type=model.problem_type,
                    feature_importance=model.feature_importance,
                )
            if explanation is None:
                continue
            result = item["result"]
            result["explanation_text"] = explanation.explanation_text
            result["explanation"] = {
                "method": explanation.method,
                "top_features": [
                    {
                        "feature_name": f.feature_name,
                        "contribution": f.contribution,
                        "feature_value": f.feature_value,
                    }
                    for f in explanation.top_features
                ],
            }

    def _calculate_summary_statistics(
        self,
        predictions: list[dict[str, Any]],
        model: MLModel,
    ) -> dict[str, Any]:
        """Aggregate batch results into summary statistics (issue #82).

        Produces a prediction distribution (per class for classification, value
        stats for regression) and confidence statistics for the downloadable
        results' summary.
        """
        successful = [
            p for p in predictions if p.get("error") is None and "prediction" in p
        ]
        errors = [p for p in predictions if p.get("error") is not None]
        is_classification = str(model.problem_type).endswith("classification")

        prediction_distribution: dict[str, int] = {}
        prediction_value_stats: dict[str, float] = {}
        if is_classification:
            for p in successful:
                key = str(p["prediction"])
                prediction_distribution[key] = prediction_distribution.get(key, 0) + 1
        else:
            try:
                values = [float(p["prediction"]) for p in successful]
                if values:
                    prediction_value_stats = {
                        "min": min(values),
                        "max": max(values),
                        "mean": statistics.fmean(values),
                        "median": statistics.median(values),
                    }
            except (TypeError, ValueError):
                prediction_value_stats = {}

        confidences = [
            p["confidence"] for p in successful if p.get("confidence") is not None
        ]
        confidence_stats: dict[str, float] = {}
        if confidences:
            confidence_stats = {
                "min": min(confidences),
                "max": max(confidences),
                "mean": statistics.fmean(confidences),
                "median": statistics.median(confidences),
            }

        # Number of successful predictions flagged low-confidence (issue #83).
        low_confidence_count = sum(
            1 for p in successful if p.get("low_confidence") is True
        )

        success_count = len(successful)
        total = len(predictions)
        summary: dict[str, Any] = {
            "total_predictions": total,
            "success_count": success_count,
            "error_count": len(errors),
            "success_rate": (success_count / total * 100) if total else 0.0,
            "prediction_distribution": prediction_distribution,
            "confidence_stats": confidence_stats,
            "low_confidence_count": low_confidence_count,
        }
        if prediction_value_stats:
            summary["prediction_value_stats"] = prediction_value_stats
        return summary

    def _results_to_dataframe(self, predictions: list[dict[str, Any]]) -> pd.DataFrame:
        """Flatten prediction records into a clean tabular frame for CSV export:
        the original input columns plus prediction/confidence/error columns."""
        rows: list[dict[str, Any]] = []
        for p in predictions:
            row: dict[str, Any] = dict(p.get("input_data", {}) or {})
            if "prediction" in p:
                row["prediction"] = p["prediction"]
            if p.get("confidence") is not None:
                row["confidence"] = p["confidence"]
            if p.get("low_confidence") is not None:
                row["low_confidence"] = p["low_confidence"]
            if p.get("prediction_interval") is not None:
                row["prediction_interval"] = json.dumps(p["prediction_interval"])
            if p.get("probabilities") is not None:
                row["probabilities"] = json.dumps(p["probabilities"])
            if p.get("explanation_text") is not None:
                row["explanation"] = p["explanation_text"]
            if p.get("error") is not None:
                row["error"] = p["error"]
            rows.append(row)
        return pd.DataFrame(rows)

    async def _save_results(
        self,
        job: BatchJob,
        predictions: list[dict[str, Any]],
        config: BatchPredictionConfig,
    ) -> str:
        """Save prediction results to S3"""

        # Generate output path
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_key = f"batch-jobs/{job.user_id}/{config.model_id}/{timestamp}/results.{config.output_format}"

        if config.output_format.lower() == "csv":
            # Convert to a clean tabular CSV
            df = self._results_to_dataframe(predictions)
            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)
            content = csv_buffer.getvalue().encode("utf-8")

        elif config.output_format.lower() == "json":
            # Convert to JSON
            content = json.dumps(predictions, indent=2, default=str).encode("utf-8")

        else:
            raise ValueError(f"Unsupported output format: {config.output_format}")

        # Upload to S3
        await self.s3_service.upload_file_obj(BytesIO(content), output_key)

        return output_key

    async def get_job_status(self, job_id: str, user_id: str) -> BatchJob | None:
        """Get job status and progress"""

        return await BatchJob.find_one({"job_id": job_id, "user_id": user_id})

    async def list_user_jobs(
        self,
        user_id: str,
        job_type: JobType | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[BatchJob]:
        """List user's batch jobs"""

        query = {"user_id": user_id}
        if job_type:
            query["job_type"] = job_type
        if status:
            query["status"] = status

        return await BatchJob.find(query).sort("-created_at").limit(limit).to_list()

    async def cancel_job(self, job_id: str, user_id: str) -> bool:
        """Cancel a pending or running job"""

        job = await BatchJob.find_one(
            {
                "job_id": job_id,
                "user_id": user_id,
                "status": {"$in": [JobStatus.PENDING, JobStatus.RUNNING]},
            }
        )

        if not job:
            return False

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        await job.save()

        return True

    async def retry_job(self, job_id: str, user_id: str) -> bool:
        """Retry a failed job"""

        job = await BatchJob.find_one({"job_id": job_id, "user_id": user_id})

        if not job or not job.can_retry():
            return False

        # Reset job status
        job.status = JobStatus.PENDING
        job.started_at = None
        job.completed_at = None
        job.error_message = None
        job.progress.processed_records = 0
        job.progress.success_count = 0
        job.progress.error_count = 0
        job.progress.current_chunk = 0

        await job.save()

        # Start processing again
        self._spawn_processing(job)

        return True

    async def download_results(self, job_id: str, user_id: str) -> bytes | None:
        """Download job results"""

        job = await BatchJob.find_one(
            {"job_id": job_id, "user_id": user_id, "status": JobStatus.COMPLETED}
        )

        if not job or not job.output_path:
            return None

        return await self.s3_service.download_file_obj(job.output_path)
