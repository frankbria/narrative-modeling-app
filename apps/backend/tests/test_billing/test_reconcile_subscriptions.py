"""Coverage for the #458/#510 reconciliation, which bulk-writes real data.

`app/billing/reconcile_subscriptions.py` is the repair path for a missed webhook and
the backfill for every row written before the `_period_end()` fix. It runs against
staging and production, so its comparison logic is worth a test rather than a
one-off manual run. `reconcile()` takes the collection and the Stripe fetch, so it
can be pointed at the test DB with a fake Stripe.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.billing import reconcile_subscriptions
from app.config import settings as _settings
from app.models.subscription import PlanTier, Subscription, SubscriptionStatus
from app.utils.datetime import as_utc

pytestmark = pytest.mark.asyncio


def _load_reconcile():
    return reconcile_subscriptions.reconcile


def _remote(
    status: str,
    period_end: int | None,
    *,
    on_item: bool = True,
    price: str | None = None,
) -> dict:
    """A Stripe subscription payload in the pinned version's shape."""
    obj: dict = {"status": status, "id": "sub_x"}
    item: dict = {}
    if price is not None:
        item["price"] = {"id": price}
    if period_end is not None:
        if on_item:
            item["current_period_end"] = period_end
        else:
            obj["current_period_end"] = period_end
    if item:
        obj["items"] = {"data": [item]}
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

    async def test_a_missed_upgrade_is_repaired(self, setup_database, monkeypatch):
        """The tier drifts on its own. An upgrade keeps the same subscription, the
        same status and the same period end and changes only the price, so a script
        that compared only status and period end would report "everything matches"
        while an ENTERPRISE customer was enforced as PRO."""
        reconcile = _load_reconcile()
        monkeypatch.setattr(_settings, "STRIPE_PRICE_PRO", "price_pro")
        monkeypatch.setattr(_settings, "STRIPE_PRICE_ENTERPRISE", "price_ent")
        period_end = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0)
        await _seed("u-upgrade", plan_tier=PlanTier.PRO, current_period_end=period_end)

        code = await reconcile(
            _collection(),
            lambda _: _remote("active", int(period_end.timestamp()), price="price_ent"),
            apply=True,
        )

        assert code == 0
        sub = await Subscription.find_one(Subscription.user_id == "u-upgrade")
        assert sub is not None
        assert sub.plan_tier == PlanTier.ENTERPRISE
        assert sub.effective_tier == PlanTier.ENTERPRISE

    async def test_unconfigured_prices_never_rewrite_the_tier(
        self, setup_database, monkeypatch
    ):
        """The dangerous half of reusing `tier_for_price`: it falls back to PRO for
        any price it cannot match against a *configured* setting, and an unset
        setting matches nothing. An operator shell carrying only a secret key would
        otherwise resolve every tenant to PRO and `--apply` would write it,
        downgrading every ENTERPRISE customer on the cluster with no error."""
        reconcile = _load_reconcile()
        monkeypatch.setattr(_settings, "STRIPE_PRICE_PRO", "")
        monkeypatch.setattr(_settings, "STRIPE_PRICE_ENTERPRISE", "")
        period_end = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0)
        await _seed(
            "u-unconf", plan_tier=PlanTier.ENTERPRISE, current_period_end=period_end
        )

        await reconcile(
            _collection(),
            lambda _: _remote(
                "active", int(period_end.timestamp()), price="price_whatever"
            ),
            apply=True,
        )

        sub = await Subscription.find_one(Subscription.user_id == "u-unconf")
        assert sub is not None
        assert sub.plan_tier == PlanTier.ENTERPRISE
        # The run announces "status and period end only". `stripe_price_id` is
        # harmless for entitlement, but writing it would make that line untrue.
        assert sub.stripe_price_id is None

    async def test_a_repair_moves_updated_at(self, setup_database):
        """The raw write bypasses Beanie's `_touch()` hook. That is load-bearing:
        `is_entitled` falls back to `updated_at` when no period end is known, so a
        repair that just confirmed with Stripe that a subscription is live would
        otherwise leave the row lapsing on a pre-repair timestamp."""
        reconcile = _load_reconcile()
        stale = (datetime.now(UTC) - timedelta(days=10)).replace(microsecond=0)
        await _seed(
            "u-touch", status=SubscriptionStatus.PAST_DUE, current_period_end=None
        )
        # Written straight to Mongo: `_touch()` fires on insert and would stamp
        # `updated_at` with now, so seeding it through the model is a no-op — which
        # is exactly what made the first version of this test pass with the bump
        # removed.
        await _collection().update_one(
            {"user_id": "u-touch"}, {"$set": {"updated_at": stale}}
        )

        await reconcile(_collection(), lambda _: _remote("active", None), apply=True)

        sub = await Subscription.find_one(Subscription.user_id == "u-touch")
        assert sub is not None
        assert sub.status == SubscriptionStatus.ACTIVE
        assert as_utc(sub.updated_at) > stale + timedelta(days=9)
        assert sub.is_entitled

    async def test_a_payload_without_a_price_leaves_the_tier_alone(
        self, setup_database, monkeypatch
    ):
        """`tier_for_price` falls back to PRO rather than returning None, so passing
        it unconditionally would silently downgrade an ENTERPRISE tenant whenever
        Stripe answered without expanded item data. Same caution the webhook takes."""
        reconcile = _load_reconcile()
        # Configured, so this test fails for the reason it names rather than
        # passing through the unconfigured-prices guard above it.
        monkeypatch.setattr(_settings, "STRIPE_PRICE_PRO", "price_pro")
        monkeypatch.setattr(_settings, "STRIPE_PRICE_ENTERPRISE", "price_ent")
        period_end = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0)
        await _seed(
            "u-noprice", plan_tier=PlanTier.ENTERPRISE, current_period_end=period_end
        )

        await reconcile(
            _collection(),
            lambda _: _remote("active", int(period_end.timestamp())),
            apply=True,
        )

        sub = await Subscription.find_one(Subscription.user_id == "u-noprice")
        assert sub is not None
        assert sub.plan_tier == PlanTier.ENTERPRISE

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

        assert code == 0  # no price in the payload, so the tier is left alone

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

        # Not 0: the row drifted and was not repaired. A run that raced on every row
        # must not report a finished repair — re-running settles it.
        assert code == 1
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


class TestEntryPoint:
    """`main()` refuses only what would make `--apply` write a wrong tier (#598)."""

    def _main(self):
        return reconcile_subscriptions.main

    async def test_an_unset_enterprise_price_still_repairs_status(
        self, setup_database, monkeypatch, capsys
    ):
        """ENTERPRISE is sales-led (ADR-003), so staging runs without its price.

        `reconcile()` then rewrites status and period end only, which is the repair
        staging actually needs; refusing outright left it with no repair at all.
        """
        monkeypatch.setattr(_settings, "STRIPE_SECRET_KEY", "sk_test_x")
        monkeypatch.setattr(_settings, "STRIPE_PRICE_PRO", "price_pro")
        monkeypatch.setattr(_settings, "STRIPE_PRICE_ENTERPRISE", "")
        monkeypatch.setattr("sys.argv", ["reconcile_subscriptions.py"])

        assert await self._main()() == 0
        assert "status and period end only" in capsys.readouterr().out

    async def test_an_unset_pro_price_is_refused(self, monkeypatch, capsys):
        monkeypatch.setattr(_settings, "STRIPE_SECRET_KEY", "sk_test_x")
        monkeypatch.setattr(_settings, "STRIPE_PRICE_PRO", "")
        monkeypatch.setattr(_settings, "STRIPE_PRICE_ENTERPRISE", "price_ent")
        monkeypatch.setattr("sys.argv", ["reconcile_subscriptions.py"])

        assert await self._main()() == 2
        assert "STRIPE_PRICE_PRO" in capsys.readouterr().err

    async def test_stripe_unconfigured_is_refused(self, monkeypatch, capsys):
        monkeypatch.setattr(_settings, "STRIPE_SECRET_KEY", "")
        monkeypatch.setattr("sys.argv", ["reconcile_subscriptions.py"])

        assert await self._main()() == 2
        assert "STRIPE_SECRET_KEY" in capsys.readouterr().err

    async def test_a_missing_database_name_is_refused(self, monkeypatch, capsys):
        """Without `MONGODB_DB` the client would land on a database named `test`
        and report "every subscription matches" about an empty collection."""
        monkeypatch.delenv("MONGODB_DB", raising=False)
        monkeypatch.setattr("sys.argv", ["reconcile_subscriptions.py"])

        assert await self._main()() == 2
        assert "MONGODB_DB" in capsys.readouterr().err

    async def test_a_crash_reports_its_class_and_never_its_message(
        self, setup_database, monkeypatch, capsys
    ):
        """A pymongo error names the Atlas hosts, and the scheduled run's output
        and stderr are quoted in a public issue (#606)."""
        monkeypatch.setattr(_settings, "STRIPE_SECRET_KEY", "sk_test_x")
        monkeypatch.setattr(_settings, "STRIPE_PRICE_PRO", "price_pro")
        monkeypatch.setattr("sys.argv", ["reconcile_subscriptions.py", "--apply"])

        async def unreachable(*_args):
            raise TimeoutError(
                "cluster0-shard-00-00.abc123.mongodb.net:27017: timed out"
            )

        monkeypatch.setattr(reconcile_subscriptions, "reconcile", unreachable)

        assert await self._main()() == 3

        captured = capsys.readouterr()
        assert "did not finish: TimeoutError" in captured.out
        assert "mongodb.net" not in captured.out + captured.err

    async def test_a_malformed_database_address_is_reported_by_class_only(
        self, monkeypatch, capsys
    ):
        """Building the client raises before any read, and pymongo's message can
        quote the address it was given, password included."""
        monkeypatch.setattr(_settings, "STRIPE_SECRET_KEY", "sk_test_x")
        monkeypatch.setattr(_settings, "STRIPE_PRICE_PRO", "price_pro")
        monkeypatch.setenv("MONGODB_URI", "mongodb://svc:hunter2@:not-a-port/")
        monkeypatch.setattr("sys.argv", ["reconcile_subscriptions.py", "--apply"])

        assert await self._main()() == 3

        captured = capsys.readouterr()
        assert "did not finish: " in captured.out
        assert "hunter2" not in captured.out + captured.err


def _sdk_subscription(status: str, period_end: int):
    """What `stripe.Subscription.retrieve` returns: an SDK object, not a dict."""
    import stripe

    return stripe.Subscription.construct_from(
        {
            "id": "sub_x",
            "object": "subscription",
            "status": status,
            "items": {
                "object": "list",
                "data": [
                    {
                        "id": "si_x",
                        "object": "subscription_item",
                        "current_period_end": period_end,
                        "price": {"id": "price_pro", "object": "price"},
                    }
                ],
            },
        },
        "sk_test_x",
    )


class TestTheStripeRead:
    """The read the scheduled run makes (#606), against the SDK's own object.

    Every other test injects a dict. The SDK returns an object that `dict()`
    cannot convert in this major, so the unattended run read every row as
    unreadable while these tests stayed green.
    """

    async def test_a_missed_renewal_is_repaired_from_the_sdk_object(
        self, setup_database, monkeypatch, capsys
    ):
        import stripe

        monkeypatch.setattr(_settings, "STRIPE_SECRET_KEY", "sk_test_x")
        monkeypatch.setattr(_settings, "STRIPE_PRICE_PRO", "price_pro")
        monkeypatch.setattr("sys.argv", ["reconcile_subscriptions.py", "--apply"])
        renewed = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0)
        lapsed = datetime.now(UTC) - timedelta(days=10)
        await _seed("u-renewed", current_period_end=lapsed)
        await _collection().update_one(
            {"user_id": "u-renewed"}, {"$set": {"updated_at": lapsed}}
        )
        before = await Subscription.find_one(Subscription.user_id == "u-renewed")
        assert before is not None and before.effective_tier == PlanTier.FREE
        monkeypatch.setattr(
            stripe.Subscription,
            "retrieve",
            lambda _id: _sdk_subscription("active", int(renewed.timestamp())),
        )

        assert await reconcile_subscriptions.main() == 0

        assert "repaired:                       1" in capsys.readouterr().out
        sub = await Subscription.find_one(Subscription.user_id == "u-renewed")
        assert sub is not None
        assert as_utc(sub.current_period_end) == renewed
        assert sub.effective_tier == PlanTier.PRO

    async def test_a_stripe_failure_reads_as_unreadable_and_names_its_class(
        self, setup_database, monkeypatch, capsys
    ):
        import stripe

        monkeypatch.setattr(_settings, "STRIPE_SECRET_KEY", "sk_test_x")
        monkeypatch.setattr(_settings, "STRIPE_PRICE_PRO", "price_pro")
        monkeypatch.setattr("sys.argv", ["reconcile_subscriptions.py", "--apply"])
        await _seed("u-limited")

        def limited(_id):
            raise stripe.RateLimitError("slow down, sub_x")

        monkeypatch.setattr(stripe.Subscription, "retrieve", limited)

        assert await reconcile_subscriptions.main() == 1

        out = capsys.readouterr().out
        assert "RateLimitError" in out
        assert "unreadable from stripe:         1" in out
        assert "sub_x" not in out, "the output lands in a public issue"
