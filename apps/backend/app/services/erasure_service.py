"""Cascade dataset/user erasure (issue #259).

Fixes the non-cascading ``delete_dataset`` that orphaned S3 objects, PII, and
every child document. Provides GDPR/CCPA right-to-erasure across BOTH dataset
id-spaces (the ``DatasetMetadata`` string-``dataset_id`` system and the legacy
``UserData`` ObjectId system).

Design (user-confirmed, see tasks/259-cascade-erasure.md):
- **Best-effort, not ACID.** Real Mongo transactions need a replica set, which
  local/CI single-node Mongo lacks (the codebase already avoids them). Instead
  the cascade is ordered (children -> S3 -> parent last) and idempotent: a
  re-run clears any residuals a partial failure left behind.
- Every step is guarded; failures are recorded on the ``DeletionManifest``
  rather than aborting the sweep, so one bad delete can't strand the rest.
- The parent document is deleted **last**, so an interrupted run is always
  re-discoverable and re-runnable.
"""

from __future__ import annotations

import logging
import uuid

from beanie import Document, PydanticObjectId

from app.models.ai_feedback import AIRecommendationFeedback
from app.models.analytics_result import AnalyticsResult
from app.models.bulk_transformation import BulkTransformationJob
from app.models.column_stats import ColumnStats
from app.models.data_issue import DataIssueRecord
from app.models.dataset import DatasetMetadata
from app.models.erasure_audit import ErasureAuditLog
from app.models.feature import FeatureDefinition
from app.models.ml_model import MLModel
from app.models.model import ModelConfig
from app.models.plot import Plot
from app.models.revised_data import RevisedData
from app.models.trained_model import TrainedModel
from app.models.training_job import TrainingJob
from app.models.transformation import TransformationConfig
from app.models.user_data import UserData
from app.models.version import DatasetVersion, TransformationLineage
from app.models.visualization_cache import VisualizationCache
from app.models.workflow import WorkflowState
from app.schemas.erasure import DeletionManifest
from app.services.model_storage import ModelStorageService
from app.services.redis_cache import cache_service
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)

# Child collections keyed by the DatasetMetadata string ``dataset_id``.
# MLModel is handled separately (its S3 artifacts are swept via delete_model).
_STRING_KEYED_MODELS = [
    TransformationConfig,
    DatasetVersion,
    TransformationLineage,
    FeatureDefinition,
    WorkflowState,
    BulkTransformationJob,
    ModelConfig,
    TrainingJob,
    DataIssueRecord,
    AIRecommendationFeedback,
]

# Legacy UserData children linked via a Beanie Link (stored as a DBRef); queried
# by ``{"<field>.$id": <ObjectId>}``. (model_class, dbref_field_name).
_LINK_KEYED_MODELS = [
    (ColumnStats, "dataset_id"),
    (VisualizationCache, "dataset_id"),
    (Plot, "datasetId"),
    (AnalyticsResult, "datasetId"),
    (TrainedModel, "datasetId"),
    (RevisedData, "original_data"),
]


def _s3_key(url_or_key: str | None, bucket_name: str) -> str | None:
    """Derive a raw S3 object key from a stored ``s3://.../key`` URL or a bare key."""
    if not url_or_key:
        return None
    if url_or_key.startswith("s3://"):
        # s3://bucket/key... -> key...
        without_scheme = url_or_key[len("s3://"):]
        parts = without_scheme.split("/", 1)
        return parts[1] if len(parts) == 2 else None
    if url_or_key.startswith("http"):
        # https://bucket.s3[.region].amazonaws.com/key... -> key...
        after_host = url_or_key.split("/", 3)
        return after_host[3] if len(after_host) == 4 else None
    return url_or_key  # already a key (e.g. DatasetMetadata.file_path)


class DatasetErasureService:
    """Ordered, idempotent cascade erasure with a deletion manifest + audit log."""

    def __init__(self) -> None:
        self.s3_service = S3Service()
        self.model_storage = ModelStorageService()

    # ---- public API -----------------------------------------------------

    async def erase_dataset(
        self,
        dataset_id: str,
        user_id: str,
        *,
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> DeletionManifest:
        """Cascade-erase a single dataset (either id-space) and record an audit entry."""
        manifest = DeletionManifest(
            target_type="dataset", target_id=dataset_id, subject_user_id=user_id
        )
        found = await self._erase_one_dataset(dataset_id, user_id, manifest)
        manifest.idempotent_noop = not found and self._is_empty(manifest)
        await self._write_audit("dataset", dataset_id, user_id, actor_id or user_id, reason, manifest)
        return manifest

    async def erase_user(
        self,
        user_id: str,
        *,
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> DeletionManifest:
        """Cascade-erase every dataset owned by a user, plus user-scoped records."""
        manifest = DeletionManifest(
            target_type="user", target_id=user_id, subject_user_id=user_id
        )

        # Both dataset systems.
        async for ds in DatasetMetadata.find(DatasetMetadata.user_id == user_id):
            await self._erase_one_dataset(ds.dataset_id, user_id, manifest, _parent=ds)
        async for ud in UserData.find(UserData.user_id == user_id):
            await self._erase_one_dataset(str(ud.id), user_id, manifest, _parent=ud)

        # Any remaining user-scoped documents (models/jobs not tied to a surviving
        # dataset, feedback, etc.). Best-effort sweep by user_id.
        await self._sweep_user_scoped(user_id, manifest)

        manifest.idempotent_noop = self._is_empty(manifest)
        await self._write_audit("user", user_id, user_id, actor_id or user_id, reason, manifest)
        return manifest

    @staticmethod
    def _is_empty(manifest: DeletionManifest) -> bool:
        """Nothing was actually removed from any store."""
        return (
            manifest.total_documents_deleted == 0
            and not manifest.s3_objects_deleted
            and manifest.redis_keys_evicted == 0
        )

    # ---- cascade core ---------------------------------------------------

    async def _erase_one_dataset(
        self,
        dataset_id: str,
        user_id: str,
        manifest: DeletionManifest,
        _parent: DatasetMetadata | UserData | None = None,
    ) -> bool:
        """Sweep all children/artifacts for one dataset. Returns True if an owned parent existed.

        SECURITY: children are swept ONLY for an id-space whose parent document
        is owned by ``user_id``. Without this gate a caller could erase another
        tenant's children by passing a dataset_id/ObjectId they don't own (the
        children collections aren't all user-scoped) — the ownership chain runs
        through the parent, so we require it before deleting anything.
        """
        # Scope tombstone retention to THIS dataset's cascade (erase_user shares
        # one manifest across many datasets — an earlier dataset's failure must
        # not retain later, cleanly-erased datasets' parents).
        failures_start = len(manifest.failures)

        # Resolve parent(s) in either id-space (ownership-checked).
        parent_meta = _parent if isinstance(_parent, DatasetMetadata) else None
        parent_ud = _parent if isinstance(_parent, UserData) else None
        if parent_meta is None and parent_ud is None:
            parent_meta = await DatasetMetadata.find_one(
                DatasetMetadata.dataset_id == dataset_id,
                DatasetMetadata.user_id == user_id,
            )
            parent_ud = await self._get_userdata(dataset_id, user_id)

        # Dual-write: a DatasetMetadata-backed dataset (created via
        # DatasetService.create_dataset) ALSO has a legacy UserData row sharing
        # its s3_url and carrying PII (contains_pii/pii_report/data_preview) +
        # Link[UserData] children. There is no id link, so resolve it by
        # (user_id, s3_url) — else erasing a string dataset_id orphans that PII
        # (the central bug in issue #259).
        if parent_meta is not None and parent_ud is None and parent_meta.s3_url:
            # Guard on a truthy s3_url: `s3_url == None`/"" would match unrelated
            # UserData rows with a null/empty url for this user.
            parent_ud = await UserData.find_one(
                UserData.user_id == user_id, UserData.s3_url == parent_meta.s3_url
            )

        # No owned parent -> nothing this caller may erase. Idempotent no-op.
        if parent_meta is None and parent_ud is None:
            return False

        # --- string / DatasetMetadata id-space (only if that parent is owned) ---
        if parent_meta is not None:
            # 1. MLModel children first (delete_model sweeps their S3 artifacts + doc).
            await self._erase_models(dataset_id, user_id, manifest)
            # 2. Remaining string-keyed children.
            for model_cls in _STRING_KEYED_MODELS:
                await self._delete_many(model_cls, {"dataset_id": dataset_id}, manifest)
            # 3. S3 source + redis, then parent LAST.
            await self._delete_s3(
                _s3_key(parent_meta.file_path or parent_meta.s3_url, self.s3_service.bucket_name),
                manifest,
            )
            await self._evict_redis(dataset_id, manifest)

        # --- legacy UserData id-space (dual-write twin or a legacy-only upload) ---
        if parent_ud is not None:
            for model_cls, field in _LINK_KEYED_MODELS:
                await self._delete_many(model_cls, {f"{field}.$id": parent_ud.id}, manifest)
            await self._delete_s3(
                _s3_key(parent_ud.file_path or parent_ud.s3_url, self.s3_service.bucket_name),
                manifest,
            )
            await self._evict_redis(str(parent_ud.id), manifest)

        # Parents LAST — retained as re-discoverable tombstones if THIS dataset's
        # cascade left residuals, so the owner can re-run to finish.
        if parent_meta is not None:
            await self._delete_parent_if_clean(parent_meta, "dataset_metadata", manifest, failures_start)
        if parent_ud is not None:
            await self._delete_parent_if_clean(parent_ud, "user_data", manifest, failures_start)

        return True

    async def _erase_models(self, dataset_id: str, user_id: str, manifest: DeletionManifest) -> None:
        """Delete every MLModel for the dataset, sweeping its S3 artifacts via delete_model."""
        try:
            models = await MLModel.find(
                MLModel.dataset_id == dataset_id, MLModel.user_id == user_id
            ).to_list()
        except Exception as e:  # noqa: BLE001 - best-effort sweep
            manifest.failures.append(f"query ml_models: {e}")
            return
        for m in models:
            try:
                await self.model_storage.delete_model(m.model_id, user_id)
                manifest.documents_deleted["ml_models"] = manifest.documents_deleted.get("ml_models", 0) + 1
                # delete_model removes the per-model artifact prefix.
                manifest.s3_objects_deleted.append(f"models/{user_id}/{m.model_id}/")
            except Exception as e:  # noqa: BLE001
                manifest.failures.append(f"delete_model {m.model_id}: {e}")

    # ---- primitives (each guarded; records failures, never raises) ------

    async def _delete_many(
        self, model_cls: type[Document], query: dict, manifest: DeletionManifest
    ) -> None:
        try:
            name = model_cls.Settings.name
            result = await model_cls.find(query).delete()
            count = getattr(result, "deleted_count", 0) or 0
            if count:
                manifest.documents_deleted[name] = manifest.documents_deleted.get(name, 0) + count
        except Exception as e:  # noqa: BLE001
            manifest.failures.append(f"delete {getattr(model_cls, '__name__', '?')}: {e}")

    async def _delete_doc(self, doc: Document, name: str, manifest: DeletionManifest) -> None:
        try:
            result = await doc.delete()
            # Count only an actual deletion — a doc already removed (e.g. a
            # dual-write twin swept in an earlier pass) returns deleted_count=0
            # and must not inflate the manifest. (result is None on some Beanie
            # paths -> treat as deleted.)
            if result is None or result.deleted_count:
                manifest.documents_deleted[name] = manifest.documents_deleted.get(name, 0) + 1
        except Exception as e:  # noqa: BLE001
            manifest.failures.append(f"delete {name} doc: {e}")

    async def _delete_parent_if_clean(
        self, doc: Document, name: str, manifest: DeletionManifest, failures_start: int
    ) -> None:
        """Delete the parent LAST — but keep it as a re-discoverable tombstone if a
        **Mongo child** deletion failed in THIS dataset's cascade, so the owner can
        re-run the erase to finish clearing the child documents.

        S3/Redis failures do NOT block parent deletion: Mongo is the source of
        truth for discoverability, users expect DELETE to remove the dataset, and
        an orphaned S3 object is recorded in ``manifest.failures`` (covered by the
        AC3 S3 lifecycle/versioning and a re-runnable POST /erase). The tombstone
        note goes to ``notes`` (informational), not ``failures``."""
        new_failures = manifest.failures[failures_start:]
        blocking = [f for f in new_failures if not f.startswith(("s3 delete", "redis evict"))]
        if blocking:
            manifest.notes.append(
                f"retained {name} parent as tombstone (Mongo residual present; re-run erase)"
            )
            return
        await self._delete_doc(doc, name, manifest)

    async def _delete_s3(self, key: str | None, manifest: DeletionManifest) -> None:
        if not key:
            return
        if self.s3_service.is_mock_mode or self.s3_service.s3_client is None:
            # No S3 configured (e.g. unit tests) -> nothing to delete, not a failure.
            return
        try:
            # delete_object is idempotent (no error if the key is already gone).
            await self.s3_service.delete_file(key)
            manifest.s3_objects_deleted.append(key)
        except Exception as e:  # noqa: BLE001
            manifest.failures.append(f"s3 delete {key}: {e}")

    async def _evict_redis(self, dataset_id: str, manifest: DeletionManifest) -> None:
        try:
            # delete_pattern uses Redis KEYS (O(N), blocking) — fine at beta scale;
            # swap for a SCAN-based sweep if the viz-cache keyspace grows large.
            evicted = await cache_service.delete_pattern(f"viz:{dataset_id}:*")
            manifest.redis_keys_evicted += evicted or 0
        except Exception as e:  # noqa: BLE001
            manifest.failures.append(f"redis evict {dataset_id}: {e}")

    async def _sweep_user_scoped(self, user_id: str, manifest: DeletionManifest) -> None:
        """Delete leftover user-scoped docs (models/jobs/feedback) for a full-user erasure."""
        from app.models.ab_test import ABTest
        from app.models.batch_job import BatchJob
        from app.models.feedback import Feedback

        # Any MLModels not tied to a dataset we already swept.
        try:
            leftover = await MLModel.find(MLModel.user_id == user_id).to_list()
            for m in leftover:
                await self.model_storage.delete_model(m.model_id, user_id)
                manifest.documents_deleted["ml_models"] = manifest.documents_deleted.get("ml_models", 0) + 1
                manifest.s3_objects_deleted.append(f"models/{user_id}/{m.model_id}/")
        except Exception as e:  # noqa: BLE001
            manifest.failures.append(f"sweep ml_models: {e}")

        # Only sweep collections that actually have a user_id field (some
        # dataset-keyed children don't — querying them by user_id is a no-op).
        for model_cls in [BatchJob, ABTest, Feedback, *_STRING_KEYED_MODELS]:
            if "user_id" in model_cls.model_fields:
                await self._delete_many(model_cls, {"user_id": user_id}, manifest)

    # ---- helpers --------------------------------------------------------

    async def _get_userdata(self, dataset_id: str, user_id: str) -> UserData | None:
        oid = _as_object_id(dataset_id)
        if oid is None:
            return None
        ud = await UserData.get(oid)
        return ud if ud is not None and ud.user_id == user_id else None

    async def _write_audit(
        self,
        target_type: str,
        target_id: str,
        subject_user_id: str,
        actor_id: str,
        reason: str | None,
        manifest: DeletionManifest,
    ) -> None:
        # Don't record (or mint an id for) a pure no-op — nothing was erased, so
        # there is nothing to audit. Prevents an authenticated caller from
        # spamming the append-only log with erase attempts on data they don't own.
        if self._is_empty(manifest):
            return
        erasure_id = uuid.uuid4().hex
        manifest.erasure_id = erasure_id  # single id shared by response + audit
        try:
            await ErasureAuditLog(
                erasure_id=erasure_id,
                actor_id=actor_id,
                subject_user_id=subject_user_id,
                target_type=target_type,
                target_id=target_id,
                reason=reason,
                manifest=manifest.model_dump(mode="json"),
                status=manifest.status,
            ).insert()
        except Exception as e:  # noqa: BLE001 - audit failure must not lose the erasure result
            logger.error(f"Failed to write erasure audit log for {target_type} {target_id}: {e}")
            manifest.failures.append("audit write failed (see server logs)")


def _as_object_id(value: str) -> PydanticObjectId | None:
    try:
        return PydanticObjectId(value)
    except Exception:  # noqa: BLE001 - not an ObjectId (e.g. a 'dataset_xxx' string)
        return None


# Singleton
dataset_erasure_service = DatasetErasureService()
