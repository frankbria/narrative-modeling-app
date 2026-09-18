"""Global daily AI spend ceiling (#768).

Per-tenant ``ai_calls`` quotas bound one account; nothing bounded the sum, so the
aggregate bill scaled with the number of accounts — and one person with a script
and disposable OAuth accounts sets that number. This is the backstop: one
all-tenant counter of model calls per UTC day, capped at ``AI_CALLS_DAILY_CEILING``.

It is enforced at the one place every model call passes through, the ``openai*``
circuit breakers (``app/utils/circuit_breaker.py``), once per logical call. Past
the ceiling the breaker raises ``AICeilingReached``, a ``CircuitBreakerOpen``, so
every service takes the rule-based fallback it already has (#461) and every route
releases the tenant's unit because no model ran. That includes the post-upload
summaries, which carry no ``ai_calls`` quota but do reach the same breaker.

The counter is a ``UsageRecord`` under a sentinel tenant with a ``YYYY-MM-DD``
period key, reserved through ``metering.consume`` — the same conditional ``$inc``
the tenant quotas use, so it is atomic across workers and fails CLOSED: if the
counter cannot be written, the model is not called and the fallback is served.
"""

import logging
from datetime import UTC, datetime

from app.billing import metering
from app.billing.plans import _env_positive_int
from app.middleware.metrics import ai_calls_admitted, ai_ceiling_denials

logger = logging.getLogger(__name__)

#: Not a user id anything else can produce (NextAuth ids are ObjectIds / UUIDs).
GLOBAL_TENANT = "__global__"

#: Sized in ADR-003 ("Aggregate exposure"): 500 calls/day at the worst-case
#: $0.12/call is a $60/day ($1 800/month) ceiling on the whole AI bill.
DEFAULT_DAILY_CEILING = 500
AI_CALLS_DAILY_CEILING = _env_positive_int("AI_CALLS_DAILY_CEILING", DEFAULT_DAILY_CEILING)

_alerted_day: str | None = None


def day_key(moment: datetime | None = None) -> str:
    """The UTC day a moment falls in, as ``YYYY-MM-DD``."""
    return (moment or datetime.now(UTC)).strftime("%Y-%m-%d")


async def admit() -> bool:
    """Spend one unit of today's global budget. False once it is gone."""
    global _alerted_day
    day = day_key()
    if await metering.consume(GLOBAL_TENANT, "ai_calls", AI_CALLS_DAILY_CEILING, period_key=day):
        ai_calls_admitted.inc()
        return True

    ai_ceiling_denials.inc()
    # ERROR once per day per worker, so an alert fires without a log line (and a
    # Sentry event) for every refused call for the rest of the day.
    if _alerted_day != day:
        _alerted_day = day
        logger.error(
            "Global AI ceiling reached: %d model calls today (AI_CALLS_DAILY_CEILING); "
            "every AI feature is serving its rule-based fallback until 00:00 UTC",
            AI_CALLS_DAILY_CEILING,
        )
    return False
