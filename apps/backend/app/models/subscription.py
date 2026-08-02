"""Per-tenant subscription state (#366).

The local mirror of what Stripe believes about a customer. Stripe is the source of
truth; this exists so that a request can decide what a caller is entitled to without
a network round-trip on every call, and so the app still works when Stripe is
unreachable.

Plan limits live in `app/config/plans.py` rather than here on purpose: a limit is a
product decision that changes without a migration, whereas this document records
what a tenant actually bought.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated

from beanie import Document, Indexed
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class PlanTier(str, Enum):
    """Tiers a tenant can be on.

    `FREE` is the absence of a paid plan, not a separate purchase — a tenant with no
    Subscription document at all is treated as FREE, so enforcement never depends on
    a backfill having run.
    """

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Mirrors the Stripe subscription statuses this app acts on.

    Deliberately a subset: Stripe also emits `trialing`, `incomplete`,
    `incomplete_expired`, `unpaid` and `paused`. Mapping the ones we do not model
    onto a status we do would silently grant or revoke access, so `from_stripe()`
    maps them explicitly and anything unrecognised becomes INCOMPLETE (no access)
    rather than defaulting to ACTIVE.
    """

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"

    @classmethod
    def from_stripe(cls, status: str) -> "SubscriptionStatus":
        """Map a Stripe status onto ours, failing closed."""
        mapping = {
            "active": cls.ACTIVE,
            "trialing": cls.ACTIVE,  # a trial is entitled access
            "past_due": cls.PAST_DUE,
            "canceled": cls.CANCELED,
            "unpaid": cls.PAST_DUE,
            "paused": cls.CANCELED,
            "incomplete": cls.INCOMPLETE,
            "incomplete_expired": cls.INCOMPLETE,
        }
        return mapping.get(status, cls.INCOMPLETE)


class Subscription(Document):
    """What a tenant is entitled to, mirrored from Stripe."""

    user_id: Annotated[str, Indexed(unique=True)] = Field(
        description="Owning tenant. Unique: one subscription per tenant."
    )

    plan_tier: PlanTier = Field(
        default=PlanTier.FREE, description="Tier this tenant is entitled to"
    )
    status: SubscriptionStatus = Field(
        default=SubscriptionStatus.INCOMPLETE,
        description="Lifecycle state, mirrored from Stripe",
    )

    # Stripe identifiers. Optional because a tenant can exist on FREE without ever
    # having reached Stripe.
    stripe_customer_id: Annotated[str | None, Indexed()] = Field(
        None, description="Stripe customer id, once one exists"
    )
    stripe_subscription_id: Annotated[str | None, Indexed()] = Field(
        None, description="Stripe subscription id, once one exists"
    )
    stripe_price_id: str | None = Field(
        None, description="Stripe price the tenant is on"
    )

    current_period_end: datetime | None = Field(
        None, description="When the paid period lapses; drives metering rollover"
    )
    cancel_at_period_end: bool = Field(
        default=False,
        description="Stripe's 'cancel when the period ends' flag — still entitled until then",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "subscriptions"
        indexes = [
            # Unique so a webhook retry cannot create a second row for one tenant —
            # the upsert path relies on this to be idempotent.
            IndexModel([("user_id", ASCENDING)], unique=True, name="uniq_user_id"),
            "stripe_customer_id",
            "stripe_subscription_id",
        ]

    @property
    def is_entitled(self) -> bool:
        """Whether this subscription currently grants its tier's entitlements.

        PAST_DUE deliberately still counts. Stripe retries a failed payment for days;
        cutting a paying customer off at the first failure is worse than serving
        them through a card that is about to be updated. CANCELED does not count.
        """
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE)

    @property
    def effective_tier(self) -> PlanTier:
        """The tier to enforce against — FREE unless the subscription is entitled.

        This is what callers should read. Using `plan_tier` directly would keep
        serving PRO limits to a canceled subscription, since the tier field records
        what was bought rather than whether it is still paid for.
        """
        return self.plan_tier if self.is_entitled else PlanTier.FREE
