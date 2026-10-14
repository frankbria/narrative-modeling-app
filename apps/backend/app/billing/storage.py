"""Per-tenant storage ceiling (#768).

FREE may hold ``PlanLimits.storage_bytes`` of stored datasets plus model
artifacts. Every dataset-creating route calls ``enforce_storage_ceiling`` with the
bytes it is about to store, before the S3 put; crossing the ceiling is a 402 in the
same ``quota_exceeded`` shape as the per-period quotas (``enforcement.reserve``),
so the frontend's one plan-limit dialog renders it. Sizes go out in MB
(``storage_mb``): the dialog prints ``used`` and ``limit`` as they come.

Counted (#781): ``UserData.file_size``, the file a dataset is on NOW, which a
transformation, an undo or a fix keeps in step with ``s3_url``
(``dataset_link.record_new_file``; the dual-written ``DatasetMetadata`` twin is the
same object, so it is not added again); ``DatasetVersion.file_size``, each version
being its own object under ``versions/``; and ``MLModel.model_size``.

A dataset whose current file IS a version's object (where an undo leaves it) is
counted once, not as both.

Not counted: the files a dataset has moved off (``superseded_s3_urls``): their sizes
are not recorded, and each holds the same bytes as a version that is counted. So the
figure is a floor on what the tenant holds, never more. A row written before
``file_size`` existed counts as nothing until
``scripts/backfill_dataset_file_sizes.py`` has run. Training is not refused at the
ceiling — the check is at upload.
"""

from fastapi import HTTPException, status

from app.billing import metering
from app.billing.plans import UNLIMITED, limits_for
from app.middleware.metrics import quota_denials
from app.models.ml_model import MLModel
from app.models.subscription import PlanTier
from app.models.user_data import UserData
from app.models.version import DatasetVersion
from app.services import product_events

_MB = 1024 * 1024


async def _sum(model, field: str, user_id: str) -> int:
    rows = await model.aggregate(
        [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": None, "total": {"$sum": {"$ifNull": [f"${field}", 0]}}}},
        ]
    ).to_list()
    return int(rows[0]["total"]) if rows else 0


async def _dataset_and_version_bytes(user_id: str) -> int:
    """Each stored object once: every version, and every dataset's current file unless
    that file IS a version's object (where an undo leaves it).

    # shortcut: reads the tenant's dataset and version locations (two small fields a
    # row) to compare them here; move the comparison into an aggregation if a capped
    # tenant can come to hold tens of thousands of versions.
    """
    versions = await _locations(DatasetVersion, user_id)
    datasets = await _locations(UserData, user_id)
    held_by_a_version = {url for url, _ in versions}
    current = sum(size for url, size in datasets if url not in held_by_a_version)
    return current + sum(size for _, size in versions)


async def _locations(model, user_id: str) -> list[tuple[str, int]]:
    """(s3_url, file_size) of the tenant's rows; a row with no size counts as nothing."""
    cursor = model.get_motor_collection().find({"user_id": user_id}, {"s3_url": 1, "file_size": 1})
    return [(row.get("s3_url"), row.get("file_size") or 0) async for row in cursor]


async def stored_bytes(user_id: str) -> int:
    """Bytes this tenant holds: datasets, their versions, and model artifacts."""
    return await _dataset_and_version_bytes(user_id) + await _sum(MLModel, "model_size", user_id)


async def enforce_storage_ceiling(user_id: str, incoming_bytes: int) -> None:
    """Raise 402 if storing ``incoming_bytes`` more would cross the tenant's ceiling.

    # ponytail: check-then-write, so two concurrent uploads can each pass and
    # overshoot by one file; bounded by the per-user upload concurrency cap (#526).
    """
    tier = await metering.effective_tier_for(user_id)
    limit = limits_for(tier).storage_bytes
    if limit == UNLIMITED:
        return
    used = await stored_bytes(user_id)
    if used + incoming_bytes <= limit:
        return
    quota_denials.labels(metric="storage_mb", tier=tier.value).inc()
    await product_events.record(
        user_id, product_events.QUOTA_DENIED, metric="storage_mb", tier=tier.value
    )
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "error": "quota_exceeded",
            "metric": "storage_mb",
            "limit": limit // _MB,
            "used": used // _MB,
            "tier": tier.value,
            "resets_at": None,  # a standing ceiling: it frees up when data is erased
            "message": (
                f"This upload would take you past the {limit // _MB} MB of storage "
                f"included in the {tier.value} plan. Delete datasets or models you no "
                "longer need, or upgrade."
            ),
            "upgrade_available": tier == PlanTier.FREE,
        },
    )
