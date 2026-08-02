"""Stripe client and the two hosted flows we use (#365).

**Lazy initialisation is the whole point of this module.** `next build`-style
secret-less Docker builds and the free invite-only beta both run with no
`STRIPE_SECRET_KEY` at all, and importing this module must not care. The client is
constructed on first use, so importing it — which the router does at startup —
touches no configuration and cannot fail.

Both flows are *hosted*: Stripe collects the card and manages the subscription on
its own pages. This service never sees a card number, which is the reason to use
Checkout and the customer portal rather than building either.
"""

import logging
from typing import Any

from app.config import settings
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


class BillingNotConfigured(Exception):
    """Stripe is not set up on this deployment.

    A distinct type so callers can answer 503 ("billing is not available here")
    rather than 500 ("something broke"). Running without Stripe is a supported
    configuration, not a fault.
    """


def _client():
    """The Stripe SDK, configured on first use.

    Imported inside the function, not at module scope: an import at the top would
    make the SDK a hard requirement of starting the app, which is exactly the
    coupling the free tier must not have.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise BillingNotConfigured("STRIPE_SECRET_KEY is not set")

    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def is_configured() -> bool:
    """Whether this deployment can start a paid flow at all."""
    return bool(settings.STRIPE_SECRET_KEY)


async def _customer_id_for(user_id: str) -> str | None:
    """The Stripe customer we already know about for this tenant, if any."""
    sub = await Subscription.find_one(Subscription.user_id == user_id)
    return sub.stripe_customer_id if sub else None


async def create_checkout_session(
    user_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> dict[str, Any]:
    """Start a hosted Checkout for this tenant.

    `client_reference_id` and `subscription_data.metadata.user_id` are both set, and
    both matter: the webhook (#367) reads the first off the checkout session and the
    second off the subscription object, and an event carrying neither is treated as
    one we did not originate. Setting only one would silently drop half the events.

    Reuses the tenant's existing Stripe customer when there is one, so a second
    subscription does not create a duplicate customer with a separate billing
    history.
    """
    stripe = _client()

    params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": user_id,
        "subscription_data": {"metadata": {"user_id": user_id}},
    }

    existing = await _customer_id_for(user_id)
    if existing:
        params["customer"] = existing

    session = await _to_thread(stripe.checkout.Session.create, **params)
    return {"id": session["id"], "url": session["url"]}


async def create_portal_session(user_id: str, return_url: str) -> dict[str, Any]:
    """A link to Stripe's customer portal for self-service management.

    Requires a known Stripe customer: the portal manages an existing relationship,
    so a tenant who has never subscribed has nothing to manage.
    """
    stripe = _client()

    customer_id = await _customer_id_for(user_id)
    if not customer_id:
        raise BillingNotConfigured("this tenant has no Stripe customer")

    session = await _to_thread(
        stripe.billing_portal.Session.create,
        customer=customer_id,
        return_url=return_url,
    )
    return {"url": session["url"]}


async def _to_thread(fn, /, *args, **kwargs):
    """Run a blocking SDK call off the event loop.

    The Stripe SDK's sync client makes real HTTP calls; awaiting them inline would
    block every other request on the worker for the duration.
    """
    import asyncio
    from functools import partial

    return await asyncio.to_thread(partial(fn, *args, **kwargs))
