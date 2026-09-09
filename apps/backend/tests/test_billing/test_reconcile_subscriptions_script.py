"""Coverage for the #458/#510 reconciliation script, which bulk-writes real data.

`scripts/reconcile_subscriptions.py` is the repair path for a missed webhook and
the backfill for every row written before the `_period_end()` fix. It runs against
staging and production, so its comparison logic is worth a test rather than a
one-off manual run. `reconcile()` takes the collection and the Stripe fetch, so it
can be pointed at the test DB with a fake Stripe.
"""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.models.subscription import PlanTier, Subscription, SubscriptionStatus

pytestmark = pytest.mark.asyncio

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reconcile_subscriptions.py"


def _load_reconcile():
    spec = importlib.util.spec_from_file_location("reconcile_subscriptions", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.reconcile


def _remote(status: str, period_end: int | None, *, on_item: bool = True) -> dict:
    """A Stripe subscription payload in the pinned version's shape."""
    obj: dict = {"status": status, "id": "sub_x"}
    if period_end is None:
        return obj
    if on_item:
        obj["items"] = {"data": [{"current_period_end": period_end}]}
    else:
        obj["current_period_end"] = period_end
    return obj


async def _seed(user_id: str, **kwargs) -> Subscription:
    kwargs.setdefault("plan_tier", PlanTier.PRO)
    kwargs.setdefault("status", SubscriptionStatus.ACTIVE)
    kwargs.setdefault("stripe_subscription_id", "sub_x")
    return await Subscription(user_id=user_id, **kwargs).insert()


def _collection():
    return Subscription.get_motor_collection()


class TestReconcile:
    async def test_a_null_period_end_is_backfilled(self, setup_database):
        """The #510 symptom: the row is otherwise correct, but the field nothing
        ever populated has to be filled in before #458's expiry check judges it."""
        reconcile = _load_reconcile()
        await _seed("u-backfill", current_period_end=None)
        future = int((datetime.now(UTC) + timedelta(days=30)).timestamp())

        code = await reconcile(
            _collection(), lambda _: _remote("active", future), apply=True
        )

        assert code == 0
        sub = await Subscription.find_one(Subscription.user_id == "u-backfill")
        assert sub is not None and sub.current_period_end is not None
        assert sub.is_entitled

    async def test_a_stale_status_is_rewritten_from_stripe(self, setup_database):
        """The missed-webhook case in the dangerous direction: Stripe has given up
        on this customer and the local row still says ACTIVE."""
        reconcile = _load_reconcile()
        await _seed("u-stale", current_period_end=datetime.now(UTC))

        await reconcile(_collection(), lambda _: _remote("unpaid", None), apply=True)

        sub = await Subscription.find_one(Subscription.user_id == "u-stale")
        assert sub is not None
        assert sub.status == SubscriptionStatus.CANCELED
        assert not sub.is_entitled

    async def test_a_matching_row_is_not_counted_as_drift(self, setup_database):
        """The stored datetime comes back from Mongo naive. Comparing it against
        the aware value from Stripe without coercing would report every row on the
        cluster as drifted, every run — a repair script that always finds work is
        one nobody reads the output of."""
        reconcile = _load_reconcile()
        period_end = datetime.now(UTC) + timedelta(days=30)
        # Truncate to whole seconds: Stripe deals in epoch seconds, so a stored
        # microsecond component would be a genuine (if uninteresting) difference.
        period_end = period_end.replace(microsecond=0)
        await _seed("u-match", current_period_end=period_end)

        code = await reconcile(
            _collection(),
            lambda _: _remote("active", int(period_end.timestamp())),
            apply=False,
        )

        assert code == 0

    async def test_a_dry_run_reports_drift_without_writing(self, setup_database):
        reconcile = _load_reconcile()
        await _seed("u-dry", current_period_end=None)

        code = await reconcile(
            _collection(), lambda _: _remote("canceled", None), apply=False
        )

        assert code == 1
        sub = await Subscription.find_one(Subscription.user_id == "u-dry")
        assert sub is not None
        assert sub.status == SubscriptionStatus.ACTIVE

    async def test_one_unreadable_subscription_does_not_stop_the_rest(
        self, setup_database
    ):
        """A deleted test subscription in the middle of the cursor must not leave
        every row behind it unrepaired."""
        reconcile = _load_reconcile()
        await _seed("u-gone", stripe_subscription_id="sub_gone")
        await _seed("u-fine", stripe_subscription_id="sub_fine")
        future = int((datetime.now(UTC) + timedelta(days=30)).timestamp())

        def fetch(subscription_id):
            return None if subscription_id == "sub_gone" else _remote("unpaid", future)

        code = await reconcile(_collection(), fetch, apply=True)

        assert code == 1  # unreadable rows keep the exit status non-zero
        fine = await Subscription.find_one(Subscription.user_id == "u-fine")
        assert fine is not None
        assert fine.status == SubscriptionStatus.CANCELED

    async def test_a_row_that_changed_under_the_script_is_not_overwritten(
        self, setup_database
    ):
        """A webhook can land between the Stripe read and the write. That webhook is
        newer than what the script fetched, so overwriting it would undo a real
        cancellation and leave the row wrong until somebody ran this again.

        Driven through a collection whose cursor hands back a stale `updated_at` —
        which is exactly what the real cursor holds once a webhook has written since
        the row was read — so the script's own conditional write is what is under
        test, not a hand-rolled query.
        """
        reconcile = _load_reconcile()
        await _seed("u-raced", status=SubscriptionStatus.CANCELED)

        collection = _collection()

        class StaleCursorCollection:
            """Delegates everything, but ages every row the cursor yields."""

            def find(self, *args, **kwargs):
                inner = collection.find(*args, **kwargs)

                async def aged():
                    async for row in inner:
                        row["updated_at"] = row["updated_at"] - timedelta(seconds=1)
                        yield row

                return aged()

            def __getattr__(self, name):
                return getattr(collection, name)

        code = await reconcile(
            StaleCursorCollection(), lambda _: _remote("active", None), apply=True
        )

        assert code == 0
        fresh = await Subscription.find_one(Subscription.user_id == "u-raced")
        assert fresh is not None
        assert fresh.status == SubscriptionStatus.CANCELED

    async def test_rows_that_never_reached_stripe_are_skipped(self, setup_database):
        """A FREE tenant has no `stripe_subscription_id`; calling Stripe for one
        would be a guaranteed error per row."""
        reconcile = _load_reconcile()
        await _seed("u-free", stripe_subscription_id=None, plan_tier=PlanTier.FREE)

        def fetch(_):  # pragma: no cover - reaching this is the failure
            raise AssertionError("should not have been asked about a FREE tenant")

        assert await reconcile(_collection(), fetch, apply=False) == 0
