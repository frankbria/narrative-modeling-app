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
import tempfile
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
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
from app.services.model_storage import ModelStorageService, run_locked_inference
from app.services.prediction_explainer_service import PredictionExplainerService
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)


def _safe_unlink(path: str) -> None:
    """Best-effort temp-file removal (issue #285). Called from ``finally``
    blocks, so a cleanup failure must never mask the original exception."""
    try:
        os.unlink(path)
    except OSError as exc:
        logger.debug("Failed to remove temp file %s: %s", path, exc)


# Hard ceiling on a single batch (issue #278). The result stream and summary are
# now O(chunk_size), so this is a resource/DoS guard (disk temp file + wall time),
# not a memory bound. Generous vs the 1000-record sync path; env-tunable.
MAX_BATCH_PREDICT_RECORDS = int(os.getenv("MAX_BATCH_PREDICT_RECORDS", "1000000"))

# Every column `_results_to_dataframe` can emit that is NOT an input column, so
# the deterministic streamed-CSV header (issue #278) can drop an input column
# that collides with one of these and keep its own canonical position.
_RESERVED_OUTPUT_COLUMNS = frozenset(
    {
        "prediction",
        "confidence",
        "low_confidence",
        "prediction_interval",
        "probabilities",
        "explanation",
        "error",
    }
)


class _BatchSummaryAccumulator:
    """Streaming aggregator for batch summary statistics (issue #278).

    Folds one prediction record at a time so the batch pipeline never holds every
    result in memory. Produces the same summary the pre-#278 in-memory pass did,
    minus median: median needs every value retained, which defeats the bounded-
    memory goal, and no consumer reads it (the UI uses ``confidence_stats.mean``
    and ``low_confidence_count`` only).
    """

    def __init__(self, is_classification: bool) -> None:
        self.is_classification = is_classification
        self.total = 0
        self.success = 0
        self.error_count = 0
        self.low_confidence_count = 0
        self.distribution: dict[str, int] = {}
        # Running scalar stats — O(1) state each (no value retention).
        self._val_n = 0
        self._val_sum = 0.0
        self._val_min: float | None = None
        self._val_max: float | None = None
        self._val_invalid = False  # any non-numeric prediction voids value stats
        self._conf_n = 0
        self._conf_sum = 0.0
        self._conf_min: float | None = None
        self._conf_max: float | None = None

    def add(self, p: dict[str, Any]) -> None:
        self.total += 1
        if p.get("error") is not None:
            self.error_count += 1
            return
        if "prediction" not in p:
            # error-free but prediction-less — matches the pre-#278 `successful`
            # filter (error is None AND prediction present); shouldn't occur.
            return
        self.success += 1
        prediction = p["prediction"]
        if self.is_classification:
            key = str(prediction)
            self.distribution[key] = self.distribution.get(key, 0) + 1
        elif not self._val_invalid:
            try:
                value = float(prediction)
            except (TypeError, ValueError):
                self._val_invalid = True  # all-or-nothing, mirroring the old code
            else:
                self._val_n += 1
                self._val_sum += value
                self._val_min = value if self._val_min is None else min(self._val_min, value)
                self._val_max = value if self._val_max is None else max(self._val_max, value)

        conf = p.get("confidence")
        if conf is not None:
            self._conf_n += 1
            self._conf_sum += conf
            self._conf_min = conf if self._conf_min is None else min(self._conf_min, conf)
            self._conf_max = conf if self._conf_max is None else max(self._conf_max, conf)
        if p.get("low_confidence") is True:
            self.low_confidence_count += 1

    def result(self) -> dict[str, Any]:
        confidence_stats: dict[str, float] = {}
        if self._conf_n and self._conf_min is not None and self._conf_max is not None:
            confidence_stats = {
                "min": self._conf_min,
                "max": self._conf_max,
                "mean": self._conf_sum / self._conf_n,
            }
        summary: dict[str, Any] = {
            "total_predictions": self.total,
            "success_count": self.success,
            "error_count": self.error_count,
            "success_rate": (self.success / self.total * 100) if self.total else 0.0,
            "prediction_distribution": self.distribution,
            "confidence_stats": confidence_stats,
            "low_confidence_count": self.low_confidence_count,
        }
        if (
            not self.is_classification
            and not self._val_invalid
            and self._val_n
            and self._val_min is not None
            and self._val_max is not None
        ):
            summary["prediction_value_stats"] = {
                "min": self._val_min,
                "max": self._val_max,
                "mean": self._val_sum / self._val_n,
            }
        return summary


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
        """Prepare and upload input data to S3.

        Resolves the record count first and rejects an over-cap batch (issue #278)
        *before* the S3 upload, so an oversized job never spends an upload round
        trip. Input file size is already bounded upstream by the upload cap (#270).
        """

        # Generate unique S3 path
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        s3_key = f"batch-jobs/{user_id}/{model_id}/{timestamp}/input.csv"

        if isinstance(input_data, str):
            if not os.path.exists(input_data):
                raise ValueError("Input file not found")
            # Count rows in bounded memory — never materialise the whole CSV just
            # to reject an over-cap batch (issue #278 review).
            total_records = sum(
                len(chunk) for chunk in pd.read_csv(input_data, chunksize=100_000)
            )
        elif isinstance(input_data, pd.DataFrame):
            total_records = len(input_data)
        elif isinstance(input_data, list):
            input_data = pd.DataFrame(input_data)
            total_records = len(input_data)
        else:
            raise ValueError("Unsupported input data type")

        if total_records > MAX_BATCH_PREDICT_RECORDS:
            raise ValueError(
                f"Batch too large: {total_records} records exceeds the maximum of "
                f"{MAX_BATCH_PREDICT_RECORDS}."
            )

        if isinstance(input_data, str):
            with open(input_data, "rb") as fh:
                await self.s3_service.upload_file_obj(fh, s3_key)
        else:  # DataFrame (a list input was converted above)
            csv_buffer = StringIO()
            input_data.to_csv(csv_buffer, index=False)
            await self.s3_service.upload_file_obj(
                BytesIO(csv_buffer.getvalue().encode("utf-8")), s3_key
            )

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

            output_format = config.output_format.lower()
            if output_format not in ("csv", "json"):
                raise ValueError(f"Unsupported output format: {config.output_format}")

            # Load model artifacts. load_model returns a (model, feature_engineer)
            # tuple keyed by (model_id, user_id) — issue #82 bugfix.
            trained_model, feature_engineer = await self.model_storage.load_model(
                config.model_id, job.user_id
            )

            is_classification = str(model.problem_type).endswith("classification")
            want_proba = is_classification and hasattr(trained_model, "predict_proba")

            # Stream results to a temp file chunk-by-chunk and fold summary stats
            # incrementally, so peak memory stays O(chunk_size) instead of
            # O(total_records) — issue #278. The finished file is streamed to S3.
            summary_acc = _BatchSummaryAccumulator(is_classification)
            out_fd, out_path = tempfile.mkstemp(suffix=f".{output_format}")
            chunk_num = 0
            csv_header: list[str] | None = None
            json_first = True
            try:
                with os.fdopen(out_fd, "w", encoding="utf-8", newline="") as out:
                    if output_format == "json":
                        out.write("[")

                    async for chunk_df in self._read_data_chunks(
                        job.input_path, config.chunk_size
                    ):
                        chunk_num += 1

                        try:
                            chunk_predictions = await self._predict_chunk(
                                chunk_df, trained_model, feature_engineer, model, config
                            )
                        except Exception as e:  # noqa: BLE001 - isolate a failed chunk
                            chunk_predictions = [
                                {"error": str(e), "row_index": i}
                                for i in range(len(chunk_df))
                            ]

                        if output_format == "csv":
                            if csv_header is None:
                                csv_header = self._csv_header(
                                    list(chunk_df.columns),
                                    is_classification,
                                    want_proba,
                                    model,
                                    config,
                                )
                            chunk_frame = self._results_to_dataframe(
                                chunk_predictions
                            ).reindex(columns=csv_header)
                            chunk_frame.to_csv(out, index=False, header=(chunk_num == 1))
                        else:
                            for prediction in chunk_predictions:
                                if not json_first:
                                    out.write(", ")
                                out.write(json.dumps(prediction, default=str))
                                json_first = False

                        for prediction in chunk_predictions:
                            summary_acc.add(prediction)

                        # Update cumulative progress after each chunk
                        job.update_progress(
                            processed_records=summary_acc.total,
                            success_count=summary_acc.success,
                            error_count=summary_acc.error_count,
                            current_chunk=chunk_num,
                        )
                        await job.save()

                    if output_format == "json":
                        out.write("]")

                # Stream the finished results file to S3 (bounded memory).
                output_path = await self._upload_results_file(out_path, job, config)
                job.output_path = output_path

                # Mark job as completed with summary statistics
                summary = summary_acc.result()
                summary["output_path"] = output_path
                job.mark_completed(summary)
            finally:
                _safe_unlink(out_path)

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
        thread so it never blocks the event loop. Note: this is a basic resolve-
        and-check guard, not DNS-rebinding-proof; tighten with an egress proxy or
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
                # Unwrap IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) so a mapped
                # private/loopback address can't slip past the flag checks.
                mapped = getattr(ip, "ipv4_mapped", None)
                if mapped is not None:
                    ip = mapped
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
            # Log only the host (URL may carry credentials in its query string).
            logger.warning(
                "Skipping webhook to unsafe/unresolvable host: %s",
                urlparse(webhook_url).netloc or "<webhook>",
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

        # Log only the host, never the full URL — a webhook URL can carry tokens
        # in its query string that must not land in application logs.
        host = urlparse(webhook_url).netloc or "<webhook>"
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
                    host,
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
            _safe_unlink(temp_file_path)

    async def _predict_chunk(
        self,
        chunk_df: pd.DataFrame,
        trained_model: Any,
        feature_engineer: Any,
        model: MLModel,
        config: BatchPredictionConfig,
    ) -> list[dict[str, Any]]:
        """Make predictions for a chunk of data.

        Vectorised (issue #202): transform/predict/predict_proba run once over
        the whole chunk instead of once per row (~3 sklearn calls per chunk vs
        ~3·N). On any chunk-level failure, fall back to row-by-row processing so
        a single bad row (or a batch-incompatible estimator) still yields per-row
        error isolation. Explanations stay batched via ``_attach_explanations``.
        """
        try:
            return await self._predict_chunk_vectorized(
                chunk_df, trained_model, feature_engineer, model, config
            )
        except Exception as exc:  # noqa: BLE001 - fall back to per-row isolation
            # warning + traceback: a systematic failure (e.g. a model/feature
            # contract change) would silently fall back on every chunk otherwise.
            logger.warning(
                "Vectorised chunk inference failed (%s); falling back to row-by-row",
                exc,
                exc_info=True,
            )
            return await self._predict_chunk_sequential(
                chunk_df, trained_model, feature_engineer, model, config
            )

    async def _predict_chunk_vectorized(
        self,
        chunk_df: pd.DataFrame,
        trained_model: Any,
        feature_engineer: Any,
        model: MLModel,
        config: BatchPredictionConfig,
    ) -> list[dict[str, Any]]:
        """Vectorised chunk inference (issue #202).

        Runs feature transform, ``predict`` and (for classifiers) ``predict_proba``
        once over the entire chunk, then assembles per-row result dicts by indexing
        into the resulting arrays — no sklearn calls in the assembly loop. Any
        failure here propagates to ``_predict_chunk``'s row-by-row fallback.
        """
        is_classification = str(model.problem_type).endswith("classification")

        # One transform / predict / predict_proba per chunk.
        if feature_engineer:
            X_transformed = await feature_engineer.transform(chunk_df)
        else:
            X_transformed = chunk_df[model.feature_names]

        # Inference runs off the loop and serialized per model on the shared
        # cached estimator (issue #265).
        want_proba = is_classification and hasattr(trained_model, "predict_proba")

        def _infer(X):
            p = trained_model.predict(X)
            pm = trained_model.predict_proba(X) if want_proba else None
            return p, pm

        preds, proba_matrix = await run_locked_inference(
            model.model_id, model.user_id, lambda: _infer(X_transformed)
        )

        # Engineered feature rows for the batched explainer (issue #80) — only
        # materialised when explanations are requested, so we never densify a
        # (possibly sparse) feature matrix for the common no-explanation path.
        want_explanations = config.include_explanations
        X_array = np.asarray(X_transformed) if want_explanations else None

        predictions: list[dict[str, Any]] = []
        to_explain: list[dict[str, Any]] = []

        for i, (index, row) in enumerate(chunk_df.iterrows()):
            input_data = row.to_dict()
            prediction = preds[i]
            prediction_value = (
                prediction.item() if hasattr(prediction, "item") else prediction
            )

            result: dict[str, Any] = {
                "row_index": index,
                "prediction": prediction_value,
                "input_data": input_data,
            }

            # Probabilities drive confidence + low-confidence flags even when the
            # caller didn't request the full vectors (#83).
            if proba_matrix is not None:
                proba_list = proba_matrix[i].tolist()
                confidence = self.confidence.confidence_from_proba(proba_list)
                if confidence is not None:
                    result["confidence"] = confidence
                    result["low_confidence"] = self.confidence.is_low_confidence(
                        confidence
                    )
                if config.include_probabilities:
                    result["probabilities"] = proba_list

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

            # Per-prediction explanation (opt-in — issue #83/#80). Collected here
            # and computed in one batched pass after the loop so the explainer is
            # built once per chunk, not once per row.
            if want_explanations and X_array is not None:
                to_explain.append(
                    {
                        "result": result,
                        "x_row": X_array[i],
                        "prediction": prediction_value,
                    }
                )

            if config.include_metadata:
                result["metadata"] = {
                    "model_id": model.model_id,
                    "model_version": model.version,
                    "prediction_time": datetime.now(UTC).isoformat(),
                }

            predictions.append(result)

        await self._attach_explanations(to_explain, trained_model, model)
        return predictions

    async def _predict_chunk_sequential(
        self,
        chunk_df: pd.DataFrame,
        trained_model: Any,
        feature_engineer: Any,
        model: MLModel,
        config: BatchPredictionConfig,
    ) -> list[dict[str, Any]]:
        """Row-by-row chunk inference — the fallback for ``_predict_chunk`` (#202).

        Preserves per-row error isolation: a row that fails inference becomes an
        error record instead of sinking the whole chunk.
        """

        predictions = []
        # Rows needing a per-prediction explanation, explained in one batched
        # pass after the loop (issue #80).
        to_explain: list[dict[str, Any]] = []
        is_classification = str(model.problem_type).endswith("classification")
        want_proba = is_classification and hasattr(trained_model, "predict_proba")

        def _infer(X):
            # Off the loop + serialized per model on the shared cached estimator
            # (issue #265). Loop-invariant, so defined once outside the row loop.
            p = trained_model.predict(X)
            pm = trained_model.predict_proba(X) if want_proba else None
            return p, pm

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

                pred_arr, proba_matrix = await run_locked_inference(
                    model.model_id, model.user_id, lambda: _infer(X_transformed)
                )
                prediction = pred_arr[0]
                prediction_value = (
                    prediction.item() if hasattr(prediction, "item") else prediction
                )

                # Compute probabilities whenever the (calibrated) classifier
                # supports them; they drive confidence + low-confidence flags
                # even when the caller didn't request the full vectors (#83).
                probabilities = None
                confidence = None
                low_confidence = None
                if proba_matrix is not None:
                    proba_row = proba_matrix[0]
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
                        "prediction_time": datetime.now(UTC).isoformat(),
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
        """Aggregate an in-memory prediction list into summary statistics (#82).

        Thin wrapper over the streaming :class:`_BatchSummaryAccumulator` so there
        is one implementation shared with the chunk-by-chunk batch pipeline (#278).
        """
        is_classification = str(model.problem_type).endswith("classification")
        acc = _BatchSummaryAccumulator(is_classification)
        for prediction in predictions:
            acc.add(prediction)
        return acc.result()

    def _csv_header(
        self,
        input_columns: list[str],
        is_classification: bool,
        want_proba: bool,
        model: MLModel,
        config: BatchPredictionConfig,
    ) -> list[str]:
        """Deterministic CSV column order for streamed results (issue #278).

        A superset of every column ``_results_to_dataframe`` can emit for this
        config + model, in the same order, so each chunk reindexes to a stable
        header and appends without a per-chunk header row. Data-dependent columns
        (notably ``error``) are always reserved last so a later chunk's error rows
        can never misalign the file. An input column that collides with an output
        name is dropped (``_results_to_dataframe`` already overwrites it with the
        output value), so the reserved columns keep their canonical positions.
        """
        cols = [c for c in input_columns if c not in _RESERVED_OUTPUT_COLUMNS]
        cols.append("prediction")
        if want_proba:
            cols += ["confidence", "low_confidence"]
        if not is_classification and getattr(model, "residual_std", None) is not None:
            cols.append("prediction_interval")
        if want_proba and config.include_probabilities:
            cols.append("probabilities")
        if config.include_explanations:
            cols.append("explanation")
        cols.append("error")
        return cols

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

    async def _upload_results_file(
        self,
        out_path: str,
        job: BatchJob,
        config: BatchPredictionConfig,
    ) -> str:
        """Upload a finished, on-disk results file to S3 (issue #278).

        Streams the file straight from disk via ``upload_fileobj`` (multipart
        under the hood), so a large results file is never loaded into memory.
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_key = f"batch-jobs/{job.user_id}/{config.model_id}/{timestamp}/results.{config.output_format}"

        with open(out_path, "rb") as fh:
            await self.s3_service.upload_file_obj(fh, output_key)

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
        job.completed_at = datetime.now(UTC)
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
