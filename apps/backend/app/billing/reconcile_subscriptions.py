"""Re-read every Subscription from Stripe and rewrite what has drifted (#458, #510, #606).

Webhook delivery is the primary sync mechanism, and Stripe gives up retrying an
event after about three days. The expiry check makes a missed *lapse* fail closed
on its own. A missed *renewal* fails the other way: a paying customer loses their
tier once the stale period end goes past the grace window, and nothing but
re-reading Stripe can repair that. This is that repair, and the backfill for rows
whose `current_period_end` was never written (#510).

**What runs it.** `.github/workflows/subscription-reconcile.yml`, daily, with
`--apply`, inside the staging backend container; a run that does not exit 0 opens
an alert issue (#606). The service itself still has no scheduler. It lives under
`app/` rather than `scripts/` only because the runtime image ships nothing else.
By hand, after a Stripe incident, from `apps/backend`:

    MONGODB_URI=... MONGODB_DB=... STRIPE_SECRET_KEY=... STRIPE_PRICE_PRO=... \
        PYTHONPATH=. uv run python -m app.billing.reconcile_subscriptions [--apply]

Read-only without `--apply`. Reports counts and exception class names only (no
user ids, no Stripe ids), because the scheduled run's output lands in a public
issue.

Without `STRIPE_PRICE_ENTERPRISE` (unset wherever no sales-led deal is sold
through checkout, ADR-003) the tier is left alone and only status and period end
are repaired: an unmatched price resolves to PRO, so a tier rewrite would
downgrade any ENTERPRISE customer.

Exit status: 0 when every row matches Stripe (after repairs, under `--apply`),
1 when a row is unreadable, raced, or (read-only) drifted, 2 when a required
setting is missing, 3 when the run could not finish (the database was unreachable).

A sales-led ENTERPRISE deal sold on its own price must use the price in
`STRIPE_PRICE_ENTERPRISE`: any other price resolves to PRO, here as in the
webhook, and this runs every day.
"""

import asyncio
import os
import sys
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.api.routes.billing_webhook import _period_end, _price_id, tier_for_price
from app.billing import stripe_client
from app.models.subscription import SubscriptionStatus
from app.utils.datetime import as_utc

Row = Mapping[str, Any]
Fetch = Callable[[str], dict[str, Any] | None]


async def main() -> int:
    apply = "--apply" in sys.argv[1:]

    uri, db_name = os.getenv("MONGODB_URI"), os.getenv("MONGODB_DB")
    if not uri or not db_name:
        print("Set MONGODB_URI and MONGODB_DB.", file=sys.stderr)
        return 2
    if not stripe_client.is_configured():
        print("Set STRIPE_SECRET_KEY: this reads from Stripe.", file=sys.stderr)
        return 2
    # Required like the app requires it. An unset ENTERPRISE price is not refused:
    # `reconcile()` then leaves every tier alone, because `tier_for_price` would
    # resolve an unmatched price to PRO and `--apply` would downgrade ENTERPRISE.
    if not stripe_client.setting("STRIPE_PRICE_PRO"):
        print(
            "Set STRIPE_PRICE_PRO: the price billing sells, as the app requires.",
            file=sys.stderr,
        )
        return 2

    return await _reconcile_database(uri, db_name, apply)


async def _reconcile_database(uri: str, db_name: str, apply: bool) -> int:
    """Run `reconcile()` against the database; 3 when it could not finish.

    The class name only: a pymongo error names the cluster's hosts, and the
    scheduled run's output and stderr are quoted in a public issue.
    """
    try:
        # Built inside the boundary: a malformed address raises here, and
        # pymongo's message can quote it.
        client: AsyncIOMotorClient[dict[str, Any]] = AsyncIOMotorClient(uri)
        try:
            return await reconcile(
                client[db_name]["subscriptions"], _fetch_from_stripe, apply
            )
        finally:
            client.close()
    except Exception as exc:  # noqa: BLE001 - reported by class, see above
        print(f"the reconciliation did not finish: {type(exc).__name__}")
        return 3


def _fetch_from_stripe(subscription_id: str) -> dict[str, Any] | None:
    """The live subscription, or None if Stripe will not give it to us.

    A single unreadable subscription must not abort a bulk repair: one deleted
    test subscription would otherwise stop every real row behind it from being
    fixed. `to_dict()`, never `dict()`: the SDK object is not a dict in this
    major and `dict()` raises on it, which read every row as unreadable (#606).

    shortcut: one blocking call per row, and a rate limit reads as unreadable;
    upgrade (batching, backoff) when the subscriber count is no longer trivial (#1213).
    """
    try:
        stripe = stripe_client._client()
        return stripe.Subscription.retrieve(subscription_id).to_dict()
    except Exception as exc:  # noqa: BLE001 - any Stripe failure is per-row, not fatal
        print(f"  could not read one subscription from Stripe: {type(exc).__name__}")
        return None


def _tier_changes(
    row: Row, price: str | None, tiers_resolvable: bool
) -> dict[str, Any]:
    """The tier drifts on its own: an upgrade keeps the same subscription, the same
    status and the same period end, and changes only the price. A missed
    `customer.subscription.updated` there leaves a customer paying for ENTERPRISE
    and enforced as PRO.

    No price means leave the tier alone, exactly as the webhook does:
    `tier_for_price` falls back to PRO rather than returning None, so passing it
    unconditionally would silently downgrade an ENTERPRISE tenant whenever Stripe
    answered without expanded item data. `stripe_price_id` is gated on the same
    flag: the run announces that only status and period end will move, and a
    price write would make that untrue.
    """
    if not (price and tiers_resolvable):
        return {}
    wanted = {"plan_tier": tier_for_price(price).value, "stripe_price_id": price}
    return {field: value for field, value in wanted.items() if value != row.get(field)}


def _period_end_change(row: Row, period_end: datetime | None) -> dict[str, Any]:
    """A null period end is the #510 symptom, so "unset locally, set remotely"
    counts as drift. The stored value comes back naive: comparing it directly
    against the aware value from Stripe would mark every row as drifted, forever.
    """
    stored = row.get("current_period_end")
    if period_end is None or (stored is not None and as_utc(stored) == period_end):
        return {}
    return {"current_period_end": period_end}


def _drift(row: Row, remote: dict[str, Any], tiers_resolvable: bool) -> dict[str, Any]:
    """The fields of `row` that Stripe disagrees with, as the values to write."""
    status = SubscriptionStatus.from_stripe(remote.get("status", "")).value
    changes: dict[str, Any] = {} if status == row.get("status") else {"status": status}
    changes |= _tier_changes(row, _price_id(remote), tiers_resolvable)
    changes |= _period_end_change(row, _period_end(remote))
    return changes


async def _reconcile_row(
    collection: AsyncIOMotorCollection[dict[str, Any]],
    fetch: Fetch,
    row: Row,
    tiers_resolvable: bool,
    apply: bool,
) -> str:
    """What happened to one row: unreadable, matched, drifted, repaired or raced."""
    remote = fetch(row["stripe_subscription_id"])
    if remote is None:
        return "unreadable"
    changes = _drift(row, remote, tiers_resolvable)
    if not changes:
        return "matched"
    if not apply:
        return "drifted"
    # The raw `update_one` below bypasses Beanie, so the model's `_touch()` hook
    # never fires. `is_entitled` falls back to `updated_at` when no period end is
    # known, so a repair that confirmed with Stripe that a subscription is live
    # would otherwise leave the row lapsing on a timestamp from before the repair.
    changes["updated_at"] = datetime.now(UTC)
    # Conditional on the row not having moved since it was read. A webhook can
    # land between the Stripe read and this write, and it is newer than what was
    # fetched, so writing over it would undo a real cancellation. `_touch()` bumps
    # `updated_at` on every Beanie save, so a lost race matches nothing and is
    # counted rather than applied.
    result = await collection.update_one(
        {"_id": row["_id"], "updated_at": row.get("updated_at")},
        {"$set": changes},
    )
    return "repaired" if result.modified_count else "raced"


async def reconcile(
    collection: AsyncIOMotorCollection[dict[str, Any]], fetch: Fetch, apply: bool
) -> int:
    """Compare each row against Stripe; rewrite what drifted under `apply`.

    `fetch` is injected so this can be tested against a fake without a Stripe
    account, and so the caller decides what "read from Stripe" means.
    """
    # Defence in depth behind `main()`'s check: this is the tested entry point and
    # can be called directly, and the failure it guards against rewrites paying
    # customers' tiers with no error.
    tiers_resolvable = bool(
        stripe_client.setting("STRIPE_PRICE_PRO")
        and stripe_client.setting("STRIPE_PRICE_ENTERPRISE")
    )
    if not tiers_resolvable:
        print("STRIPE_PRICE_* unset: reconciling status and period end only.")

    outcomes: Counter[str] = Counter()
    async for row in collection.find({"stripe_subscription_id": {"$type": "string"}}):
        outcomes[
            await _reconcile_row(collection, fetch, row, tiers_resolvable, apply)
        ] += 1

    drifted = outcomes["drifted"] + outcomes["repaired"] + outcomes["raced"]
    print(f"subscriptions with a stripe id: {outcomes.total()}")
    print(f"unreadable from stripe:         {outcomes['unreadable']}")
    print(f"drifted from stripe:            {drifted}")
    if apply:
        return _applied_status(outcomes)
    return _read_only_status(drifted, outcomes["unreadable"])


def _applied_status(outcomes: Counter[str]) -> int:
    """A raced row is the right OUTCOME (a webhook wrote something newer than what
    was fetched) but not a finished run: that row drifted and was not repaired, and
    a run that raced on every row must not report success. Re-running settles it.
    Unreadable rows will not settle on a re-run with the same credentials.
    """
    print(f"repaired:                       {outcomes['repaired']}")
    print(f"skipped (changed under us):     {outcomes['raced']}")
    return 1 if (outcomes["unreadable"] or outcomes["raced"]) else 0


def _read_only_status(drifted: int, unreadable: int) -> int:
    if drifted:
        print("\nDrift found. Re-run with --apply to rewrite these rows from Stripe.")
    if unreadable:
        print(_UNREADABLE_HELP)
    if drifted or unreadable:
        return 1
    print("\nEvery subscription matches Stripe.")
    return 0


_UNREADABLE_HELP = """
Some subscriptions could not be read from Stripe, and --apply will
not fix those: they will keep this exit status at 1 every run. Two
causes, and they need opposite responses:
  * wrong account or MODE (another account's key, or a test key against
    live ids): every row reads as missing. Re-run with the matching key;
    do NOT cancel anything, the subscriptions are real.
  * the subscription really was deleted in Stripe: cancel that row by
    hand. This will not do it for you, because the two cases look
    identical from here and one of them ends paid access."""


if __name__ == "__main__":  # pragma: no cover
    sys.exit(asyncio.run(main()))
