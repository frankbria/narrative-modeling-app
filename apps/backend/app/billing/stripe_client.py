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


class BillingProviderError(Exception):
    """Stripe rejected the call or could not be reached.

    Separate from `BillingNotConfigured` so a route can answer 502 (upstream
    failed, worth retrying) rather than 503 (not offered here) or 500 (our bug).
    """


class BillingNotConfigured(Exception):
    """Stripe is not set up on this deployment.

    A distinct type so callers can answer 503 ("billing is not available here")
    rather than 500 ("something broke"). Running without Stripe is a supported
    configuration, not a fault.
    """


def setting(name: str) -> str:
    """A billing setting, normalised: blank means unset, and padding is stripped.

    **Every consumer of a `STRIPE_*` value goes through here.** These all arrive
    from environment variables, and there are three ordinary ways to get a bad one:
    compose passes `${STRIPE_SECRET_KEY:-}` so an absent value becomes the empty
    string rather than `None`, an env file happily carries `STRIPE_PRICE_PRO=` or a
    trailing newline, and a pasted value picks up whitespace. Each consumer then
    fails differently and silently:

    * a padded `STRIPE_WEBHOOK_SECRET` is HMAC key material, so every genuine Stripe
      signature mismatches — checkout keeps charging and nobody is ever entitled,
      and the rejection looks exactly like a forged request;
    * a padded `STRIPE_PRICE_ENTERPRISE` never `==` the incoming price, and
      `tier_for_price` falls back to PRO, so enterprise customers are quietly
      downgraded;
    * a blank price is truthy, so `start_checkout`'s `if not price_id` guard is
      skipped and the blank goes to Stripe — an opaque 502 instead of a clean 503.

    Normalising in one place is the point: the predicate that *reports*
    configuration must be the one the consuming code *uses*, or the report is the
    one that gets believed. Fixing it for `STRIPE_SECRET_KEY` alone left exactly
    that gap (#457).
    """
    return (getattr(settings, name, None) or "").strip()


#: The Stripe API version this code is written against, pinned explicitly (#510).
#:
#: It matters because the payload SHAPE changes between versions, and one field
#: this service depends on has already moved: `current_period_end` lives on the
#: subscription *item* here, not on the subscription object, which is why
#: `_period_end()` in the webhook reads both locations. Writing the version down
#: means the next reader knows which reference to check rather than guessing from a
#: blog post.
#:
#: Kept in step with the installed SDK's own default rather than diverging from it
#: — `tests/test_billing/test_stripe_api_version.py` fails if an SDK bump moves the
#: default, so a version change surfaces as a test to read rather than a silently
#: reshaped payload.
STRIPE_API_VERSION = "2026-07-29.dahlia"


def _client():
    """The Stripe SDK, configured on first use.

    Imported inside the function, not at module scope: an import at the top would
    make the SDK a hard requirement of starting the app, which is exactly the
    coupling the free tier must not have.
    """
    key = setting("STRIPE_SECRET_KEY")
    if not key:
        raise BillingNotConfigured("STRIPE_SECRET_KEY is not set")

    import stripe

    stripe.api_key = key
    stripe.api_version = STRIPE_API_VERSION
    return stripe


def is_configured() -> bool:
    """Whether this deployment can start a paid flow at all."""
    return bool(setting("STRIPE_SECRET_KEY"))


#: Every variable the billing surface needs to work end to end, in the order an
#: operator provisions them. `STRIPE_PUBLISHABLE_KEY` is not here: it is read into
#: `Settings` but nothing reads it back, and Checkout is hosted, so the frontend
#: has no Stripe code to hand it to.
_REQUIRED_SETTINGS = (
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_PRO",
    "STRIPE_PRICE_ENTERPRISE",
)

#: What each one being unset actually costs, once `STRIPE_SECRET_KEY` is present
#: and checkout is therefore live. Stated per-variable rather than as one sentence
#: naming every consequence: a startup line that describes a missing price id as a
#: webhook problem points the operator at the wrong fix, which for a diagnostic is
#: the same as being wrong. `STRIPE_SECRET_KEY` has no entry — without it billing
#: is simply off, which `configuration_warning` handles separately.
_CONSEQUENCES = {
    "STRIPE_WEBHOOK_SECRET": (
        "the events that would entitle a paying customer are rejected"
    ),
    "STRIPE_PRICE_PRO": "the pro tier cannot be sold",
    "STRIPE_PRICE_ENTERPRISE": "the enterprise tier cannot be sold",
}


def missing_configuration() -> list[str]:
    """Which billing variables are unset, for the startup log (#457).

    `is_configured()` is one boolean about one key, which cannot express the state
    that actually costs money: a `STRIPE_SECRET_KEY` with no `STRIPE_WEBHOOK_SECRET`
    reports `configured: true`, sells a subscription, and then rejects the event that
    would have entitled anyone — worse than no Stripe at all. Naming each unset
    variable is what makes a half-provisioned deploy visible.

    Blank counts as unset — see `setting`.
    """
    return [name for name in _REQUIRED_SETTINGS if not setting(name)]


def configuration_warning() -> str | None:
    """The startup line for an incompletely configured deployment, or None (#457).

    Two states, and conflating them is worse than saying nothing. With no
    `STRIPE_SECRET_KEY` billing is simply off — checkout answers 503 and nobody can
    be charged. With the secret key present but something else missing, checkout is
    LIVE: it creates real sessions and takes real money, while the webhook that
    would entitle the customer is rejected. Telling an operator "checkout answers
    503" in that second state is exactly backwards, and it is the state most worth
    getting right.
    """
    missing = missing_configuration()
    if not missing:
        return None

    if not is_configured():
        return (
            f"Stripe is not configured (unset: {', '.join(missing)}). "
            "POST /billing/checkout answers 503, webhooks are rejected, and every "
            "tenant stays on FREE limits."
        )

    consequences = [_CONSEQUENCES[name] for name in missing if name in _CONSEQUENCES]
    return (
        f"Stripe is only PARTIALLY configured (unset: {', '.join(missing)}). "
        f"Checkout is live and can charge a customer, but {'; '.join(consequences)}."
    )


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

    try:
        session = await _to_thread(stripe.checkout.Session.create, **params)
    except Exception as exc:  # noqa: BLE001 - narrowed by re-raise below
        _reraise_provider_error(exc)
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

    try:
        session = await _to_thread(
            stripe.billing_portal.Session.create,
            customer=customer_id,
            return_url=return_url,
        )
    except Exception as exc:  # noqa: BLE001 - narrowed by re-raise below
        _reraise_provider_error(exc)
    return {"url": session["url"]}


def _reraise_provider_error(exc: Exception):
    """Turn any Stripe failure into BillingProviderError, preserving the cause.

    Deliberately catches broadly: the SDK raises a family of types
    (CardError, RateLimitError, APIConnectionError, …) and a new one appearing in
    an SDK upgrade must not become an uncaught 500.
    """
    if isinstance(exc, BillingNotConfigured):
        raise exc
    raise BillingProviderError(str(exc)) from exc


async def _to_thread(fn, /, *args, **kwargs):
    """Run a blocking SDK call off the event loop.

    The Stripe SDK's sync client makes real HTTP calls; awaiting them inline would
    block every other request on the worker for the duration.
    """
    import asyncio
    from functools import partial

    return await asyncio.to_thread(partial(fn, *args, **kwargs))
