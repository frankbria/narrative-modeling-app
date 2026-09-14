"""#602: the published refund window is enforced, and the enforced number cannot
drift from the published one."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.billing.refunds import (
    REFUND_WINDOW_DAYS,
    is_in_refund_window,
    refund_window_ends_at,
)

_COMPANY_TS = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "lib"
    / "legal"
    / "company.ts"
)


def test_enforced_window_matches_the_terms_page():
    """AC2: the backend constant must equal the frontend `refundWindowDays` the Terms
    page renders — otherwise the published promise and the enforced rule diverge."""
    src = _COMPANY_TS.read_text()
    m = re.search(r"refundWindowDays:\s*(\d+)", src)
    assert m, f"refundWindowDays not found in {_COMPANY_TS}"
    assert int(m.group(1)) == REFUND_WINDOW_DAYS, (
        f"company.ts publishes {m.group(1)} days but the backend enforces "
        f"{REFUND_WINDOW_DAYS}; change both together."
    )


def test_never_paid_is_not_eligible():
    assert is_in_refund_window(None) is False
    assert refund_window_ends_at(None) is None


class TestBoundary:
    """AC4: inside the window, outside it, and exactly on it."""

    def _paid_days_ago(self, days: float) -> datetime:
        return datetime.now(UTC) - timedelta(days=days)

    def test_inside_the_window(self):
        assert is_in_refund_window(self._paid_days_ago(REFUND_WINDOW_DAYS - 1)) is True

    def test_outside_the_window(self):
        assert is_in_refund_window(self._paid_days_ago(REFUND_WINDOW_DAYS + 1)) is False

    def test_exactly_on_the_boundary_is_inclusive(self):
        # first_paid_at + REFUND_WINDOW_DAYS == now exactly -> still eligible.
        now = datetime.now(UTC)
        first_paid = now - timedelta(days=REFUND_WINDOW_DAYS)
        assert is_in_refund_window(first_paid, now=now) is True
        # one microsecond past the boundary -> not eligible.
        assert is_in_refund_window(first_paid, now=now + timedelta(microseconds=1)) is False

    def test_naive_stored_datetime_is_coerced(self):
        # Mongo returns naive datetimes; a naive first_paid_at must not raise and must
        # compare as UTC (CLAUDE.md as_utc note).
        naive = (datetime.now(UTC) - timedelta(days=1)).replace(tzinfo=None)
        assert is_in_refund_window(naive) is True


@pytest.mark.parametrize("days,expected", [(0, True), (7, True), (13.9, True), (14.1, False), (30, False)])
def test_window_across_the_range(days, expected):
    assert is_in_refund_window(datetime.now(UTC) - timedelta(days=days)) is expected


class TestFirstPaidCaptureFromWebhook:
    """AC1: the first settled paid charge is recorded once, from the webhook."""

    @pytest.mark.asyncio
    async def test_first_settled_charge_is_recorded_and_not_moved(self, setup_database):
        from app.api.routes.billing_webhook import _handle
        from app.models.subscription import Subscription
        from app.utils.datetime import as_utc

        user = "refund-user-1"
        t1 = datetime.now(UTC) - timedelta(days=2)
        await _handle(
            "checkout.session.completed",
            {"client_reference_id": user, "payment_status": "paid"},
            event_at=t1,
        )
        sub = await Subscription.find_one(Subscription.user_id == user)
        assert sub is not None and sub.first_paid_at is not None
        first = as_utc(sub.first_paid_at)

        # A later settled charge must NOT move first_paid_at (first-write-wins).
        await _handle(
            "checkout.session.async_payment_succeeded",
            {"client_reference_id": user},
            event_at=datetime.now(UTC),
        )
        sub = await Subscription.find_one(Subscription.user_id == user)
        assert as_utc(sub.first_paid_at) == first

    @pytest.mark.asyncio
    async def test_unsettled_checkout_does_not_stamp(self, setup_database):
        from app.api.routes.billing_webhook import _handle
        from app.models.subscription import Subscription

        user = "refund-user-2"
        # `completed` with payment_status unpaid (async debit not cleared) is not paid.
        await _handle(
            "checkout.session.completed",
            {"client_reference_id": user, "payment_status": "unpaid"},
        )
        sub = await Subscription.find_one(Subscription.user_id == user)
        assert sub is not None and sub.first_paid_at is None

    @pytest.mark.asyncio
    async def test_no_payment_required_checkout_does_not_open_the_window(self, setup_database):
        """A trial / 100%-discounted checkout is entitled (ACTIVE) but is NOT a paid
        charge — it must not start the refund window, and the later real first charge
        must be the one that does (codex, #602)."""
        from app.api.routes.billing_webhook import _handle
        from app.models.subscription import Subscription, SubscriptionStatus
        from app.utils.datetime import as_utc

        user = "refund-user-3"
        t_trial = datetime.now(UTC) - timedelta(days=30)  # long ago; would be "expired" if stamped
        await _handle(
            "checkout.session.completed",
            {"client_reference_id": user, "payment_status": "no_payment_required"},
            event_at=t_trial,
        )
        sub = await Subscription.find_one(Subscription.user_id == user)
        # Entitled, but no paid charge recorded.
        assert sub is not None
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.first_paid_at is None

        # The first real charge (days later) opens the window from THEN, not the trial.
        t_paid = datetime.now(UTC) - timedelta(days=1)
        await _handle(
            "checkout.session.completed",
            {"client_reference_id": user, "payment_status": "paid"},
            event_at=t_paid,
        )
        sub = await Subscription.find_one(Subscription.user_id == user)
        assert sub.first_paid_at is not None
        assert is_in_refund_window(sub.first_paid_at) is True  # within 14 days of the real charge
        assert as_utc(sub.first_paid_at).date() == t_paid.date()
