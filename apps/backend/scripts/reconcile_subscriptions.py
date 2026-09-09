#!/usr/bin/env python3
"""Re-read every Subscription from Stripe and rewrite what has drifted (#458, #510).

Two jobs, one script, because they are the same operation:

* **#510's backfill.** Every row written before the `_period_end()` fix has a null
  `current_period_end` — the pinned API version moved the field onto the
  subscription item and nothing read it there. Those rows must be filled in
  *before* they are judged against #458's expiry check.
* **#458's reconciliation.** Webhook delivery is the only sync mechanism this
  service has, and Stripe gives up retrying an event after about three days. The
  expiry check makes a missed *lapse* fail closed on its own. A missed *renewal*
  fails the other way — a paying customer loses their tier once the stale period
  end goes past the grace window — and nothing but re-reading Stripe can repair
  that. This is that repair.

Deliberately a one-shot script rather than a scheduler: this service has no
scheduler, and introducing one to cover a case that Stripe's own three-day retry
window already makes rare is more machinery than the problem is worth.

**When it is not optional.** Any `Subscription` row written while Stripe was live but
before the `_period_end()` fix carries a null period end, and once the expiry check
is live such a row lapses on `updated_at` instead. Running `--apply` on those rows is
part of that deploy, not routine maintenance — see #598. Otherwise: by hand after a
Stripe incident, or from cron if you want it regularly.

Read-only by default. Reports counts only — no user ids, no Stripe ids — so its
output is safe to paste into a public issue.

Usage (from apps/backend, against whichever cluster you want to check):

    MONGODB_URI=... MONGODB_DB=... STRIPE_SECRET_KEY=... \
    STRIPE_PRICE_PRO=... STRIPE_PRICE_ENTERPRISE=... \
        uv run python scripts/reconcile_subscriptions.py
    # ... same environment, plus --apply, to write

All five are required. The two price ids are not decoration: without them every
tenant resolves to PRO and `--apply` downgrades your ENTERPRISE customers.

Exit status is 1 when uncorrected drift remains, so it can gate a deploy.
"""

import asyncio
import os
import sys
from datetime import UTC, datetime


async def main() -> int:
    from motor.motor_asyncio import AsyncIOMotorClient

    from app.billing import stripe_client

    apply = "--apply" in sys.argv[1:]

    uri, db_name = os.getenv("MONGODB_URI"), os.getenv("MONGODB_DB")
    if not uri or not db_name:
        print("Set MONGODB_URI and MONGODB_DB.", file=sys.stderr)
        return 2
    if not stripe_client.is_configured():
        print("Set STRIPE_SECRET_KEY — this script reads from Stripe.", file=sys.stderr)
        return 2
    # Not optional, and the reason is not symmetry with the app's env file.
    # `tier_for_price` falls back to PRO for any price it cannot match against a
    # CONFIGURED setting — and an unset setting matches nothing. An operator shell
    # with only a secret key would therefore resolve every tenant to PRO and
    # `--apply` would write it, silently downgrading every ENTERPRISE customer on
    # the cluster. This is the same trap CLAUDE.md documents for the webhook, one
    # environment removed.
    missing = [
        name
        for name in ("STRIPE_PRICE_PRO", "STRIPE_PRICE_ENTERPRISE")
        if not stripe_client.setting(name)
    ]
    if missing:
        print(
            "Set " + " and ".join(missing) + " — without them every tenant resolves\n"
            "to PRO and --apply would downgrade your ENTERPRISE customers.",
            file=sys.stderr,
        )
        return 2

    client = AsyncIOMotorClient(uri)
    try:
        return await reconcile(
            client[db_name]["subscriptions"], _fetch_from_stripe, apply
        )
    finally:
        client.close()


def _fetch_from_stripe(subscription_id: str) -> dict | None:
    """The live subscription, or None if Stripe will not give it to us.

    A single unreadable subscription must not abort a bulk repair — one deleted
    test subscription would otherwise stop every real row behind it from being
    fixed.
    """
    from app.billing import stripe_client

    try:
        stripe = stripe_client._client()
        return dict(stripe.Subscription.retrieve(subscription_id))
    except Exception as exc:  # noqa: BLE001 - any Stripe failure is per-row, not fatal
        print(f"  could not read one subscription from Stripe: {type(exc).__name__}")
        return None


async def reconcile(collection, fetch, apply: bool) -> int:
    """Compare each row against Stripe; rewrite status and period end under --apply.

    `fetch` is injected so this can be tested against a fake without a Stripe
    account, and so the caller decides what "read from Stripe" means.
    """
    # Imported here rather than at module scope so `--help`-style misuse and the
    # env-var checks above fail before anything touches the app package.
    from app.api.routes.billing_webhook import _period_end, _price_id, tier_for_price
    from app.billing import stripe_client
    from app.models.subscription import SubscriptionStatus
    from app.utils.datetime import as_utc

    # Defence in depth behind `main()`'s check: `reconcile()` is the tested entry
    # point and can be called directly, and the failure it guards against rewrites
    # paying customers' tiers with no error.
    tiers_resolvable = bool(
        stripe_client.setting("STRIPE_PRICE_PRO")
        and stripe_client.setting("STRIPE_PRICE_ENTERPRISE")
    )
    if not tiers_resolvable:
        print("STRIPE_PRICE_* unset: reconciling status and period end only.")

    total = drifted = repaired = unreadable = raced = 0

    cursor = collection.find({"stripe_subscription_id": {"$type": "string"}})
    async for row in cursor:
        total += 1
        remote = fetch(row["stripe_subscription_id"])
        if remote is None:
            unreadable += 1
            continue

        status = SubscriptionStatus.from_stripe(remote.get("status", "")).value
        period_end = _period_end(remote)
        # The tier drifts on its own: an upgrade keeps the same subscription, the
        # same status and the same period end, and changes only the price. A missed
        # `customer.subscription.updated` there leaves a customer paying for
        # ENTERPRISE and enforced as PRO, and a script that compared only status and
        # period end would report "everything matches" while it happened.
        price = _price_id(remote)
        # No price means leave the tier alone, exactly as the webhook does:
        # `tier_for_price` falls back to PRO rather than returning None, so passing
        # it unconditionally would silently downgrade an ENTERPRISE tenant whenever
        # Stripe answered without expanded item data.
        tier = tier_for_price(price).value if price and tiers_resolvable else None

        changes = {}
        if status != row.get("status"):
            changes["status"] = status
        if tier is not None and tier != row.get("plan_tier"):
            changes["plan_tier"] = tier
        if price and price != row.get("stripe_price_id"):
            changes["stripe_price_id"] = price
        # A null period end is the #510 symptom, so "unset locally, set remotely"
        # counts as drift; equality alone would leave those rows behind. The stored
        # value comes back naive (CLAUDE.md) — comparing it directly against the
        # aware value from Stripe would mark every single row as drifted, forever.
        stored = row.get("current_period_end")
        if period_end is not None and (stored is None or as_utc(stored) != period_end):
            changes["current_period_end"] = period_end
        if not changes:
            continue

        # The raw `update_one` below bypasses Beanie, so the model's `_touch()` hook
        # never fires. That matters here rather than being cosmetic: `is_entitled`
        # falls back to `updated_at` when no period end is known, so a repair that
        # confirmed with Stripe that a subscription is live would otherwise leave the
        # row lapsing on a timestamp from before the repair.
        changes["updated_at"] = datetime.now(UTC)

        drifted += 1
        if apply:
            # Conditional on the row not having moved since it was read. A webhook
            # can land between the Stripe read above and this write — and it is
            # newer than what the script fetched, so writing over it would undo a
            # real cancellation and leave the row wrong until somebody happens to
            # run this again. `_touch()` bumps `updated_at` on every Beanie save, so
            # a lost race matches nothing and is counted rather than applied.
            result = await collection.update_one(
                {"_id": row["_id"], "updated_at": row.get("updated_at")},
                {"$set": changes},
            )
            if result.modified_count:
                repaired += 1
            else:
                raced += 1

    print(f"subscriptions with a stripe id: {total}")
    print(f"unreadable from stripe:         {unreadable}")
    print(f"drifted from stripe:            {drifted}")
    if apply:
        print(f"repaired:                       {repaired}")
        print(f"skipped (changed under us):     {raced}")
        # A raced row is not a failure — a webhook wrote something newer than what
        # was fetched, which is the outcome we want. Unreadable rows are, and they
        # will not be fixed by running again with the same Stripe credentials.
        return 1 if unreadable else 0

    if drifted:
        print("\nDrift found. Re-run with --apply to rewrite these rows from Stripe.")
    if unreadable:
        print("\nSome subscriptions could not be read from Stripe, and --apply will")
        print("not fix those — they will keep this exit status at 1 every run. Two")
        print("causes, and they need opposite responses:")
        print("  * wrong account MODE (a test key against live ids, or the reverse):")
        print("    every row reads as missing. Re-run with the matching key; do NOT")
        print("    cancel anything, the subscriptions are real.")
        print("  * the subscription really was deleted in Stripe: cancel that row by")
        print("    hand. This script will not do it for you, because the two cases")
        print("    look identical from here and one of them ends paid access.")
    if drifted or unreadable:
        return 1
    print("\nEvery subscription matches Stripe.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
