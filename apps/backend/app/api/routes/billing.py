"""Billing endpoints the frontend calls (#365).

Three routes, all scoped to the caller's own tenant:

* `GET  /billing/status`   — what this tenant is on, and what it has used
* `POST /billing/checkout` — start a paid subscription
* `POST /billing/portal`   — manage an existing one

`user_id` always comes from the authenticated session, never from the request
body. A tenant id accepted from a caller would let anyone start a subscription
against — or read the usage of — someone else's account.
"""

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.nextauth_auth import get_current_user_id
from app.billing import metering, stripe_client
from app.billing.plans import UNLIMITED, limits_for
from app.config import settings
from app.models.subscription import PlanTier, Subscription

logger = logging.getLogger(__name__)

router = APIRouter()


def _assert_known_origin(url: str) -> str:
    """Reject a redirect target that is not one of this app's own origins.

    Stripe sends the browser to these after a hosted flow. Forwarded unvalidated,
    they are an open redirect wearing a legitimate costume: an authenticated caller
    can walk a user through the REAL Stripe checkout — which looks exactly right,
    because it is — and land them on a phishing page at the end. The authentication
    does not help; the attacker is a valid user, and the victim is themselves.

    `BACKEND_CORS_ORIGINS` is already this app's list of known origins, so it is the
    source of truth here too rather than a second list to drift.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="redirect URL must be an absolute http(s) URL",
        )

    origin = f"{parsed.scheme}://{parsed.netloc}"
    allowed = settings.BACKEND_CORS_ORIGINS
    if "*" in allowed:
        # The two settings have OPPOSITE safe defaults, which is worth stating.
        # Unset, BACKEND_CORS_ORIGINS is `["*"]` — a deliberate dev convenience for
        # CORS. As a redirect allowlist a wildcard means "anywhere", so it is
        # refused rather than honoured. Correct, but it makes a fresh checkout that
        # never set the var reject its own URLs, so the message says exactly what to
        # do instead of repeating "not allowed".
        logger.warning(
            "billing redirect refused: BACKEND_CORS_ORIGINS is the wildcard default"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "BACKEND_CORS_ORIGINS is unset (defaulting to '*'), which cannot be "
                "used as a redirect allowlist. Set it to this app's origin(s)."
            ),
        )
    if origin not in allowed:
        logger.warning("rejected billing redirect to unknown origin: %s", origin)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="redirect URL origin is not allowed",
        )
    return url


class CheckoutRequest(BaseModel):
    """Where to send the customer back to. No tenant id — see the module note."""

    tier: PlanTier = Field(
        default=PlanTier.PRO, description="Tier to subscribe to"
    )
    success_url: str = Field(description="Where Stripe returns on success")
    cancel_url: str = Field(description="Where Stripe returns if abandoned")


class PortalRequest(BaseModel):
    return_url: str = Field(description="Where the portal returns the customer")


class BillingStatus(BaseModel):
    configured: bool = Field(
        description="Whether this deployment can start a paid flow at all"
    )
    tier: PlanTier
    status: str | None = None
    cancel_at_period_end: bool = False
    current_period_end: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    limits: dict[str, int] = Field(default_factory=dict)


def _price_for(tier: PlanTier) -> str | None:
    return {
        PlanTier.PRO: settings.STRIPE_PRICE_PRO,
        PlanTier.ENTERPRISE: settings.STRIPE_PRICE_ENTERPRISE,
    }.get(tier)


@router.get("/status", response_model=BillingStatus)
async def billing_status(current_user_id: str = Depends(get_current_user_id)):
    """What this tenant is entitled to and how much of it they have used.

    Works with Stripe unconfigured: `configured` is false and everything else
    describes the FREE tier, which is what the free beta actually runs on.
    """
    sub = await Subscription.find_one(Subscription.user_id == current_user_id)
    tier = sub.effective_tier if sub else PlanTier.FREE
    limits = limits_for(tier)

    return BillingStatus(
        configured=stripe_client.is_configured(),
        tier=tier,
        status=sub.status.value if sub else None,
        cancel_at_period_end=sub.cancel_at_period_end if sub else False,
        current_period_end=(
            sub.current_period_end.isoformat()
            if sub and sub.current_period_end
            else None
        ),
        usage=await metering.usage_summary(current_user_id),
        # UNLIMITED (-1) is passed through rather than omitted, so the client can
        # tell "no ceiling" from "not reported".
        limits={
            metric: limits.limit_for(metric)
            for metric in ("training_runs", "predictions", "uploads")
        },
    )


@router.post("/checkout")
async def start_checkout(
    body: CheckoutRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    """Create a hosted Checkout session and return its URL."""
    if body.tier == PlanTier.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="the free tier does not require a subscription",
        )

    _assert_known_origin(body.success_url)
    _assert_known_origin(body.cancel_url)

    price_id = _price_for(body.tier)
    if not price_id:
        # A missing price is configuration, not a client error — the caller asked
        # for something perfectly valid that this deployment cannot sell.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"no Stripe price configured for the {body.tier.value} tier",
        )

    try:
        return await stripe_client.create_checkout_session(
            user_id=current_user_id,
            price_id=price_id,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    except stripe_client.BillingNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="billing is not available on this deployment",
        ) from exc
    except stripe_client.BillingProviderError as exc:
        # Stripe rejected or could not be reached. 502, not 500: the failure is
        # upstream, and the generic body keeps provider detail out of the response
        # while the log keeps it for us.
        logger.warning("stripe checkout failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="could not start checkout, please try again",
        ) from exc


@router.post("/portal")
async def open_portal(
    body: PortalRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    """Return a link to Stripe's customer portal for this tenant."""
    _assert_known_origin(body.return_url)

    try:
        return await stripe_client.create_portal_session(
            user_id=current_user_id, return_url=body.return_url
        )
    except stripe_client.BillingNotConfigured as exc:
        # Covers both "Stripe is off here" and "this tenant has never subscribed".
        # The portal manages an existing relationship; without one there is nothing
        # to open, and that is not an error the caller can fix by retrying.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="no billing account to manage",
        ) from exc
    except stripe_client.BillingProviderError as exc:
        logger.warning("stripe portal failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="could not open the billing portal, please try again",
        ) from exc


__all__ = ["router", "UNLIMITED"]
