"""Per-tenant, per-period usage counters (#369).

#369 asks whether the existing rate-limit buckets (#151) can be reused. **They
cannot**, for two reasons that are properties of that design rather than gaps in it:

* `RedisRateLimitStore` **fails open** on any Redis error, deliberately, so a cache
  outage never takes the API down. That is right for rate limiting and wrong for
  billing — a Redis blip would hand out unlimited quota.
* Its counters are fixed windows with a TTL measured in seconds and are discarded
  when they expire. Billing needs a durable record that survives the period, both to
  enforce against and to answer "what did this tenant actually use".

So usage lives in Mongo alongside the subscription it bills against, and fails
*closed* by simply not existing — an absent record reads as zero used.
"""

from datetime import UTC, datetime

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class UsageRecord(Document):
    """One tenant's count of one metric within one billing period.

    Deliberately one document per `(user_id, period_key, metric)` rather than a
    single document per tenant holding a dict of counters: concurrent predictions
    and training runs increment independently, and separate documents let Mongo
    apply `$inc` to each without the two contending on one document's revision.
    """

    user_id: str = Field(description="Owning tenant")
    period_key: str = Field(
        description="Billing period this count belongs to, e.g. '2026-08'"
    )
    metric: str = Field(description="One of app.billing.plans.METERED_METRICS")

    # Named `units`, not `count`: Beanie's FindInterface already defines `count()`,
    # so a field of that name shadows the method — mypy rejects it outright, and
    # `ColumnStats` carries a runtime warning for exactly this clash.
    units: int = Field(default=0, description="Units consumed in this period")

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "usage_records"
        indexes = [
            # Unique so concurrent `$inc` upserts converge on one document rather
            # than racing to create several — which would under-count, and
            # under-counting is the direction that gives usage away for free.
            IndexModel(
                [
                    ("user_id", ASCENDING),
                    ("period_key", ASCENDING),
                    ("metric", ASCENDING),
                ],
                unique=True,
                name="user_id_1_period_key_1_metric_1",
            ),
        ]
