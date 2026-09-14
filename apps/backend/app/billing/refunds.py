"""The published refund window, enforced (#602).

`/legal/terms#refunds` commits to a full refund if a customer asks within
``refundWindowDays`` of their first paid charge. That number lives in the frontend
(`apps/frontend/lib/legal/company.ts`) because the Terms page renders it; this module
holds the backend copy, and `tests/test_billing/test_refund_window.py` fails if the two
drift — so the published number and the enforced number stay one value.

Eligibility is computed from ``Subscription.first_paid_at`` (set once by the Stripe
webhook), never inferred by reading Stripe at request time.
"""

from datetime import UTC, datetime, timedelta

from app.utils.datetime import as_utc

#: Days after the first paid charge during which a full refund is offered. MUST equal
#: ``refundWindowDays`` in ``apps/frontend/lib/legal/company.ts`` (guarded by a test).
REFUND_WINDOW_DAYS = 14


def refund_window_ends_at(first_paid_at: datetime | None) -> datetime | None:
    """The instant the refund window closes, or ``None`` if the tenant has no
    recorded first paid charge (never paid → not applicable)."""
    if first_paid_at is None:
        return None
    return as_utc(first_paid_at) + timedelta(days=REFUND_WINDOW_DAYS)


def is_in_refund_window(
    first_paid_at: datetime | None, now: datetime | None = None
) -> bool:
    """Whether a tenant whose first paid charge was ``first_paid_at`` is still inside
    the refund window at ``now`` (default: current UTC).

    Inclusive at the exact boundary — "within 14 days" read in the customer's favour.
    ``first_paid_at`` and ``now`` both go through ``as_utc`` because Mongo hands datetimes
    back naive; comparing a naive stored value against an aware ``now`` would otherwise
    raise or silently drift by the deployment's offset (CLAUDE.md).
    """
    ends = refund_window_ends_at(first_paid_at)
    if ends is None:
        return False
    now = now if now is not None else datetime.now(UTC)
    return as_utc(now) <= ends
