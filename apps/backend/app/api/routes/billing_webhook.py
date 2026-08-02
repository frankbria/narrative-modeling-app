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

from beanie.exceptions import RevisionIdWasChanged
from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse
from pymongo.errors import DuplicateKeyError

from app.billing.stripe_signature import (
    SignatureVerificationError,
    verify_signature,
)
from app.config import settings
from app.models.subscription import (
    PlanTier,
    Subscription,
    SubscriptionStatus,
)
from app.utils.datetime import as_utc

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
        (PlanTier.ENTERPRISE, settings.STRIPE_PRICE_ENTERPRISE),
        (PlanTier.PRO, settings.STRIPE_PRICE_PRO),
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
    """Create or update this tenant's subscription, idempotently.

    Only fields actually present on the event are written, so a later event that
    omits something cannot blank what an earlier one established.

    find-then-insert is not atomic and `user_id` is uniquely indexed, so two events
    for a brand-new tenant arriving together — which is the NORMAL flow here,
    `checkout.session.completed` immediately followed by
    `customer.subscription.created` — can both see nothing and both try to insert.
    The loser is retried once against the row the winner created, rather than 500ing
    and relying on Stripe's redelivery to paper over it.
    """
    try:
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
    except (DuplicateKeyError, RevisionIdWasChanged):
        # BOTH, and RevisionIdWasChanged is the one that actually fires here:
        # `_apply` persists via `save()`, and Beanie surfaces a unique-index
        # violation on save() as RevisionIdWasChanged, not DuplicateKeyError.
        # CLAUDE.md records this and `workflow_service.py:96` already catches the
        # pair for the same reason — an earlier version of this handler caught only
        # DuplicateKeyError, so the retry could never fire for the very race it was
        # written for. Verified against a real collection, not assumed.
        #
        # The row exists now; the second attempt takes the update path.
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
    """One find-then-write attempt. Raises DuplicateKeyError if it loses a race."""
    sub = await Subscription.find_one(Subscription.user_id == user_id)
    if sub is None:
        sub = Subscription(user_id=user_id)

    # Stripe does not guarantee ordering between different events. A late
    # `subscription.updated` arriving after `subscription.deleted` would otherwise
    # resurrect a cancelled subscription. Mongo reads datetimes back naive, so the
    # stored value is coerced before comparing (CLAUDE.md).
    if event_at is not None and sub.last_event_at is not None:
        if event_at < as_utc(sub.last_event_at):
            logger.info(
                "ignoring out-of-order stripe event",
                extra={"user_id": user_id},
            )
            return
    if event_at is not None:
        sub.last_event_at = event_at

    if status_ is not None:
        sub.status = status_
    if tier is not None:
        sub.plan_tier = tier
    if customer_id:
        sub.stripe_customer_id = customer_id
    if subscription_id:
        sub.stripe_subscription_id = subscription_id
    if price_id:
        sub.stripe_price_id = price_id
    if period_end is not None:
        sub.current_period_end = period_end
    if cancel_at_period_end is not None:
        sub.cancel_at_period_end = cancel_at_period_end

    await sub.save()


def _period_end(obj: dict[str, Any]):
    """Stripe sends epoch seconds; the model stores a datetime.

    Returns None rather than raising on anything not int-coercible (a future API
    version sending a string, a schema quirk). Everything else in this file is
    defensive about shape for one reason — an uncaught raise is a 500, and Stripe
    retries a non-2xx forever. Losing a period-end is recoverable; a retry loop is
    not.
    """
    raw = obj.get("current_period_end")
    if raw is None:
        return None
    try:
        return datetime.fromtimestamp(int(raw), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        logger.warning("unparseable current_period_end; leaving it unset")
        return None


def _price_id(obj: dict[str, Any]) -> str | None:
    """The price that decides the tier.

    Reads the FIRST line item only. This product sells one plan per subscription —
    there are no bundles or add-ons — so a multi-item subscription is not a shape
    Stripe should ever send us. If that changes, tier attribution has to pick the
    plan-defining item rather than position 0, and this is the function to change.
    """
    items = (obj.get("items") or {}).get("data") or []
    if not items or not isinstance(items[0], dict):
        return None
    return (items[0].get("price") or {}).get("id")


def _epoch(raw: Any):
    """Epoch seconds -> aware datetime, or None if it will not convert."""
    try:
        return datetime.fromtimestamp(int(raw), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


async def _handle(
    event_type: str, obj: dict[str, Any], event_at: datetime | None = None
) -> bool:
    """Apply one event. Returns whether it was acted on."""
    user_id = _user_id_from(obj)
    if not user_id:
        logger.warning(
            "stripe event carried no tenant id; ignoring",
            extra={"event_type": event_type},
        )
        return False

    if event_type in (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    ):
        # `completed` does NOT mean paid. Asynchronous methods (bank debits) fire it
        # with payment_status "unpaid" — the flow finished, the funds have not
        # cleared — and granting ACTIVE there would entitle a customer who may never
        # pay. Only a settled session grants access; the async_payment_succeeded
        # event that follows a cleared debit takes the same path.
        payment_status = obj.get("payment_status")
        settled = event_type == "checkout.session.async_payment_succeeded" or (
            payment_status in ("paid", "no_payment_required")
        )

        # Tier is deliberately NOT set here. A checkout session does not carry the
        # price without an `expand`, and calling tier_for_price(None) would grant
        # PRO to every completed checkout — including an ENTERPRISE purchase.
        # `customer.subscription.created/updated` follows and DOES resolve the
        # price, so that event is the source of truth for tier. This one establishes
        # the link and, once settled, the ACTIVE status.
        await _upsert(
            user_id,
            status_=(
                SubscriptionStatus.ACTIVE if settled else SubscriptionStatus.INCOMPLETE
            ),
            customer_id=obj.get("customer"),
            subscription_id=obj.get("subscription"),
            event_at=event_at,
        )
        return True

    if event_type == "checkout.session.async_payment_failed":
        # The debit bounced. Without this the INCOMPLETE set above would be the only
        # thing standing between a failed payment and entitlement, and a
        # `completed`-then-`updated` sequence could quietly flip it to ACTIVE.
        await _upsert(user_id, status_=SubscriptionStatus.INCOMPLETE, event_at=event_at)
        return True

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        price = _price_id(obj)
        # No price on an UPDATE means leave the tier alone. `tier_for_price` never
        # returns None — it falls back to PRO — so passing it here unconditionally
        # would silently downgrade an ENTERPRISE tenant on any update that arrived
        # without expanded item data. Not guessing high and not guessing wrong are
        # the same principle; this is the second half of it.
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
        return True

    if event_type == "customer.subscription.deleted":
        # Tier is deliberately left alone: it records what was bought, and
        # `effective_tier` already drops to FREE once the status is CANCELED (#366).
        await _upsert(user_id, status_=SubscriptionStatus.CANCELED, event_at=event_at)
        return True

    if event_type == "invoice.payment_failed":
        # PAST_DUE still grants access — Stripe retries for days, and cutting a
        # paying customer off at the first failure is worse (#366).
        await _upsert(user_id, status_=SubscriptionStatus.PAST_DUE, event_at=event_at)
        return True

    return False


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
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET or ""
        )
    except SignatureVerificationError as exc:
        # 400, not 500: this is a bad request, and it must not be retried. The
        # message is safe to return — it says nothing about the secret, only that
        # verification failed.
        logger.warning("rejected stripe webhook: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"signature verification failed: {exc}"},
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
