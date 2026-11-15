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
`stripe_unreachable_since`, a read Stripe answers under `--apply` clears it, and a
row still busy `UNREACHABLE_ALERT_AFTER` later, with no answer from Stripe in
between, threatens the grace window. A run that never asked Stripe (the database
or the box unreachable) does not reset that clock: nothing showed Stripe was back.

The run stops itself after `RUN_BUDGET_SECONDS`, inside the job's timeout: reads
still in flight are cancelled and the rows not reached are counted busy, so a
Stripe that hangs is reported here rather than by a cancelled job (#1228).

Rows are read in `_id` order, from where the previous `--apply` run stopped and
round to the start again (#1239): that run stores the first row it did not read
in `RESUME_COLLECTION`. A table that outgrows one run is then read in full every
two runs, inside `ENTITLEMENT_GRACE`; one that outgrows two leaves a row unread on
two runs in a row, which is exit 5. The same document lists the rows Stripe
refused (#1251): the next run reads them before anything else and leaves them
out of its walk, so a row refused late in a run is not left until after the
wrap. A listed row refused again is not listed again, and a listed row never
moves the start, so a row that stays busy cannot hold anything up. After a
Stripe outage the list can be long, and reading it first spends the next run's
budget on rows the previous one reached; the rows left go to exit 5. The resume
point is also stored when the deadline stops the walk, before the rows left are
counted, so a database that stalls there (exit 3) does not keep the next run at
the old start. A cursor that fails still stores nothing: a row that breaks it
would break it from any start. A run without `--apply` follows the stored
order and writes nothing: neither the resume point nor a busy marker, set or
cleared, so it is safe to run by hand; the next `--apply` run settles both. An
`--apply` run by hand while the scheduled one runs is not: both start at the
same point and read the same range, and the last to finish stores its own.

Exit status: 0 when every row it could read matches Stripe (after repairs, under
`--apply`), 1 when a row is missing, unreadable, raced, or (read-only) drifted,
2 when a required setting is missing, 3 when the run could not finish (the
database was unreachable or stalled past `FINISH_SECONDS` after the budget, or a
row's repair raised; the other rows are still repaired), 5 when nothing else is wrong but a row was busy on this run and the
previous one. A row Stripe was busy for only this once does not fail the run: it
settles on a later run.

A sales-led ENTERPRISE deal sold on its own price must use the price in
`STRIPE_PRICE_ENTERPRISE`: any other price resolves to PRO, here as in the
webhook, and this runs every day.
"""

import asyncio
import logging
import os
import sys
from collections import Counter
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, NoReturn

import stripe
from bson import ObjectId
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
    #: The run's deadline ended the read: Stripe said nothing either way.
    UNREAD = "unread"


Row = Mapping[str, Any]
Remote = dict[str, Any]
Fetch = Callable[[str], Awaitable[Remote | ReadFailure]]
Collection = AsyncIOMotorCollection[dict[str, Any]]

#: Reads in flight at once. Five at Stripe's usual latency stays under the
#: sandbox's 25 reads a second (live allows 100), and inside the thread pool
#: `asyncio.to_thread` gets on a two-CPU box (`min(32, cpus + 4)`).
CONCURRENT_READS = 5
#: Seconds to wait before each retry of a read Stripe was busy or unreachable for.
RETRY_DELAYS_SECONDS = (1, 2, 4)
#: Seconds the run may spend reading before it stops: its workflow step allows 11
#: minutes, the container start takes some, and a read cancelled
#: here keeps its thread until the SDK's own timeout.
RUN_BUDGET_SECONDS = 9 * 60
#: Seconds past the budget for the cancelled reads, the bulk accounting of the
#: rows not reached and the report; past it the run stops with exit 3.
FINISH_SECONDS = 60
#: How long a row may stay busy before it alerts: the previous daily run, with
#: room for GitHub starting a scheduled run late. `ENTITLEMENT_GRACE` is three
#: days, so a missed renewal still has about one run left when this fires.
UNREACHABLE_ALERT_AFTER = timedelta(hours=20)
UNREACHABLE_FIELD = "stripe_unreachable_since"
#: One document, `RESUME_ID`, holding `resume_from`: the `_id` the next run
#: starts at, or null when the last `--apply` run read every row; and
#: `read_first`: the rows Stripe refused, which the next run reads first.
RESUME_COLLECTION = "subscription_reconcile_resume"
RESUME_ID = "subscriptions"
_NO_ANSWER = (ReadFailure.UNAVAILABLE, ReadFailure.UNREAD)
_WITH_A_STRIPE_ID = {"stripe_subscription_id": {"$type": "string"}}
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
            # A database that stalls is bounded too, not only Stripe.
            async with asyncio.timeout(RUN_BUDGET_SECONDS + FINISH_SECONDS):
                database = client[db_name]
                return await reconcile(
                    database["subscriptions"],
                    _fetch_from_stripe,
                    apply,
                    RUN_BUDGET_SECONDS,
                    database[RESUME_COLLECTION],
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
    """The read, or unread if it is still waiting at the run's deadline."""
    try:
        async with asyncio.timeout_at(deadline):
            return await fetch(subscription_id)
    except TimeoutError:
        return ReadFailure.UNREAD


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
    not_read: "_NotRead",
) -> str:
    """What happened to one row: a `ReadFailure`, matched, drifted, repaired or
    raced. A row without an answer joins `not_read` before any write, so a
    marker write that fails cannot drop it from the next run's start."""
    remote = await _read_before(fetch, row["stripe_subscription_id"], deadline)
    not_read.note(row, remote)
    if remote in _NO_ANSWER:
        return await _busy(collection, row, apply)
    await _answered(collection, row, apply)
    if isinstance(remote, ReadFailure):
        return remote.value
    return await _repair(collection, row, _drift(row, remote, tiers_resolvable), apply)


@dataclass
class _NotRead:
    """The rows of this run that Stripe gave no answer for, as the next run
    needs them: the deadline's, which move its start, and the ones Stripe
    refused, which it reads before anything else (#1251).

    A row this run already read first (`listed`) is not listed again, so a row
    that stays busy is read early every other run, not every run. A listed row
    never moves the start, so none can pin it; one busy on two runs goes on to
    exit 5 like any other."""

    listed: tuple[ObjectId, ...]
    cut_short: list[ObjectId] = field(default_factory=list)
    refused: list[ObjectId] = field(default_factory=list)

    def note(self, row: Row, remote: Remote | ReadFailure) -> None:
        if remote is ReadFailure.UNREAD:
            self.cut_short.append(row["_id"])
        elif remote is ReadFailure.UNAVAILABLE and row["_id"] not in self.listed:
            self.refused.append(row["_id"])


@dataclass(frozen=True)
class _Order:
    """The walk's order: the rows in `first`, then `_id` order from `start` to
    the end, then from the first row up to `start`, leaving out `first`. No
    start is plain `_id` order."""

    start: ObjectId | None
    first: tuple[ObjectId, ...] = ()

    def segments(self) -> list[dict[str, Any]]:
        if self.start is None:
            main: list[dict[str, Any]] = [{}]
        else:
            main = [{"_id": {"$gte": self.start}}, {"_id": {"$lt": self.start}}]
        listed = [{"_id": {"$in": list(self.first)}}] if self.first else []
        return listed + [self._outside_first(segment) for segment in main]

    def position(self, row_id: ObjectId) -> tuple[bool, ObjectId]:
        """Sorts the ids outside `first` in this order: the wrapped part last."""
        return (self.start is not None and row_id < self.start, row_id)

    def after(self, row_id: ObjectId) -> dict[str, Any]:
        """A filter for the rows that come after `row_id` in this order."""
        if row_id in self.first:
            later = [each for each in self.first if each > row_id]
            rest = {"_id": {"$nin": list(self.first)}}
            return {"$or": [{"_id": {"$in": later}}, rest]}
        return self._outside_first(self._after_in_id_order(row_id))

    def _after_in_id_order(self, row_id: ObjectId) -> dict[str, Any]:
        if self.start is None:
            return {"_id": {"$gt": row_id}}
        if row_id < self.start:
            return {"_id": {"$gt": row_id, "$lt": self.start}}
        return {"$or": [{"_id": {"$gt": row_id}}, {"_id": {"$lt": self.start}}]}

    def _outside_first(self, query: dict[str, Any]) -> dict[str, Any]:
        if not self.first:
            return query
        return {"$and": [query, {"_id": {"$nin": list(self.first)}}]}


async def _stored_order(resume: Collection | None) -> _Order:
    """The order the previous `--apply` run left, or plain `_id` order."""
    stored = await resume.find_one({"_id": RESUME_ID}) if resume is not None else None
    return _order_from(stored or {})


def _order_from(stored: Mapping[str, Any]) -> _Order:
    """The rows to read first and the row to resume from. Only an `ObjectId` is
    a place in `_id` order; anything else written by hand would match every row
    in one segment and fail the comparisons at the deadline."""
    start = stored.get("resume_from")
    first = [each for each in stored.get("read_first") or [] if _is_id(each)]
    return _Order(start if _is_id(start) else None, tuple(sorted(first)))


def _is_id(value: object) -> bool:
    return isinstance(value, ObjectId)


def _resume_from(
    order: _Order, unread: list[ObjectId], stopped_at: list[ObjectId]
) -> ObjectId | None:
    """The first row after `first`, in this run's order, that it did not read:
    one the deadline cut short or the one the walk stopped at; None when it read
    every row. A stop among the listed rows reached none of the rest, so the
    start stays. A listed row the deadline cut short is not the start: it is
    marked busy like any row, and holding the start for it would read the same
    range again."""
    if any(each in order.first for each in stopped_at):
        return order.start
    rest = [each for each in unread + stopped_at if each not in order.first]
    return min(rest, key=order.position, default=None)


async def _store_resume_point(
    resume: Collection, resume_from: ObjectId | None, refused: list[ObjectId]
) -> None:
    await resume.update_one(
        {"_id": RESUME_ID},
        {"$set": {"resume_from": resume_from, "read_first": sorted(refused)}},
        upsert=True,
    )


async def _not_reached_after(
    collection: AsyncIOMotorCollection[dict[str, Any]],
    after: dict[str, Any],
    apply: bool,
) -> Counter[str]:
    """The rows matching `after`, counted busy with three queries rather than one
    write per row, so the time this takes does not grow with the table."""
    rest = {**_WITH_A_STRIPE_ID, **after}
    now = datetime.now(UTC)
    unreached = await collection.count_documents(rest)
    too_long = await collection.count_documents(
        {**rest, UNREACHABLE_FIELD: {"$lte": now - UNREACHABLE_ALERT_AFTER}}
    )
    if apply:
        await collection.update_many(
            {**rest, UNREACHABLE_FIELD: None}, {"$set": {UNREACHABLE_FIELD: now}}
        )
    return Counter(
        unreached=unreached,
        unavailable_too_long=too_long,
        unavailable=unreached - too_long,
    )


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


async def _the_rest(
    collection: AsyncIOMotorCollection[dict[str, Any]],
    row: Row,
    apply: bool,
    order: _Order,
) -> Counter[str]:
    """The row the deadline caught and every row after it, all counted busy."""
    rest = await _not_reached_after(collection, order.after(row["_id"]), apply)
    rest.update({await _busy(collection, row, apply): 1, "unreached": 1})
    return rest


async def _cancel(tasks: set[asyncio.Task[None]]) -> None:
    """Cancel the reads still running and wait until they have stopped."""
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def _rows_in(
    collection: AsyncIOMotorCollection[dict[str, Any]], order: _Order
) -> AsyncIterator[Row]:
    """The rows with a Stripe id, in `order`, so the rows a deadline leaves are
    one range of it."""
    for segment in order.segments():
        query = {**_WITH_A_STRIPE_ID, **segment}
        async for row in collection.find(query, sort=[("_id", 1)]):
            yield row


async def _walk(
    collection: AsyncIOMotorCollection[dict[str, Any]],
    read_row: Callable[[Row], Coroutine[Any, Any, None]],
    slots: asyncio.Semaphore,
    deadline: float,
    apply: bool,
    outcomes: Counter[str],
    order: _Order,
    checkpoint: Callable[[list[ObjectId], list[ObjectId]], Awaitable[None]],
) -> list[ObjectId]:
    """Start `read_row` for each row as a slot frees, until the deadline; the id
    of the row the deadline stopped it at, if any.

    At the stop, `checkpoint` gets the reads still in flight and that row before
    the rows left are counted: a database that stalls there ends the run, and
    the next one should still start here (#1251). Only the reads in flight are
    held, so memory does not grow with the table.
    """
    in_flight: dict[asyncio.Task[None], ObjectId] = {}
    stopped_at: list[ObjectId] = []
    try:
        async for row in _rows_in(collection, order):
            if not await _slot_before(slots, deadline):
                stopped_at = [row["_id"]]
                await checkpoint(list(in_flight.values()), stopped_at)
                outcomes.update(await _the_rest(collection, row, apply, order))
                break
            task = asyncio.create_task(read_row(row))
            in_flight[task] = row["_id"]
            task.add_done_callback(in_flight.pop)
        await asyncio.gather(*in_flight)
    finally:
        # A cursor that fails mid-table must not leave reads running behind it.
        await _cancel(set(in_flight))
    return stopped_at


async def reconcile(
    collection: AsyncIOMotorCollection[dict[str, Any]],
    fetch: Fetch,
    apply: bool,
    budget_seconds: float = RUN_BUDGET_SECONDS,
    resume: Collection | None = None,
) -> int:
    """Compare each row against Stripe; rewrite what drifted under `apply`.

    `fetch` is injected so this can be tested against a fake without a Stripe
    account, and so the caller decides what "read from Stripe" means. Without
    `resume` every run starts at the first row and nothing is stored.
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
    # table: a longer window would turn more rows into "changed under us".
    deadline = asyncio.get_running_loop().time() + budget_seconds
    order = await _stored_order(resume)
    slots = asyncio.Semaphore(CONCURRENT_READS)
    outcomes: Counter[str] = Counter()
    not_read = _NotRead(order.first)

    async def in_slot(row: Row) -> None:
        try:
            outcomes[
                await _reconcile_row(
                    collection, fetch, row, tiers_resolvable, apply, deadline, not_read
                )
            ] += 1
        except Exception as exc:  # noqa: BLE001 - counted by class, see `_report`
            print(f"  could not repair one subscription: {type(exc).__name__}")
            outcomes["failed"] += 1
        finally:
            slots.release()

    async def checkpoint(in_flight: list[ObjectId], stopped_at: list[ObjectId]) -> None:
        if apply and resume is not None:
            unread = not_read.cut_short + in_flight
            resume_from = _resume_from(order, unread, stopped_at)
            await _store_resume_point(resume, resume_from, not_read.refused)

    stopped_at = await _walk(
        collection, in_slot, slots, deadline, apply, outcomes, order, checkpoint
    )
    await checkpoint([], stopped_at)
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
    print(f"not reached in the time limit:  {outcomes['unreached']}")
    print(f"drifted from stripe:            {drifted}")
    if outcomes["failed"]:
        # The class went to stdout per row; a database error message can name hosts.
        print(f"the reconciliation did not finish: {outcomes['failed']} rows failed")
        status = 3
    elif apply:
        status = _applied_status(outcomes)
    else:
        status = _read_only_status(
            drifted, outcomes["missing"] + outcomes["unreadable"]
        )
    # After every count, and whatever the status: the help is the only place the
    # alert learns that Stripe has been unreachable since the previous run.
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
Each run starts at the first row the previous one did not read, so a
table up to two runs' worth is read every two runs. If Stripe answered
every other read (no "could not read" lines above, the status page
clear) and "not reached in the time limit" is above zero, the table
has outgrown two runs: read more at once or run more often."""


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


def _cli() -> NoReturn:
    """Run `main()` and exit with its status without waiting for read threads.

    A read cancelled at the deadline can still be blocked in its worker thread
    (a Stripe that trickles bytes inside the SDK's read timeout), and
    `asyncio.run` waits up to five minutes for those threads on shutdown, then
    the interpreter joins them again at exit: either would outlast the job's
    timeout. The database client is closed by then and nothing else is pending.
    `os._exit` also skips the interpreter's own shutdown, so logging is flushed
    here. Sentry needs nothing: only `app.main` initialises it, and this process
    never imports that (#1239). Initialise it here and flush it here together.
    """
    status = asyncio.new_event_loop().run_until_complete(main())
    logging.shutdown()
    sys.stdout.flush()
    os._exit(status)


if __name__ == "__main__":  # pragma: no cover
    _cli()
