"""The pinned Stripe API version, and the payload shape that depends on it (#510).

`current_period_end` moved off the subscription object and onto its items. The
webhook reads both locations, but "both" is only safe while the set of shapes is
known — an SDK bump that changes the default API version can move another field the
same way, silently, and the failure mode is a null entitlement field rather than an
error. These tests turn that into a test to read.
"""

import stripe
from stripe._api_version import _ApiVersion

from app.billing.stripe_client import STRIPE_API_VERSION


def test_the_pin_matches_the_installed_sdk_default():
    """If this fails, the SDK bumped its default API version. Do not just edit the
    constant: read that version's changelog for field moves first — #510 is what
    one unnoticed move costs.

    Compared against `_ApiVersion.CURRENT`, **not** `stripe.api_version`.
    `stripe.api_version` is a mutable module global, and `_client()` assigns the pin
    to it — so any test in the session that has built a client turns this assertion
    into `pin == pin`, which passes however far the SDK's real default has moved.
    A tripwire that the code under test can disarm is not a tripwire. `_ApiVersion`
    is private, so a future SDK could remove it; that would fail loudly here, which
    is the right direction for this test.
    """
    assert STRIPE_API_VERSION == _ApiVersion.CURRENT


def test_the_pinned_version_keeps_period_end_on_the_item():
    """The assumption `_period_end()` is built on, asserted against the SDK's own
    generated types rather than from memory."""
    assert "current_period_end" in stripe.SubscriptionItem.__annotations__
    assert "current_period_end" not in stripe.Subscription.__annotations__
