"""Record funnel events and read them back as numbers (#769).

`record` never raises. Telemetry that can fail an upload, a training run or a
Stripe webhook is worse than no telemetry.
"""

import logging
from collections import Counter
from datetime import datetime, timedelta

from pymongo.errors import DuplicateKeyError

from app.models.product_event import ProductEvent
from app.utils.datetime import as_utc, utcnow

logger = logging.getLogger(__name__)

ACCOUNT_CREATED = "account_created"
FIRST_UPLOAD = "first_upload"
FIRST_MODEL_TRAINED = "first_model_trained"
QUOTA_DENIED = "quota_denied"
CHECKOUT_STARTED = "checkout_started"
CHECKOUT_COMPLETED = "checkout_completed"
SUBSCRIPTION_CANCELLED = "subscription_cancelled"

#: Activation = a first trained model within this long of signing up.
ACTIVATION_WINDOW = timedelta(days=7)


async def record(user_id: str, event: str, *, once: str | None = None, **properties) -> None:
    """Append one event. With `once`, a second event with the same key is dropped."""
    try:
        await ProductEvent(
            user_id=user_id, event=event, properties=properties, dedupe_key=once
        ).insert()
    except DuplicateKeyError:
        pass  # already recorded: the point of `once`
    except Exception:
        logger.warning("could not record product event %s", event, exc_info=True)


async def funnel(days: int, now: datetime | None = None) -> dict:
    """The launch funnel over the last `days` days.

    Activation is judged only for accounts at least `ACTIVATION_WINDOW` old, so a
    signup from this morning does not read as a failure to activate.
    """
    now = now or utcnow()
    start = now - timedelta(days=days)
    # ponytail: aggregated in Python over one window's events; fine at launch
    # volume, move to a $group pipeline if a window passes ~100k events.
    rows = await ProductEvent.find(
        ProductEvent.timestamp >= start, ProductEvent.timestamp <= now
    ).to_list()

    created: dict[str, datetime] = {}
    first_model: dict[str, datetime] = {}
    counts: Counter[str] = Counter()
    denials: Counter[str] = Counter()
    for row in rows:
        at = as_utc(row.timestamp)
        counts[row.event] += 1
        if row.event == ACCOUNT_CREATED:
            created[row.user_id] = at
        elif row.event == FIRST_MODEL_TRAINED:
            first_model[row.user_id] = at
        elif row.event == QUOTA_DENIED:
            denials[str(row.properties.get("metric"))] += 1

    per_day = Counter(at.date().isoformat() for at in created.values())
    cohort = [u for u, at in created.items() if at <= now - ACTIVATION_WINDOW]
    activated = [
        u for u in cohort
        if u in first_model and first_model[u] - created[u] <= ACTIVATION_WINDOW
    ]
    return {
        "days": days,
        "signups": len(created),
        "signups_per_day": [{"date": d, "count": n} for d, n in sorted(per_day.items())],
        "activation": {
            "cohort": len(cohort),
            "activated": len(activated),
            "rate": len(activated) / len(cohort) if cohort else None,
        },
        "quota_denials_by_metric": dict(denials),
        "checkout_started": counts[CHECKOUT_STARTED],
        "checkout_completed": counts[CHECKOUT_COMPLETED],
        "subscriptions_cancelled": counts[SUBSCRIPTION_CANCELLED],
    }
