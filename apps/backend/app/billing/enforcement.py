"""Plan enforcement on the metered endpoints (#368).

Two pieces that only make sense together:

* `quota(metric)` — a FastAPI dependency that atomically **reserves** a unit
  before the route body runs, and answers **402** when the tenant is at their cap.
* `QuotaRefundMiddleware` — gives the unit back if the request then fails.

**Enforcement is the only thing that counts these metrics.** The routes it guards
do not also call `metering.record()`, or every request would count twice. That is
the trade for getting a hard limit: the reserve has to happen before the work, so
it is the reserve that counts.

Reserving before the work means a request that fails validation has already spent
a unit. Refunding centrally rather than in each route is the difference between
"a free tenant's 20 uploads" and "a free tenant's 20 upload *attempts*, typos
included".

Composes with, and does not replace:

* the #261 invite gate — that decides whether you may be here at all;
* the #151 rate-limit middleware — that bounds requests per second and answers
  429. This bounds units per billing period and answers 402. A tenant can hit
  either independently, and the status codes keep them distinguishable.
"""

import logging
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.nextauth_auth import get_current_user_id
from app.billing import metering
from app.billing.plans import limits_for
from app.models.subscription import PlanTier

logger = logging.getLogger(__name__)

#: Where the reservation is parked for the refund middleware. `request.state` is
#: backed by `scope["state"]`, so the middleware and the endpoint see one dict.
_RESERVATION = "billing_reservation"


def _period_reset() -> str:
    """When the current calendar-month quota rolls over, as an ISO instant.

    Calendar months because `metering.period_key_for` uses them — a tenant on FREE
    has no Stripe period to anchor to. Told to the client so a 402 can say "in 3
    days" instead of leaving them to guess.
    """
    now = datetime.now(UTC)
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    return datetime(year, month, 1, tzinfo=UTC).isoformat()


async def reserve(request: Request, user_id: str, metric: str) -> None:
    """Reserve one unit of `metric` for this tenant, or raise 402.

    Records the reservation on the request so `QuotaRefundMiddleware` can undo it
    if the request does not succeed.
    """
    tier = await metering.effective_tier_for(user_id)
    limit = limits_for(tier).limit_for(metric)

    if await metering.consume(user_id, metric, limit):
        setattr(request.state, _RESERVATION, (user_id, metric, 1))
        return

    used = await metering.usage_for(user_id, metric)
    logger.info(
        "quota denied", extra={"user_id": user_id, "metric": metric, "tier": tier.value}
    )
    raise HTTPException(
        # 402, not 429. The #151 middleware owns 429 for "too fast"; this is "you
        # have used what you pay for", and a client that retries a 429 after a
        # backoff must NOT retry this — nothing changes until the period rolls or
        # the plan does.
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "error": "quota_exceeded",
            "metric": metric,
            "limit": limit,
            "used": used,
            "tier": tier.value,
            "resets_at": _period_reset(),
            "message": (
                f"You have used all {limit} {metric.replace('_', ' ')} included in "
                f"the {tier.value} plan this month."
            ),
            # Only the free tier has somewhere to upgrade *to* from here; telling an
            # enterprise tenant to upgrade is noise.
            "upgrade_available": tier == PlanTier.FREE,
        },
    )


def quota(metric: str):
    """A dependency that enforces `metric` for the authenticated caller."""

    async def dependency(
        request: Request, current_user_id: str = Depends(get_current_user_id)
    ) -> None:
        await reserve(request, current_user_id, metric)

    return dependency


class QuotaRefundMiddleware(BaseHTTPMiddleware):
    """Return a reserved unit when the request it was reserved for fails.

    One place rather than a `try/except` in six routes — routes get added, and the
    one that forgets silently overcharges.

    Refunds on any >= 400, and on an unhandled exception. A 4xx means the work was
    never done; a 5xx means it broke on our side, which is not the tenant's to pay
    for. Anything that returns 2xx keeps its unit even if the real work happens in
    a `BackgroundTask` afterwards — a training run that was accepted and then fails
    still consumed a training run.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            await self._refund(request)
            raise

        if response.status_code >= 400:
            await self._refund(request)
        return response

    @staticmethod
    async def _refund(request: Request) -> None:
        reservation = getattr(request.state, _RESERVATION, None)
        if not reservation:
            return
        user_id, metric, amount = reservation
        # Cleared first: an exception path can reach this twice otherwise, and a
        # double refund is quota minted from nothing.
        setattr(request.state, _RESERVATION, None)
        await metering.refund(user_id, metric, amount)


__all__ = ["quota", "reserve", "QuotaRefundMiddleware"]
