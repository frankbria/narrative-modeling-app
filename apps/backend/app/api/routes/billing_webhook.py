"""Stripe webhook: keep local subscription state in sync (#367).

Stripe is the source of truth; this endpoint is how that truth reaches us.

Three properties shape everything here:

* **Signature first, parse second.** Nothing about the body is trusted — not even
  that it is JSON — until it is verified against `STRIPE_WEBHOOK_SECRET`.
* **Idempotent.** Stripe delivers at least once and retries on any non-2xx, so every
  handler is an upsert keyed on `user_id`, and replaying an event is a no-op rather
  than a duplicate.
* **Unknown events are acknowledged, not rejected.** Returning a non-2xx makes Stripe
  retry forever. An event type we do not handle is not a failure; it is simply not
  ours, so it is logged and 200'd.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pymongo.errors import DuplicateKeyError

from app.billing import stripe_client
from app.billing.api_keys import reconcile_user_api_keys
from app.billing.stripe_signature import (
    SignatureVerificationError,
    verify_signature,
)
from app.models.subscription import (
    PlanTier,
    Subscription,
    SubscriptionStatus,
)
from app.services import product_events

logger = logging.getLogger(__name__)

router = APIRouter()

#: Events acted on. Everything else is acknowledged and ignored — see module note.
HANDLED_EVENTS = frozenset(
    {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.payment_failed",
    }
)


def tier_for_price(price_id: str | None) -> PlanTier:
    """Map a Stripe price id onto a tier.

    Falls back to PRO rather than ENTERPRISE for an unrecognised price: guessing
    high hands out the most expensive entitlements to a misconfiguration.

    Never returns None, which is why callers on the UPDATE path must decide for
    themselves whether a missing price means "PRO" or "leave it alone".
    """
    if not price_id:
        return PlanTier.PRO

    for tier, configured in (
        (PlanTier.ENTERPRISE, stripe_client.setting("STRIPE_PRICE_ENTERPRISE")),
        (PlanTier.PRO, stripe_client.setting("STRIPE_PRICE_PRO")),
    ):
        if configured and configured == price_id:
            return tier
    return PlanTier.PRO


def _user_id_from(obj: dict[str, Any]) -> str | None:
    """Find our tenant id on a Stripe object.

    Checkout sets `client_reference_id`; subscriptions carry it in `metadata`. Both
    are set by us when the session is created (#365), so an object with neither is
    one we did not originate.
    """
    return obj.get("client_reference_id") or (obj.get("metadata") or {}).get("user_id")


async def _record_first_paid(user_id: str, paid_at: datetime | None) -> None:
    """Stamp the tenant's first settled paid charge, once (#602).

    First-write-wins: the filter matches only a row whose ``first_paid_at`` is still
    unset (``None`` also matches a missing field in Mongo), so a later charge never
    moves it. Called from the settled-payment branch after the upsert has created the
    row. Never raises — a webhook must still record the subscription even if this
    bookkeeping write fails; the field simply stays unset (not-in-window) until the
    next settled charge.
    """
    if paid_at is None:
        return
    try:
        await Subscription.get_motor_collection().update_one(
            {"user_id": user_id, "first_paid_at": None},
            {"$set": {"first_paid_at": paid_at}},
        )
    except Exception:
        logger.warning("Failed to record first_paid_at for the refund window", exc_info=True)


async def _upsert(
    user_id: str,
    *,
    status_: SubscriptionStatus | None = None,
    tier: PlanTier | None = None,
    customer_id: str | None = None,
    subscription_id: str | None = None,
    price_id: str | None = None,
    period_end: Any = None,
    cancel_at_period_end: bool | None = None,
    event_at: datetime | None = None,
) -> None:
    """Create or update this tenant's subscription atomically and idempotently."""
    await _apply(
        user_id,
        status_=status_,
        tier=tier,
        customer_id=customer_id,
        subscription_id=subscription_id,
        price_id=price_id,
        period_end=period_end,
        cancel_at_period_end=cancel_at_period_end,
        event_at=event_at,
    )


def _insert_defaults(
    user_id: str, now: datetime, set_fields: dict[str, Any]
) -> dict[str, Any]:
    """Defaults only for a brand-new row, and never for a key the event itself set
    (Mongo rejects a field appearing in both $set and $setOnInsert)."""
    defaults = {
        "user_id": user_id,
        "created_at": now,
        "plan_tier": PlanTier.FREE.value,
        "status": SubscriptionStatus.INCOMPLETE.value,
        "cancel_at_period_end": False,
    }
    return {k: v for k, v in defaults.items() if k not in set_fields}


def _ordering_filter(
    user_id: str, status_: SubscriptionStatus | None, event_at: datetime | None
) -> dict[str, Any]:
    """The filter that orders events (#509, #693).

    Apply only if this event is not older than the newest already applied;
    null/missing (never applied) counts as older, so the first event applies.
    `created` has one-second resolution, so on a tie CANCELED is sticky: a
    non-terminal event in the same second can't resurrect a cancellation; only a
    strictly newer one can.
    """
    flt: dict[str, Any] = {"user_id": user_id}
    if event_at is None:
        return flt
    same_second: dict[str, Any] = {"last_event_at": event_at}
    if status_ != SubscriptionStatus.CANCELED:
        same_second["status"] = {"$ne": SubscriptionStatus.CANCELED.value}
    flt["$or"] = [
        {"last_event_at": {"$lt": event_at}},
        same_second,
        {"last_event_at": None},
        {"last_event_at": {"$exists": False}},
    ]
    return flt


def _present(fields: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None and v != ""}


async def _write_ordered(
    user_id: str, flt: dict[str, Any], update: dict[str, Any]
) -> bool:
    """One conditional upsert; False when the event was dropped as out of order."""
    coll = Subscription.get_motor_collection()
    for attempt in (1, 2):
        try:
            await coll.update_one(flt, update, upsert=True)
            return True
        except DuplicateKeyError:
            if attempt == 2:
                logger.info(
                    "ignoring out-of-order stripe event", extra={"user_id": user_id}
                )
            # A first one means a concurrent event just created the row; retry — the
            # ordering filter now decides whether to apply this event or drop it.
    return False


async def _apply(
    user_id: str,
    *,
    status_: SubscriptionStatus | None = None,
    tier: PlanTier | None = None,
    customer_id: str | None = None,
    subscription_id: str | None = None,
    price_id: str | None = None,
    period_end: Any = None,
    cancel_at_period_end: bool | None = None,
    event_at: datetime | None = None,
) -> None:
    """Persist one event with a single conditional upsert (#367, #509).

    Not a read-modify-write: ``Subscription`` has no revision, so two concurrent
    events would both read the old row and the later ``save()`` would silently
    discard the earlier — a ``subscription.updated`` racing a
    ``subscription.deleted`` could leave a cancelled tenant entitled indefinitely.

    Ordering (Stripe does not guarantee it) lives in the filter: the write applies
    only to a row whose ``last_event_at`` is ``<=`` this event's (or unset) — and, on a
    tie, only if the row is not already CANCELED unless this event is the cancellation
    (#693) — so a strictly-older event matches nothing; the upsert then tries to
    INSERT and the unique ``user_id`` index rejects it, dropping the stale event. A *first*
    ``DuplicateKeyError`` instead means a concurrent event just created the row
    (the normal ``checkout.completed`` + ``subscription.created`` burst for a new
    tenant); retry once, where the same ordering filter now decides apply-or-reject.
    Only fields present on the event are written, so a later event that omits one
    cannot blank what an earlier one set. Delivering the same event twice converges
    on the same row (idempotent in effect).
    """
    now = datetime.now(UTC)
    # Only fields present on the event; an empty id string never overwrites.
    present = {
        "status": getattr(status_, "value", None),
        "plan_tier": getattr(tier, "value", None),
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "stripe_price_id": price_id,
        "current_period_end": period_end,
        "cancel_at_period_end": cancel_at_period_end,
        "last_event_at": event_at,
    }
    set_fields = {"updated_at": now, **_present(present)}
    update = {
        "$set": set_fields,
        "$setOnInsert": _insert_defaults(user_id, now, set_fields),
    }
    if not await _write_ordered(
        user_id, _ordering_filter(user_id, status_, event_at), update
    ):
        return

    # A plan change can *lower* what a key may do; the limiter never re-reads a
    # subscription on the serving path, so nothing else revisits a key minted under
    # a richer tier (#455).
    sub = await Subscription.find_one(Subscription.user_id == user_id)
    if sub is not None:
        await reconcile_user_api_keys(user_id, sub.effective_tier)


def _period_end(obj: dict[str, Any]):
    """Stripe sends epoch seconds; the model stores a datetime.

    **Two locations, checked in that order.** The pinned API version
    (`STRIPE_API_VERSION`) no longer carries `current_period_end` on the
    subscription object at all — it moved onto each subscription *item*, which the
    installed SDK's own types confirm: `stripe/_subscription.py` has no such field
    and `stripe/_subscription_item.py` does. Reading only the old location left the
    field null on every real subscription. That was invisible while nothing read it
    and catastrophic the moment `is_entitled` began to (#510, #458).

    The old top-level location is still checked first because a webhook endpoint can
    be pinned to an older API version than the SDK uses for outbound calls, and an
    account can have several endpoints on different versions. Where both are present
    they agree, and preferring the explicit top-level value keeps an older
    integration reading exactly as it did before.

    Only the FIRST item is read, matching `_price_id` — this product sells one plan
    per subscription. All items of one subscription share a billing period anyway.

    Returns None rather than raising on anything not int-coercible. Everything else
    in this file is defensive about shape for one reason — an uncaught raise is a
    500, and Stripe retries a non-2xx forever. Losing a period-end is recoverable; a
    retry loop is not.
    """
    raw = obj.get("current_period_end")
    if raw is None:
        item = _first_item(obj)
        if item is not None:
            raw = item.get("current_period_end")
    # `bool` subclasses `int`, so a stray `true` would parse as epoch 1 and stamp the
    # subscription as having lapsed in 1970 — the same trap the `created` handling
    # below guards, and worth guarding identically rather than relying on the
    # direction it happens to fail in.
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return datetime.fromtimestamp(int(raw), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        logger.warning("unparseable current_period_end; leaving it unset")
        return None


def _first_item(obj: dict[str, Any]) -> dict[str, Any] | None:
    """The FIRST subscription line item, or None if the payload is not that shape.

    Reads position 0 only. This product sells one plan per subscription — there are
    no bundles or add-ons — so a multi-item subscription is not a shape Stripe should
    ever send us. If that changes, tier attribution has to pick the plan-defining
    item rather than position 0, and this is the function to change.

    Every level is type-checked rather than merely truthiness-checked. `obj["items"]`
    arriving as a string would make `.get("data")` an AttributeError, and a `data`
    that is a bare int would make `[0]` a TypeError — both of which propagate out of
    `_handle`, which nothing wraps, and become a 500 that Stripe then retries
    forever. Two callers needed the same walk and the earlier one only guarded the
    last step, so this is one accessor rather than the same near-miss twice.
    """
    items = obj.get("items")
    if not isinstance(items, dict):
        return None
    data = items.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None
    return data[0]


def _price_id(obj: dict[str, Any]) -> str | None:
    """The price that decides the tier."""
    item = _first_item(obj)
    if item is None:
        return None
    price = item.get("price")
    return price.get("id") if isinstance(price, dict) else None


def _epoch(raw: Any):
    """Epoch seconds -> aware datetime, or None if it will not convert."""
    try:
        return datetime.fromtimestamp(int(raw), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


async def _subscription_terms(subscription_id: str | None) -> dict[str, Any]:
    """The tier, price and period of the subscription a checkout created (#598).

    A checkout session carries no price, so the tier has to come from the
    subscription. It used to come only from `customer.subscription.created` or
    `.updated`, which left a paid customer on FREE whenever the endpoint was not
    subscribed to `created`, the event Stripe sends for a checkout and that the
    setup notes did not list. Asking Stripe here makes the checkout event alone
    enough.

    Empty when there is nothing to ask about, when Stripe is not configured, or
    when the subscription has no price: the tier is then left alone, never guessed.
    A failed request is a 503, which Stripe retries; it runs before anything is
    written, so a retry starts from where this one did.
    """
    if not subscription_id:
        return {}
    try:
        subscription = await stripe_client.retrieve_subscription(subscription_id)
    except stripe_client.BillingNotConfigured:
        logger.warning("cannot resolve a checkout's tier: Stripe is not configured")
        return {}
    except stripe_client.BillingProviderError:
        logger.exception("could not read a checkout's subscription from Stripe")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="subscription lookup failed; Stripe will retry",
        ) from None
    price = _price_id(subscription)
    if not price:
        return {}
    return {
        "tier": tier_for_price(price),
        "price_id": price,
        "period_end": _period_end(subscription),
    }


def _settlement(obj: dict[str, Any], cleared: bool) -> tuple[bool, bool]:
    """Whether a checkout grants access, and whether money actually moved."""
    payment_status = obj.get("payment_status")
    settled = cleared or payment_status in ("paid", "no_payment_required")
    paid = cleared or payment_status == "paid"
    return settled, paid


async def _record_checkout(
    user_id: str, obj: dict[str, Any], event_at: datetime | None, *, cleared: bool
) -> None:
    """A finished checkout. `cleared` is true for `async_payment_succeeded`.

    `completed` does NOT mean paid. Asynchronous methods (bank debits) fire it with
    payment_status "unpaid": the flow finished, the funds have not cleared, and
    granting ACTIVE there would entitle a customer who may never pay. Only a settled
    session grants access; the async_payment_succeeded event that follows a cleared
    debit takes the same path.

    `settled` grants entitlement (ACTIVE), which a trial or 100%-discounted checkout
    earns too (`no_payment_required`). The refund window opens on the first *paid*
    charge (#602), so `paid` excludes that case: otherwise the window would start,
    and could expire, before any money moved, and first-write-wins would stop the
    real charge from correcting it.

    The tier is read from the subscription itself (`_subscription_terms`), never
    guessed: `tier_for_price(None)` would grant PRO to an ENTERPRISE purchase.
    """
    settled, paid = _settlement(obj, cleared)
    terms = await _subscription_terms(obj.get("subscription")) if settled else {}
    await _upsert(
        user_id,
        status_=SubscriptionStatus.ACTIVE if settled else SubscriptionStatus.INCOMPLETE,
        customer_id=obj.get("customer"),
        subscription_id=obj.get("subscription"),
        event_at=event_at,
        **terms,
    )
    # After the upsert created the row; a later charge won't move it.
    if paid:
        await _record_first_paid(user_id, event_at)
    if settled:
        await product_events.record(
            user_id, product_events.CHECKOUT_COMPLETED, once=f"checkout:{obj.get('id')}"
        )


async def _on_checkout_completed(
    user_id: str, obj: dict[str, Any], event_at: datetime | None
) -> None:
    await _record_checkout(user_id, obj, event_at, cleared=False)


async def _on_async_payment_succeeded(
    user_id: str, obj: dict[str, Any], event_at: datetime | None
) -> None:
    await _record_checkout(user_id, obj, event_at, cleared=True)


async def _on_async_payment_failed(
    user_id: str, obj: dict[str, Any], event_at: datetime | None
) -> None:
    """The debit bounced. Without this the INCOMPLETE set at checkout would be the
    only thing standing between a failed payment and entitlement, and a
    `completed`-then-`updated` sequence could quietly flip it to ACTIVE."""
    await _upsert(user_id, status_=SubscriptionStatus.INCOMPLETE, event_at=event_at)


async def _on_subscription_changed(
    user_id: str, obj: dict[str, Any], event_at: datetime | None
) -> None:
    """`customer.subscription.created` and `.updated`.

    No price on an UPDATE means leave the tier alone. `tier_for_price` never returns
    None (it falls back to PRO), so passing it unconditionally would silently
    downgrade an ENTERPRISE tenant on any update that arrived without expanded item
    data. Not guessing high and not guessing wrong are the same principle.
    """
    price = _price_id(obj)
    await _upsert(
        user_id,
        status_=SubscriptionStatus.from_stripe(obj.get("status", "")),
        tier=tier_for_price(price) if price else None,
        customer_id=obj.get("customer"),
        subscription_id=obj.get("id"),
        price_id=price,
        period_end=_period_end(obj),
        cancel_at_period_end=bool(obj.get("cancel_at_period_end", False)),
        event_at=event_at,
    )


async def _on_subscription_deleted(
    user_id: str, obj: dict[str, Any], event_at: datetime | None
) -> None:
    """Tier is deliberately left alone: it records what was bought, and
    `effective_tier` already drops to FREE once the status is CANCELED (#366)."""
    await _upsert(user_id, status_=SubscriptionStatus.CANCELED, event_at=event_at)
    await product_events.record(
        user_id, product_events.SUBSCRIPTION_CANCELLED, once=f"cancel:{obj.get('id')}"
    )


async def _on_payment_failed(
    user_id: str, obj: dict[str, Any], event_at: datetime | None
) -> None:
    """PAST_DUE still grants access: Stripe retries for days, and cutting a paying
    customer off at the first failure is worse (#366)."""
    await _upsert(user_id, status_=SubscriptionStatus.PAST_DUE, event_at=event_at)


#: One handler per event acted on. Everything else is acknowledged and ignored.
_HANDLERS = {
    "checkout.session.completed": _on_checkout_completed,
    "checkout.session.async_payment_succeeded": _on_async_payment_succeeded,
    "checkout.session.async_payment_failed": _on_async_payment_failed,
    "customer.subscription.created": _on_subscription_changed,
    "customer.subscription.updated": _on_subscription_changed,
    "customer.subscription.deleted": _on_subscription_deleted,
    "invoice.payment_failed": _on_payment_failed,
}


async def _handle(
    event_type: str, obj: dict[str, Any], event_at: datetime | None = None
) -> bool:
    """Apply one event. Returns whether it was acted on."""
    handler = _HANDLERS.get(event_type)
    if handler is None:
        return False
    user_id = _user_id_from(obj)
    if not user_id:
        logger.warning(
            "stripe event carried no tenant id; ignoring",
            extra={"event_type": event_type},
        )
        return False
    await handler(user_id, obj, event_at)
    return True


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    """Receive a Stripe event and mirror it onto the local Subscription.

    Not in the OpenAPI schema: it is Stripe's endpoint, not a public API surface.
    """
    payload = await request.body()

    try:
        verify_signature(
            payload, stripe_signature, stripe_client.setting("STRIPE_WEBHOOK_SECRET")
        )
    except SignatureVerificationError as exc:
        # 400, not 500: a bad request, and one that must not be retried.
        #
        # The body is deliberately GENERIC. The specific reason goes to the log,
        # not the caller — "no webhook secret configured" would tell anyone who
        # found the URL that the endpoint is currently unprotected, which is free
        # reconnaissance during the window between deploy and ops setting
        # STRIPE_WEBHOOK_SECRET. Stripe does not need the distinction to retry
        # correctly, so there is nothing to trade away.
        logger.warning("rejected stripe webhook: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "signature verification failed"},
        )

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "malformed event payload"},
        )

    # Valid JSON is not necessarily an event. `"[]"`, `"42"` and `"true"` all parse,
    # and calling .get() on them would raise AttributeError — a 500 for what is
    # plainly a bad request, and one Stripe would then retry.
    if not isinstance(event, dict):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "event payload must be a JSON object"},
        )

    event_type = event.get("type", "")
    data = event.get("data")
    obj = (data.get("object") if isinstance(data, dict) else None) or {}
    if not isinstance(obj, dict):
        obj = {}

    if event_type not in HANDLED_EVENTS:
        # 200, deliberately. A non-2xx makes Stripe retry forever, and an event we
        # do not handle is not a failure.
        logger.info("ignoring unhandled stripe event", extra={"event_type": event_type})
        return {"received": True, "handled": False}

    # `bool` is a subclass of `int`, so `True` would otherwise parse as epoch 1.
    raw_created = event.get("created")
    event_at = (
        _epoch(raw_created)
        if isinstance(raw_created, int | float) and not isinstance(raw_created, bool)
        else None
    )

    handled = await _handle(event_type, obj, event_at)
    return {"received": True, "handled": handled}
