"""Recording and reading per-tenant usage (#369).

The read path here is what the plan-enforcement dependency (#368) consumes.

Two properties matter more than anything else in this module:

* **Increments are atomic.** A single `$inc` upsert, not read-modify-write. Two
  concurrent predictions must count as two.
* **`remaining()` is NOT an atomic check-and-consume.** It composes two independent
  reads, so concurrent requests can all see quota available before any of them
  calls `record()` — a bounded overshoot past the limit under load. Fine for
  display, and acceptable for a soft billing limit, but #368 must decide that
  explicitly rather than inherit an assumption that this gives a hard guarantee.
  Closing the window would need a conditional `$inc` that both checks and consumes
  in one operation, which is a different primitive from the one here.
* **Recording never breaks the request on a storage failure.** A tenant's
  prediction succeeding and then 500-ing because a counter could not be written is
  worse than a slightly under-counted period, so `record()` swallows storage errors
  and logs them. It still raises on an unknown metric, which is a programmer error
  rather than a runtime condition. The *enforcement* side gets no latitude at all —
  see `usage_for`.
"""

import logging
from datetime import UTC, datetime

from pymongo.errors import DuplicateKeyError

from app.billing.plans import METERED_METRICS, UNLIMITED, limits_for
from app.models.subscription import PlanTier, Subscription
from app.models.usage import UsageRecord

logger = logging.getLogger(__name__)


def period_key_for(moment: datetime | None = None) -> str:
    """The billing period a moment falls in, as `YYYY-MM`.

    Calendar months rather than the subscription's own anchor date, deliberately:
    a tenant on FREE has no Stripe period at all, and enforcement has to work for
    them too. Aligning everyone to calendar months means one rule, and rollover is
    then just "the key changed" — no scheduled job resets anything, so there is no
    reset that can fail to run.
    """
    now = moment or datetime.now(UTC)
    return f"{now.year:04d}-{now.month:02d}"


async def record(user_id: str, metric: str, amount: int = 1) -> None:
    """Add `amount` to a tenant's count for `metric` in the current period.

    Never raises **on a storage failure** — that is the promise, and it is narrower
    than "never raises". A failure to meter must not fail the request being metered:
    the user has already had the work done, and refusing them the result because a
    counter did not increment helps nobody.

    An unknown `metric` DOES raise. It is a programmer error, not a runtime
    condition — there is no request to protect from it, and swallowing it would mean
    a typo'd metric name silently meters nothing at all. (An earlier version of this
    docstring said "Never raises" flatly, which contradicted the line below it.)
    """
    if metric not in METERED_METRICS:
        raise KeyError(f"unknown metered metric: {metric}")
    if amount <= 0:
        return

    now = datetime.now(UTC)
    selector = {
        "user_id": user_id,
        "period_key": period_key_for(now),
        "metric": metric,
    }
    # Atomic: two concurrent predictions count as two, where a read-modify-write
    # would lose one.
    update = {
        "$inc": {"units": amount},
        "$set": {"updated_at": now},
        "$setOnInsert": {"created_at": now},
    }

    try:
        await UsageRecord.get_motor_collection().update_one(
            selector, update, upsert=True
        )
    except DuplicateKeyError:
        # The FIRST concurrent writes for a new (user_id, period, metric) can race
        # on the unique index: both find nothing, both try to insert, one loses.
        # Mongo often retries this internally but does not guarantee it. Handled
        # separately from a genuine outage because swallowing it would silently
        # under-count — the exact failure this module exists to avoid.
        #
        # Retry the SAME operation, upsert included. Dropping upsert here would
        # rely on the document still existing — true for this race, but a silent
        # no-op if anything ever removed it in between (a period cleanup, an
        # erasure request). Keeping upsert makes the retry idempotent regardless.
        try:
            await UsageRecord.get_motor_collection().update_one(
                selector, update, upsert=True
            )
        except DuplicateKeyError:
            # A SECOND collision is not the ordinary race — an idempotent upsert
            # should not lose twice. Logged at error with its own message so it is
            # distinguishable in a log search, rather than folded in with routine
            # storage failures. Still swallowed: the promise to the caller is the
            # same, and a request must not fail over a counter.
            logger.error(
                "usage record collided twice; count may be short",
                extra={"user_id": user_id, "metric": metric, "amount": amount},
            )
        except Exception:
            logger.exception(
                "failed to record usage after a duplicate-key retry",
                extra={"user_id": user_id, "metric": metric},
            )
    except Exception:
        logger.exception(
            "failed to record usage", extra={"user_id": user_id, "metric": metric}
        )


async def usage_for(user_id: str, metric: str, moment: datetime | None = None) -> int:
    """How much of `metric` this tenant has used in the current period.

    Unlike `record`, this does NOT swallow errors. Enforcement reads this to decide
    whether to allow a request; returning 0 on a storage failure would fail *open*
    and hand out unlimited quota, which is the whole reason the #151 rate-limit
    buckets were unsuitable for billing.

    The metric is validated for the same reason: a typo'd or drifted name would
    otherwise read back as 0 used, which is the same fail-open in a quieter form.
    """
    if metric not in METERED_METRICS:
        raise KeyError(f"unknown metered metric: {metric}")

    doc = await UsageRecord.find_one(
        UsageRecord.user_id == user_id,
        UsageRecord.period_key == period_key_for(moment),
        UsageRecord.metric == metric,
    )
    return doc.units if doc else 0


async def usage_summary(
    user_id: str, moment: datetime | None = None
) -> dict[str, int]:
    """Every metered counter for this tenant in the current period.

    Metrics with no record read as 0 rather than being absent, so a caller can
    render a usage panel without special-casing a tenant who has not used a feature.
    """
    period = period_key_for(moment)
    docs = await UsageRecord.find(
        UsageRecord.user_id == user_id, UsageRecord.period_key == period
    ).to_list()
    counts = {d.metric: d.units for d in docs}
    return {metric: counts.get(metric, 0) for metric in METERED_METRICS}


async def effective_tier_for(user_id: str) -> PlanTier:
    """The tier to enforce against, FREE when there is no entitled subscription.

    Absence is not an error: a tenant who never subscribed simply has no document,
    which is why enforcement does not depend on a backfill having run (#366).
    """
    sub = await Subscription.find_one(Subscription.user_id == user_id)
    return sub.effective_tier if sub else PlanTier.FREE


async def remaining(user_id: str, metric: str) -> int | None:
    """Units of `metric` left this period, or None when the tier is unlimited.

    Validates via `limit_for` and `usage_for`, both of which raise on an unknown
    metric rather than reporting a full quota.

    NOT an atomic check-and-consume — see the TOCTOU note in the module docstring
    before building hard enforcement on this.
    """
    limit = limits_for(await effective_tier_for(user_id)).limit_for(metric)
    if limit == UNLIMITED:
        return None
    return max(0, limit - await usage_for(user_id, metric))
