"""Recording and reading per-tenant usage (#369).

The read path here is what the plan-enforcement dependency (#368) consumes.

Two properties matter more than anything else in this module:

* **Increments are atomic.** A single `$inc` upsert, not read-modify-write. Two
  concurrent predictions must count as two.
* **`remaining()` is NOT an atomic check-and-consume.** It composes two independent
  reads, so concurrent requests can all see quota available before any of them
  calls `record()`. It is a DISPLAY primitive — the billing page's usage bars —
  and enforcement must not be built on it.

  #368 decided this rather than inheriting it: `consume()` below closes the window
  with a conditional `$inc` that checks and consumes in one operation, so the
  limits are hard rather than a bounded overshoot.
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


async def consume(user_id: str, metric: str, limit: int, amount: int = 1) -> bool:
    """Reserve `amount` if it fits under `limit`. True when reserved.

    The check and the consume are ONE operation, which is what `remaining()` +
    `record()` cannot be. The filter carries the condition (`units <= limit -
    amount`) and the update carries the consume, so there is no window between
    them for a concurrent caller to slip through.

    The insert case rides on the unique index. With `upsert=True`, a tenant with
    no record yet gets one created. A tenant whose record is already at the limit
    fails the filter, so the upsert tries to *insert* instead — and collides with
    the unique `(user_id, period_key, metric)` index. That `DuplicateKeyError` is
    the denial, and it is why this works without a preceding read.

    Fails CLOSED. Unlike `record()`, a storage error here denies rather than
    swallowing: this is the enforcement path, and an outage that hands out
    unlimited quota is the failure mode the whole module is built to avoid.
    """
    if metric not in METERED_METRICS:
        raise KeyError(f"unknown metered metric: {metric}")

    if limit == UNLIMITED:
        # Nothing to check, but still counted — usage reporting and any future
        # overage pricing both need the number.
        await record(user_id, metric, amount)
        return True

    if amount <= 0:
        return True

    if amount > limit:
        # Must be caught BEFORE the query. `limit - amount` goes negative here, no
        # existing record can satisfy it, and the upsert would take the insert path
        # and create a record above a limit it never checked. `limit == 0` is the
        # same bug at amount=1.
        return False

    now = datetime.now(UTC)
    selector = {
        "user_id": user_id,
        "period_key": period_key_for(now),
        "metric": metric,
        "units": {"$lte": limit - amount},
    }
    update = {
        "$inc": {"units": amount},
        "$set": {"updated_at": now},
        "$setOnInsert": {"created_at": now},
    }

    try:
        await UsageRecord.get_motor_collection().update_one(
            selector, update, upsert=True
        )
        return True
    except DuplicateKeyError:
        # AMBIGUOUS, and reading it as "full" is wrong. The filter missed for one of
        # two reasons: the record is genuinely at the limit, OR a concurrent writer
        # inserted it between our filter and our insert — the same first-write race
        # `record()` retries. Denying both turns a normal cold-start race into a
        # spurious 402 for a tenant with quota to spare.
        #
        # The retry disambiguates without a read: the record exists by now, so the
        # same conditional update succeeds only if there is genuinely room. Still
        # one operation, still no TOCTOU.
        #
        # `upsert=False` on the retry, and that is the whole point of it. Retrying
        # WITH upsert would take the insert path again whenever the tenant is
        # genuinely full, collide again, and make the ordinary at-the-cap case
        # arrive as an exception — two round-trips and a warning per capped request.
        # Without upsert, a filter miss simply reports `matched_count == 0`, which
        # is exactly the "full" signal we want and cannot be confused with a race.
        try:
            result = await UsageRecord.get_motor_collection().update_one(
                selector, update
            )
        except DuplicateKeyError:
            # Not reachable without an upsert — there is no insert to collide. Kept
            # so an unexpected one denies rather than escaping as a 500.
            logger.warning(
                "quota reservation collided twice; denying",
                extra={"user_id": user_id, "metric": metric},
            )
            return False
        except Exception:
            logger.exception(
                "failed to reserve quota on retry; denying",
                extra={"user_id": user_id, "metric": metric},
            )
            return False

        if result.matched_count or result.upserted_id:
            return True

        # Filter missed against an existing record: genuinely at the cap. Logged at
        # debug, not warning — a tenant sitting on their limit should not fill the
        # log with it.
        logger.debug("quota exhausted", extra={"user_id": user_id, "metric": metric})
        return False
    except Exception:
        logger.exception(
            "failed to reserve quota; denying",
            extra={"user_id": user_id, "metric": metric},
        )
        return False


async def refund(
    user_id: str, metric: str, amount: int = 1, period_key: str | None = None
) -> None:
    """Return reserved units after the work they were reserved for failed.

    Enforcement consumes at admission, so a request that then 4xxs would otherwise
    burn quota it never used — a free tenant losing their 20 uploads to malformed
    files. Refunding centrally beats each route remembering to.

    `period_key` is the period the unit was TAKEN from, and callers should pass it.
    Recomputing it here would misfire on a request that reserves just before a UTC
    month rollover and fails just after: the refund lands on the new month, which
    was never charged, and last month's unit stays burned.

    Clamped at zero via a `units >= amount` filter: a refund with nothing reserved
    must not mint quota, which would turn every failed request into free credit.
    Swallows storage errors for the same reason `record()` does — a failed refund
    must not turn a 4xx into a 500.
    """
    if metric not in METERED_METRICS:
        raise KeyError(f"unknown metered metric: {metric}")
    if amount <= 0:
        return

    try:
        await UsageRecord.get_motor_collection().update_one(
            {
                "user_id": user_id,
                "period_key": period_key or period_key_for(),
                "metric": metric,
                "units": {"$gte": amount},
            },
            {"$inc": {"units": -amount}, "$set": {"updated_at": datetime.now(UTC)}},
        )
    except Exception:
        logger.exception(
            "failed to refund quota", extra={"user_id": user_id, "metric": metric}
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
