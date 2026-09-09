"""Per-tenant subscription state (#366).

The local mirror of what Stripe believes about a customer. Stripe is the source of
truth; this exists so that a request can decide what a caller is entitled to without
a network round-trip on every call, and so the app still works when Stripe is
unreachable.

Plan limits live in `app/billing/plans.py` rather than here on purpose: a limit is a
product decision that changes without a migration, whereas this document records
what a tenant actually bought.

**How this mirror stays in sync, and what happens when it does not (#458 AC4).**
Webhook delivery is the only automatic sync mechanism. There is no scheduled
reconciliation, deliberately: this service has no scheduler, and Stripe already
retries a failed delivery with backoff for about three days, so a *permanently*
missed event is rare. The two ways a stale row can be wrong are not symmetric, and
each is handled:

* **A missed lapse** — the customer stopped paying and we never heard. The expiry
  check in `is_entitled` catches this without any help from Stripe: entitlement
  runs out with the paid period, so a dropped event fails closed rather than
  granting a tier forever, which is the bug #458 was filed for.
* **A missed renewal** — the customer paid and we never heard. This one fails the
  other way, and no local rule can repair it, because the missing information is
  the payment. `scripts/reconcile_subscriptions.py` re-reads Stripe and rewrites
  what has drifted; run it from cron on the box, or by hand after a Stripe
  incident.
"""

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Annotated

from beanie import (
    Document,
    Indexed,
    Insert,
    Replace,
    Save,
    SaveChanges,
    Update,
    before_event,
)
from pydantic import Field

from app.utils.datetime import as_utc

#: How long past `current_period_end` a subscription still grants its tier.
#:
#: Not zero, because the period end is only as fresh as the last webhook: a
#: renewal event delayed by Stripe's own retry backoff, or a few seconds of clock
#: skew, would otherwise cut off a customer who has paid. Not weeks either — the
#: window is free service. Three days matches the span over which Stripe retries
#: a failed payment before giving up, so a subscription that is going to recover
#: has recovered by the end of it.
ENTITLEMENT_GRACE = timedelta(days=3)


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
            # NOT PAST_DUE, however similar the two names look. `past_due` means a
            # payment failed and Stripe is **still retrying**; serving through it is
            # deliberate (see `is_entitled`). `unpaid` is what a subscription becomes
            # once Stripe has **exhausted** those retries and given up. It is
            # terminal, and merging the two granted permanent paid entitlement to a
            # customer whose payments had permanently failed (#458).
            "unpaid": cls.CANCELED,
            "paused": cls.CANCELED,
            "incomplete": cls.INCOMPLETE,
            "incomplete_expired": cls.INCOMPLETE,
        }
        return mapping.get(status, cls.INCOMPLETE)


class Subscription(Document):
    """What a tenant is entitled to, mirrored from Stripe."""

    # Declared ONCE, here, and deliberately auto-named (`user_id_1`).
    #
    # An earlier draft had both this annotation and an explicit
    # `IndexModel(..., name="uniq_user_id")` in Settings. Two definitions for one key
    # pattern under different names makes Mongo reject the second with
    # `Index already exists with a different name` — a hard startup crash, which I
    # reproduced rather than assumed. Naming it at all is the risk: an auto-named
    # index matches whatever a field-level `Indexed(unique=True)` would already have
    # created, so both a fresh database and one that already has `user_id_1`
    # initialise cleanly. Same trap `app/models/version.py` documents.
    #
    # Unique so a webhook retry cannot create a second row for one tenant — the
    # #367 upsert relies on this for idempotency.
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

    # Stripe does not guarantee ordering between DIFFERENT events, so a late
    # `subscription.updated` can arrive after `subscription.deleted` and resurrect a
    # cancelled subscription. This records the `created` time of the newest event
    # already applied; anything older is ignored (#367). Optional and defaulted, so
    # subscriptions written before it existed still validate.
    last_event_at: datetime | None = Field(
        None, description="`created` of the newest Stripe event applied"
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event(Insert, Replace, Save, SaveChanges, Update)
    def _touch(self) -> None:
        """Bump `updated_at` on every write.

        A hook rather than a note for the #367 webhook to remember: the field is
        only useful if it is always right, and "the caller sets it" is a rule that
        holds until the first caller forgets. Nothing updates a Subscription yet,
        which is exactly why this is the moment to make it automatic.

        All five write events are registered deliberately. An earlier version listed
        only Replace/SaveChanges/Update, and `save()` — the obvious way to persist a
        change — emits `Save`, so the hook silently never fired. The test caught it
        only after a sleep was added: without a gap, insert and save land in the
        same millisecond and an equal timestamp looks like success.
        """
        self.updated_at = datetime.now(UTC)

    class Settings:
        name = "subscriptions"
        indexes = [
            # user_id's unique index is declared on the field itself — see the
            # comment there for why it must not also appear here.
            "stripe_customer_id",
            "stripe_subscription_id",
        ]

    @property
    def is_entitled(self) -> bool:
        """Whether this subscription currently grants its tier's entitlements.

        Two conditions, both required.

        **The status must be an entitled one.** PAST_DUE deliberately counts: Stripe
        retries a failed payment for days, and cutting a paying customer off at the
        first failure is worse than serving them through a card that is about to be
        updated. CANCELED — which `from_stripe` now maps `unpaid` onto — does not.

        **The paid period must not have lapsed**, beyond `ENTITLEMENT_GRACE`. Status
        alone is a value that is only as current as the last webhook that arrived,
        and nothing in this service reconciles against Stripe on a schedule (see the
        class docstring), so without an expiry a single dropped event would grant a
        tier indefinitely.

        A `current_period_end` of `None` falls back to `updated_at` — the last time
        any Stripe event touched this row — plus the same grace. It is deliberately
        **not** unbounded. `checkout.session.completed` establishes ACTIVE before the
        `customer.subscription.created` that carries the period end, so the field is
        legitimately absent for a few seconds on every new purchase and revoking
        immediately would downgrade a customer at the instant they paid. But
        "unknown expiry means entitled forever" is the #458 bug wearing a different
        hat: the follow-up event is exactly the kind Stripe can drop for good, and
        that row would then hold paid access with no expiry and no event left to
        arrive. Bounding the gap by the last thing we actually heard covers the
        ordering window without reopening the hole.

        Mongo reads datetimes back naive, so both stored values are coerced with
        `as_utc` before being compared against an aware now (CLAUDE.md).
        """
        if self.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE):
            return False
        lapses = self.current_period_end or self.updated_at
        return as_utc(lapses) + ENTITLEMENT_GRACE > datetime.now(UTC)

    @property
    def effective_tier(self) -> PlanTier:
        """The tier to enforce against — FREE unless the subscription is entitled.

        This is what callers should read. Using `plan_tier` directly would keep
        serving PRO limits to a canceled subscription, since the tier field records
        what was bought rather than whether it is still paid for.
        """
        return self.plan_tier if self.is_entitled else PlanTier.FREE
