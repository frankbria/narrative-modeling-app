"""Stripe webhook (#367).

Signature verification is exercised for real — the signatures below are computed
with the same HMAC scheme Stripe uses, not mocked — because a mocked
`construct_event` would pass whatever it was told to and prove nothing about the
one endpoint on this service that an unauthenticated caller can reach.

The properties pinned here:

* an unsigned, wrongly-signed, or stale request is rejected, and rejected as 400 so
  Stripe does not retry it forever
* a replayed event is a no-op, because Stripe delivers at least once
* an event type we do not handle is acknowledged, not rejected
* status transitions match the entitlement rules from #366
"""

import hashlib
import hmac
import json
import time

import pytest

from app.billing.stripe_signature import (
    SignatureVerificationError,
    verify_signature,
)
from app.models.subscription import PlanTier, Subscription, SubscriptionStatus

# Outside /api/v1 on purpose — see the include_router comment in app/main.py.
WEBHOOK_PATH = "/webhooks/stripe/webhook"
SECRET = "whsec_test_secret"
TEST_USER = "test_user_123"


def sign(payload: bytes, secret: str = SECRET, timestamp: int | None = None) -> str:
    """Build a Stripe-Signature header the way Stripe does."""
    ts = timestamp if timestamp is not None else int(time.time())
    digest = hmac.new(
        secret.encode(), b"%d.%s" % (ts, payload), hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={digest}"


def event(event_type: str, obj: dict) -> bytes:
    return json.dumps({"type": event_type, "data": {"object": obj}}).encode()


class TestRoutePlacement:
    """The webhook must not sit under /api/v1 (#367 review).

    RateLimitMiddleware limits everything under that prefix and buckets
    unauthenticated callers by IP. Stripe delivers every event for every tenant
    from a small set of IPs, so a burst would 429 — and the retries Stripe then
    sends would bucket too.
    """

    def test_is_not_under_the_rate_limited_prefix(self):
        from app.middleware.rate_limit import RateLimitMiddleware

        class _Url:
            path = WEBHOOK_PATH

        class _Request:
            method = "POST"
            url = _Url()

        assert not RateLimitMiddleware(app=None)._should_limit(_Request())

    @pytest.mark.asyncio
    async def test_is_registered_where_the_tests_post(self, async_authorized_client):
        """Guards the pair: moving the route without moving WEBHOOK_PATH would
        leave every endpoint test posting at a 404 while still passing its
        `status_code == 400` assertions, for the wrong reason.

        Asserts reachability rather than walking `app.routes` — `include_router`
        does not surface a plain `.path` on every route object, so introspection
        here reports a false negative for a route that plainly works.
        """
        response = await async_authorized_client.post(WEBHOOK_PATH, content=b"{}")

        # 400 (unsigned) proves the handler ran. 404 would mean it is not mounted.
        assert response.status_code == 400, response.status_code


class TestSignatureVerification:
    """Pure unit tests — no app, no database."""

    def test_a_valid_signature_passes(self):
        payload = b'{"hello":"world"}'
        verify_signature(payload, sign(payload), SECRET)

    def test_a_wrong_secret_fails(self):
        payload = b'{"hello":"world"}'
        with pytest.raises(SignatureVerificationError):
            verify_signature(payload, sign(payload, "whsec_other"), SECRET)

    def test_a_tampered_payload_fails(self):
        header = sign(b'{"amount":100}')
        with pytest.raises(SignatureVerificationError):
            verify_signature(b'{"amount":999999}', header, SECRET)

    def test_a_stale_timestamp_fails(self):
        """Bounds replay: a captured request stops working once it ages out."""
        payload = b"{}"
        old = int(time.time()) - 10_000
        with pytest.raises(SignatureVerificationError):
            verify_signature(payload, sign(payload, timestamp=old), SECRET)

    def test_a_future_timestamp_beyond_tolerance_fails(self):
        payload = b"{}"
        ahead = int(time.time()) + 10_000
        with pytest.raises(SignatureVerificationError):
            verify_signature(payload, sign(payload, timestamp=ahead), SECRET)

    def test_a_missing_header_fails(self):
        with pytest.raises(SignatureVerificationError):
            verify_signature(b"{}", None, SECRET)

    def test_a_malformed_header_fails(self):
        with pytest.raises(SignatureVerificationError):
            verify_signature(b"{}", "not-a-signature-header", SECRET)

    def test_no_configured_secret_fails_closed(self):
        """Refusing to verify is not the same as verifying.

        The assertion that matters is the SECOND one. Signing with a *different*
        secret fails anyway, so that alone passes whether or not the guard exists —
        my first version of this test did exactly that and my mutation check caught
        it. The real exposure is an attacker signing with the EMPTY secret: without
        an explicit guard the server would use `""` as the HMAC key, and a forged
        signature would verify.
        """
        payload = b"{}"

        with pytest.raises(SignatureVerificationError):
            verify_signature(payload, sign(payload), "")

        forged = sign(payload, secret="")
        with pytest.raises(SignatureVerificationError):
            verify_signature(payload, forged, "")

    def test_any_of_several_v1_signatures_may_match(self):
        """Stripe sends multiple v1 entries while a secret is being rotated."""
        payload = b"{}"
        ts = int(time.time())
        digest = hmac.new(
            SECRET.encode(), b"%d.%s" % (ts, payload), hashlib.sha256
        ).hexdigest()

        # The stale one first, so a check that only looked at the first entry
        # would reject a request Stripe considers valid.
        verify_signature(payload, f"t={ts},v1=deadbeef,v1={digest}", SECRET)

    def test_v0_signatures_are_ignored(self):
        """v0 is a different scheme; comparing against it would be meaningless."""
        payload = b"{}"
        ts = int(time.time())
        with pytest.raises(SignatureVerificationError):
            verify_signature(payload, f"t={ts},v0=whatever", SECRET)


@pytest.mark.asyncio
class TestWebhookEndpoint:
    @pytest.fixture(autouse=True)
    def _secret(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", SECRET, raising=False)

    async def test_rejects_an_unsigned_request(
        self, async_authorized_client, setup_database
    ):
        response = await async_authorized_client.post(WEBHOOK_PATH, content=b"{}")

        # 400 rather than 500: it is a bad request, and Stripe must not retry it.
        assert response.status_code == 400

    async def test_rejects_a_forged_signature(
        self, async_authorized_client, setup_database
    ):
        payload = event("customer.subscription.updated", {})
        response = await async_authorized_client.post(
            WEBHOOK_PATH,
            content=payload,
            headers={"Stripe-Signature": sign(payload, "whsec_attacker")},
        )

        assert response.status_code == 400
        # No subscription may be created off an unverified request.
        assert await Subscription.find(Subscription.user_id == TEST_USER).count() == 0

    async def test_acknowledges_an_unhandled_event(
        self, async_authorized_client, setup_database
    ):
        """A non-2xx would make Stripe retry an event we simply do not act on."""
        payload = event("charge.refunded", {"metadata": {"user_id": TEST_USER}})
        response = await async_authorized_client.post(
            WEBHOOK_PATH,
            content=payload,
            headers={"Stripe-Signature": sign(payload)},
        )

        assert response.status_code == 200
        assert response.json()["handled"] is False

    async def test_checkout_completed_creates_an_active_subscription(
        self, async_authorized_client, setup_database
    ):
        payload = event(
            "checkout.session.completed",
            {
                "client_reference_id": TEST_USER,
                "customer": "cus_1",
                "subscription": "sub_1",
            },
        )
        response = await async_authorized_client.post(
            WEBHOOK_PATH, content=payload, headers={"Stripe-Signature": sign(payload)}
        )

        assert response.status_code == 200
        sub = await Subscription.find_one(Subscription.user_id == TEST_USER)
        assert sub is not None
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.stripe_customer_id == "cus_1"
        assert sub.is_entitled

    async def test_replaying_an_event_is_a_no_op(
        self, async_authorized_client, setup_database
    ):
        """Stripe delivers at least once; a redelivery must not duplicate."""
        payload = event(
            "checkout.session.completed",
            {"client_reference_id": TEST_USER, "customer": "cus_1"},
        )
        headers = {"Stripe-Signature": sign(payload)}

        await async_authorized_client.post(WEBHOOK_PATH, content=payload, headers=headers)
        await async_authorized_client.post(WEBHOOK_PATH, content=payload, headers=headers)

        assert await Subscription.find(Subscription.user_id == TEST_USER).count() == 1

    async def test_subscription_deleted_cancels_without_erasing_the_tier(
        self, async_authorized_client, setup_database
    ):
        """`plan_tier` records what was bought; `effective_tier` handles the drop."""
        await Subscription(
            user_id=TEST_USER,
            plan_tier=PlanTier.PRO,
            status=SubscriptionStatus.ACTIVE,
        ).insert()

        payload = event(
            "customer.subscription.deleted", {"metadata": {"user_id": TEST_USER}}
        )
        await async_authorized_client.post(
            WEBHOOK_PATH, content=payload, headers={"Stripe-Signature": sign(payload)}
        )

        sub = await Subscription.find_one(Subscription.user_id == TEST_USER)
        assert sub is not None
        assert sub.status == SubscriptionStatus.CANCELED
        assert sub.plan_tier == PlanTier.PRO
        assert sub.effective_tier == PlanTier.FREE

    async def test_payment_failed_is_past_due_and_still_entitled(
        self, async_authorized_client, setup_database
    ):
        """Stripe retries for days; access continues meanwhile (#366)."""
        await Subscription(
            user_id=TEST_USER,
            plan_tier=PlanTier.PRO,
            status=SubscriptionStatus.ACTIVE,
        ).insert()

        payload = event(
            "invoice.payment_failed", {"metadata": {"user_id": TEST_USER}}
        )
        await async_authorized_client.post(
            WEBHOOK_PATH, content=payload, headers={"Stripe-Signature": sign(payload)}
        )

        sub = await Subscription.find_one(Subscription.user_id == TEST_USER)
        assert sub is not None
        assert sub.status == SubscriptionStatus.PAST_DUE
        assert sub.is_entitled
        assert sub.effective_tier == PlanTier.PRO

    async def test_an_event_without_a_tenant_id_is_ignored(
        self, async_authorized_client, setup_database
    ):
        """An object we did not originate carries neither marker."""
        payload = event("customer.subscription.updated", {"status": "active"})
        response = await async_authorized_client.post(
            WEBHOOK_PATH, content=payload, headers={"Stripe-Signature": sign(payload)}
        )

        assert response.status_code == 200
        assert response.json()["handled"] is False

    @pytest.mark.parametrize("body", [b"[]", b"42", b"true", b'"a string"', b"null"])
    async def test_valid_json_that_is_not_an_object_is_a_400(
        self, async_authorized_client, setup_database, body
    ):
        """These all parse. Calling .get() on them raises AttributeError — a 500
        for a plainly bad request, which Stripe would then retry (#367 review)."""
        response = await async_authorized_client.post(
            WEBHOOK_PATH, content=body, headers={"Stripe-Signature": sign(body)}
        )

        assert response.status_code == 400

    async def test_checkout_does_not_guess_the_tier(
        self, async_authorized_client, setup_database
    ):
        """A checkout session carries no price without an `expand`, so setting a
        tier here would grant PRO to an ENTERPRISE purchase (#367 review). The
        subscription event that follows resolves it."""
        payload = event(
            "checkout.session.completed",
            {"client_reference_id": TEST_USER, "customer": "cus_x"},
        )
        await async_authorized_client.post(
            WEBHOOK_PATH, content=payload, headers={"Stripe-Signature": sign(payload)}
        )

        sub = await Subscription.find_one(Subscription.user_id == TEST_USER)
        assert sub is not None
        assert sub.status == SubscriptionStatus.ACTIVE
        # Untouched default, not a guess.
        assert sub.plan_tier == PlanTier.FREE

        # …and the follow-up subscription event, which DOES carry the price, sets it.
        import os

        os.environ["STRIPE_PRICE_ENTERPRISE"] = "price_ent"
        try:
            follow_up = event(
                "customer.subscription.updated",
                {
                    "metadata": {"user_id": TEST_USER},
                    "status": "active",
                    "id": "sub_x",
                    "items": {"data": [{"price": {"id": "price_ent"}}]},
                },
            )
            await async_authorized_client.post(
                WEBHOOK_PATH,
                content=follow_up,
                headers={"Stripe-Signature": sign(follow_up)},
            )
        finally:
            os.environ.pop("STRIPE_PRICE_ENTERPRISE", None)

        sub = await Subscription.find_one(Subscription.user_id == TEST_USER)
        assert sub is not None
        assert sub.plan_tier == PlanTier.ENTERPRISE

    async def test_a_first_write_race_is_retried_not_500ed(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """checkout.session.completed and customer.subscription.created arrive
        together for a brand-new tenant, so find-then-insert can lose (#367 review).

        The loser must be retried against the row the winner created, not 500 and
        rely on Stripe's redelivery to paper over it.
        """
        from app.api.routes import billing_webhook

        real_apply = billing_webhook._apply
        calls = {"n": 0}

        # Deliberately NOT a synthetic exception. An earlier version of this test
        # raised DuplicateKeyError, which is what the handler caught — so it was
        # calibrated to the bug rather than to reality. `save()` on an unpersisted
        # duplicate actually raises RevisionIdWasChanged (CLAUDE.md), so the race is
        # produced by really losing it.
        async def _lose_the_first_race(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                await Subscription(user_id=TEST_USER).insert()  # the winner
                await Subscription(user_id=TEST_USER).save()  # raises for real
            return await real_apply(*args, **kwargs)

        monkeypatch.setattr(billing_webhook, "_apply", _lose_the_first_race)

        payload = event(
            "invoice.payment_failed", {"metadata": {"user_id": TEST_USER}}
        )
        response = await async_authorized_client.post(
            WEBHOOK_PATH, content=payload, headers={"Stripe-Signature": sign(payload)}
        )

        assert response.status_code == 200, response.text
        assert calls["n"] == 2, "expected exactly one retry"

        sub = await Subscription.find_one(Subscription.user_id == TEST_USER)
        assert sub is not None
        assert sub.status == SubscriptionStatus.PAST_DUE
        assert await Subscription.find(Subscription.user_id == TEST_USER).count() == 1

    async def test_malformed_json_is_a_400_not_a_500(
        self, async_authorized_client, setup_database
    ):
        payload = b"this is not json"
        response = await async_authorized_client.post(
            WEBHOOK_PATH, content=payload, headers={"Stripe-Signature": sign(payload)}
        )

        assert response.status_code == 400
