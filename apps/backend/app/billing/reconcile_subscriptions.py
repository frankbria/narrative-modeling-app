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

Rows are read at most `CONCURRENT_READS` at a time, and a read Stripe answers
with a rate limit, a network failure or a 5xx is retried after each of
`RETRY_DELAYS_SECONDS` (#1213). A read that fails is counted as one of three:
missing (Stripe says the subscription does not exist with this key), unreadable
(Stripe refused for another reason) or busy/unreachable (still failing after the
retries). Only the first two need a person, unless the same row was busy on
the previous run too (#1228): under `--apply` a busy row gets
`stripe_unreachable_since`, a read Stripe answers clears it, and a row still busy
`UNREACHABLE_ALERT_AFTER` later threatens the grace window.

The run stops itself after `RUN_BUDGET_SECONDS`, inside the job's timeout: reads
still in flight are cancelled and the rows not reached are counted busy, so a
Stripe that hangs is reported here rather than by a cancelled job (#1228).

Exit status: 0 when every row it could read matches Stripe (after repairs, under
`--apply`), 1 when a row is missing, unreadable, raced, or (read-only) drifted,
2 when a required setting is missing, 3 when the run could not finish (the
database was unreachable, or a row's repair raised; the other rows are still
repaired), 5 when nothing else is wrong but a row was busy on this run and the
previous one. A row Stripe was busy for only this once does not fail the run: it
settles on a later run.

A sales-led ENTERPRISE deal sold on its own price must use the price in
`STRIPE_PRICE_ENTERPRISE`: any other price resolves to PRO, here as in the
webhook, and this runs every day.
"""

import asyncio
import os
import sys
from collections import Counter
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import stripe
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.api.routes.billing_webhook import _period_end, _price_id, tier_for_price
from app.billing import stripe_client
from app.models.subscription import SubscriptionStatus
from app.utils.datetime import as_utc


class ReadFailure(StrEnum):
    """Why a row could not be compared with Stripe; each needs a different answer."""

    MISSING = "missing"
    UNREADABLE = "unreadable"
    UNAVAILABLE = "unavailable"


Row = Mapping[str, Any]
Remote = dict[str, Any]
Fetch = Callable[[str], Awaitable[Remote | ReadFailure]]

#: Reads in flight at once. Five at Stripe's usual latency stays under the
#: sandbox's 25 reads a second (live allows 100), and inside the thread pool
#: `asyncio.to_thread` gets on a two-CPU box (`min(32, cpus + 4)`).
CONCURRENT_READS = 5
#: Seconds to wait before each retry of a read Stripe was busy or unreachable for.
RETRY_DELAYS_SECONDS = (1, 2, 4)
#: Seconds the run may spend reading before it stops: the job allows 15 minutes,
#: about two go to Tailscale, ssh and the container start, and a read cancelled
#: here keeps its thread until the SDK's own timeout.
RUN_BUDGET_SECONDS = 9 * 60
#: How long a row may stay busy before it alerts: the previous daily run, with
#: room for GitHub starting a scheduled run late. `ENTITLEMENT_GRACE` is three
#: days, so a missed renewal still has about one run left when this fires.
UNREACHABLE_ALERT_AFTER = timedelta(hours=20)
UNREACHABLE_FIELD = "stripe_unreachable_since"
_TRANSIENT = (stripe.RateLimitError, stripe.APIConnectionError, stripe.APIError)
_sleep = asyncio.sleep


async def main() -> int:
    apply = "--apply" in sys.argv[1:]

    uri, db_name = os.getenv("MONGODB_URI"), os.getenv("MONGODB_DB")
    missing = _missing_settings(uri, db_name)
    if missing or not uri or not db_name:
        # On stdout: the scheduled run discards the container's stderr (#1215).
        print(f"missing settings: {', '.join(missing)}")
        return 2

    return await _reconcile_database(uri, db_name, apply)


def _missing_settings(uri: str | None, db_name: str | None) -> list[str]:
    """Names of the unset settings the run needs, in the order they are read.

    STRIPE_PRICE_PRO is required like the app requires it. An unset ENTERPRISE
    price is not refused: `reconcile()` then leaves every tier alone, because
    `tier_for_price` would resolve an unmatched price to PRO and `--apply` would
    downgrade ENTERPRISE.
    """
    present = {
        "MONGODB_URI": bool(uri),
        "MONGODB_DB": bool(db_name),
        "STRIPE_SECRET_KEY": stripe_client.is_configured(),
        "STRIPE_PRICE_PRO": bool(stripe_client.setting("STRIPE_PRICE_PRO")),
    }
    return [name for name, is_set in present.items() if not is_set]


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


def _failure(cause: BaseException | None) -> ReadFailure:
    """What a Stripe error says about the row. A wrong account or mode reads as
    missing too: Stripe answers `resource_missing` for an id it holds elsewhere."""
    if isinstance(cause, _TRANSIENT):
        return ReadFailure.UNAVAILABLE
    if (
        isinstance(cause, stripe.InvalidRequestError)
        and cause.code == "resource_missing"
    ):
        return ReadFailure.MISSING
    return ReadFailure.UNREADABLE


def _stripe_error(exc: stripe_client.BillingProviderError) -> BaseException:
    """The SDK error the client raised `from`, or the wrapper if it had none."""
    return exc.__cause__ or exc


async def _fetch_from_stripe(subscription_id: str) -> Remote | ReadFailure:
    """The live subscription, or why Stripe would not give it to us.

    A single unreadable subscription must not abort a bulk repair: one deleted
    test subscription would otherwise stop every real row behind it from being
    fixed. The SDK retries a 429 only when Stripe's header asks it to, so the
    backoff is here.
    """
    waits = iter(RETRY_DELAYS_SECONDS)
    while True:
        try:
            return await stripe_client.retrieve_subscription(subscription_id)
        except stripe_client.BillingProviderError as exc:
            stripe_error = _stripe_error(exc)
            failure = _failure(stripe_error)
            delay = next(waits, None) if failure is ReadFailure.UNAVAILABLE else None
            if delay is None:
                cause = type(stripe_error).__name__
                print(f"  could not read one subscription from Stripe: {cause}")
                return failure
            await _sleep(delay)


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


async def _read_before(
    fetch: Fetch, subscription_id: str, deadline: float
) -> Remote | ReadFailure:
    """The read, or busy if it is still waiting at the run's deadline."""
    try:
        async with asyncio.timeout_at(deadline):
            return await fetch(subscription_id)
    except TimeoutError:
        return ReadFailure.UNAVAILABLE


async def _busy(
    collection: AsyncIOMotorCollection[dict[str, Any]], row: Row, apply: bool
) -> str:
    """Busy this run; busy for too long when the previous run was busy too.

    The marker is a raw write that leaves `updated_at` alone, so the repair's race
    check is unaffected, and it keeps the first busy run's time.
    """
    since = row.get(UNREACHABLE_FIELD)
    if since is None:
        if apply:
            await collection.update_one(
                {"_id": row["_id"], UNREACHABLE_FIELD: None},
                {"$set": {UNREACHABLE_FIELD: datetime.now(UTC)}},
            )
        return "unavailable"
    too_long = datetime.now(UTC) - as_utc(since) >= UNREACHABLE_ALERT_AFTER
    return "unavailable_too_long" if too_long else "unavailable"


async def _answered(
    collection: AsyncIOMotorCollection[dict[str, Any]], row: Row, apply: bool
) -> None:
    """Stripe answered for the row, whatever it said: it is reachable again."""
    if apply and row.get(UNREACHABLE_FIELD) is not None:
        await collection.update_one(
            {"_id": row["_id"]}, {"$unset": {UNREACHABLE_FIELD: ""}}
        )


async def _repair(
    collection: AsyncIOMotorCollection[dict[str, Any]],
    row: Row,
    changes: dict[str, Any],
    apply: bool,
) -> str:
    """Matched, drifted, repaired or raced."""
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


async def _reconcile_row(
    collection: AsyncIOMotorCollection[dict[str, Any]],
    fetch: Fetch,
    row: Row,
    tiers_resolvable: bool,
    apply: bool,
    deadline: float,
) -> str:
    """What happened to one row: a `ReadFailure`, matched, drifted, repaired or
    raced."""
    remote = await _read_before(fetch, row["stripe_subscription_id"], deadline)
    if remote is ReadFailure.UNAVAILABLE:
        return await _busy(collection, row, apply)
    await _answered(collection, row, apply)
    if isinstance(remote, ReadFailure):
        return remote.value
    return await _repair(collection, row, _drift(row, remote, tiers_resolvable), apply)


async def _slot_before(slots: asyncio.Semaphore, deadline: float) -> bool:
    """A free read slot, unless the deadline comes first."""
    if asyncio.get_running_loop().time() >= deadline:
        return False
    try:
        async with asyncio.timeout_at(deadline):
            await slots.acquire()
    except TimeoutError:
        return False
    return True


async def reconcile(
    collection: AsyncIOMotorCollection[dict[str, Any]],
    fetch: Fetch,
    apply: bool,
    budget_seconds: float = RUN_BUDGET_SECONDS,
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

    # A row is taken from the cursor only when a read slot is free, so the time
    # between reading a row and its conditional write does not grow with the
    # table: a longer window would turn more rows into "changed under us". Only
    # the reads in flight are held, so memory does not grow with it either.
    deadline = asyncio.get_running_loop().time() + budget_seconds
    slots = asyncio.Semaphore(CONCURRENT_READS)
    outcomes: Counter[str] = Counter()
    in_flight: set[asyncio.Task[None]] = set()

    async def in_slot(row: Row) -> None:
        try:
            outcomes[
                await _reconcile_row(
                    collection, fetch, row, tiers_resolvable, apply, deadline
                )
            ] += 1
        except Exception as exc:  # noqa: BLE001 - counted by class, see `_report`
            print(f"  could not repair one subscription: {type(exc).__name__}")
            outcomes["failed"] += 1
        finally:
            slots.release()

    try:
        async for row in collection.find(
            {"stripe_subscription_id": {"$type": "string"}}
        ):
            if not await _slot_before(slots, deadline):
                outcomes["unreached"] += 1
                outcomes[await _busy(collection, row, apply)] += 1
                continue
            task = asyncio.create_task(in_slot(row))
            in_flight.add(task)
            task.add_done_callback(in_flight.discard)
        await asyncio.gather(*in_flight)
    finally:
        # A cursor that fails mid-table must not leave reads running behind it.
        for task in in_flight:
            task.cancel()
        await asyncio.gather(*in_flight, return_exceptions=True)
    return _report(outcomes, apply)


def _report(outcomes: Counter[str], apply: bool) -> int:
    """Print the counts; the exit status `main()` documents."""
    drifted = outcomes["drifted"] + outcomes["repaired"] + outcomes["raced"]
    too_long = outcomes["unavailable_too_long"]
    print(f"subscriptions with a stripe id: {outcomes.total() - outcomes['unreached']}")
    print(f"missing from stripe:            {outcomes['missing']}")
    print(f"unreadable from stripe:         {outcomes['unreadable']}")
    print(f"stripe busy or unreachable:     {outcomes['unavailable'] + too_long}")
    print(f"busy on the previous run too:   {too_long}")
    print(f"not reached in the time limit: {outcomes['unreached']}")
    print(f"drifted from stripe:            {drifted}")
    if outcomes["failed"]:
        # The class went to stdout per row; a database error message can name hosts.
        print(f"the reconciliation did not finish: {outcomes['failed']} rows failed")
        return 3
    status = (
        _applied_status(outcomes)
        if apply
        else _read_only_status(drifted, outcomes["missing"] + outcomes["unreadable"])
    )
    busy_status = _busy_too_long_status(too_long)
    return status or busy_status


def _busy_too_long_status(too_long: int) -> int:
    """5 when rows were busy on this run and the previous one; says what to check."""
    if not too_long:
        return 0
    print(_BUSY_TOO_LONG_HELP)
    return 5


def _applied_status(outcomes: Counter[str]) -> int:
    """A raced row is the right OUTCOME (a webhook wrote something newer than what
    was fetched) but not a finished run: that row drifted and was not repaired, and
    a run that raced on every row must not report success. Re-running settles it.
    Missing and unreadable rows will not settle on a re-run with the same
    credentials. A row Stripe was too busy for will, so it is counted and left.
    """
    print(f"repaired:                       {outcomes['repaired']}")
    print(f"skipped (changed under us):     {outcomes['raced']}")
    needs_a_person = outcomes["missing"] + outcomes["unreadable"] + outcomes["raced"]
    return 1 if needs_a_person else 0


def _read_only_status(drifted: int, unread: int) -> int:
    if drifted:
        print("\nDrift found. Re-run with --apply to rewrite these rows from Stripe.")
    if unread:
        print(_UNREADABLE_HELP)
    if drifted or unread:
        return 1
    print("\nEvery subscription Stripe answered for matches it.")
    return 0


_BUSY_TOO_LONG_HELP = """
Stripe was busy or unreachable for some subscriptions on this run and
the previous one, or the run's time ran out before reaching them. A
customer whose renewal webhook was missed drops to FREE three days
after the stale period end, so this cannot wait for Stripe to recover
on its own. Check, from the box, its route to api.stripe.com (DNS,
firewall, proxy), and Stripe's status page, https://status.stripe.com.
If "not reached in the time limit" is above zero on every run, the
table has outgrown one run: read more at once or run more often."""


_UNREADABLE_HELP = """
Some subscriptions could not be read from Stripe, and --apply will
not fix those: they will keep this exit status at 1 every run.
Unreadable: Stripe refused the read (the error class is above; a
revoked key or one without permission to read subscriptions). Fix the
key. Missing has two causes, and they need opposite responses:
  * wrong account or MODE (another account's key, or a test key against
    live ids): every row reads as missing. Re-run with the matching key;
    do NOT cancel anything, the subscriptions are real.
  * the subscription really was deleted in Stripe: cancel that row by
    hand. This will not do it for you, because the two cases look
    identical from here and one of them ends paid access."""


if __name__ == "__main__":  # pragma: no cover
    sys.exit(asyncio.run(main()))
