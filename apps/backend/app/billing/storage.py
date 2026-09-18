"""Per-tenant storage ceiling (#768).

FREE may hold ``PlanLimits.storage_bytes`` of stored datasets plus model
artifacts. Every dataset-creating route calls ``enforce_storage_ceiling`` with the
bytes it is about to store, before the S3 put; crossing the ceiling is a 402 in the
same ``quota_exceeded`` shape as the per-period quotas (``enforcement.reserve``),
so the frontend's one plan-limit dialog renders it. Sizes go out in MB
(``storage_mb``): the dialog prints ``used`` and ``limit`` as they come.

Counted: ``UserData.file_size`` (the dual-written ``DatasetMetadata`` twin is the
same object, so it is not added again) and ``MLModel.model_size``. Not counted:
transformation outputs and versions, and rows written before ``file_size``
existed. Training is not refused at the ceiling — the check is at upload.
"""

from fastapi import HTTPException, status

from app.billing import metering
from app.billing.plans import UNLIMITED, limits_for
from app.middleware.metrics import quota_denials
from app.models.ml_model import MLModel
from app.models.subscription import PlanTier
from app.models.user_data import UserData
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


async def stored_bytes(user_id: str) -> int:
    """Bytes this tenant holds: datasets plus model artifacts."""
    return await _sum(UserData, "file_size", user_id) + await _sum(MLModel, "model_size", user_id)


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
