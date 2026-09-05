"""Billing endpoints (#365).

The property that matters most here is tenancy: `user_id` comes from the session,
never the request body. A tenant id accepted from a caller would let anyone start a
subscription against — or read the usage of — someone else's account.

Second is that **everything works with Stripe unconfigured**. That is not a
degraded mode, it is what the free invite-only beta actually runs on, so `/status`
must answer and the paid routes must say "not available here" rather than 500.
"""

import pytest

from app.billing import stripe_client
from app.config import settings
from app.models.subscription import PlanTier, Subscription, SubscriptionStatus

# The origin guard validates against BACKEND_CORS_ORIGINS, so the redirect URLs
# below use an origin the test environment actually allows.
APP_ORIGIN = "http://localhost:3000"


@pytest.fixture(autouse=True)
def _allow_app_origin(monkeypatch):
    """Pin the redirect allowlist to APP_ORIGIN for every test in this module.

    Unset, BACKEND_CORS_ORIGINS resolves to the wildcard `["*"]`, which the
    origin guard refuses outright (400) — so without this, ten of these tests
    passed only on machines whose apps/backend/.env happened to set the var,
    and would have failed the moment they ran anywhere else. They never did:
    this file was outside the required job's path allowlist until #445.
    The two tests that exercise the wildcard and unknown-origin paths set their
    own value inside the test body, which runs after this fixture.
    """
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", APP_ORIGIN)

STATUS = "/api/v1/billing/status"
CHECKOUT = "/api/v1/billing/checkout"
PORTAL = "/api/v1/billing/portal"
TEST_USER = "test_user_123"


@pytest.mark.asyncio
class TestStatusWithoutStripe:
    """The free-beta configuration: no Stripe keys at all."""

    @pytest.fixture(autouse=True)
    def _no_stripe(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", None, raising=False)

    async def test_reports_free_and_unconfigured(
        self, async_authorized_client, setup_database
    ):
        response = await async_authorized_client.get(STATUS)

        assert response.status_code == 200
        body = response.json()
        assert body["configured"] is False
        assert body["tier"] == PlanTier.FREE.value

    async def test_reports_limits_and_usage(
        self, async_authorized_client, setup_database
    ):
        from app.billing import metering

        await metering.record(TEST_USER, "predictions", amount=3)

        body = (await async_authorized_client.get(STATUS)).json()

        assert body["usage"]["predictions"] == 3
        assert body["limits"]["predictions"] > 0

    async def test_checkout_is_unavailable_not_broken(
        self, async_authorized_client, setup_database
    ):
        """503, not 500: running without Stripe is a supported configuration."""
        response = await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "pro",
                "success_url": "http://localhost:3000/ok",
                "cancel_url": "http://localhost:3000/no",
            },
        )

        assert response.status_code == 503

    async def test_portal_is_unavailable_not_broken(
        self, async_authorized_client, setup_database
    ):
        response = await async_authorized_client.post(
            PORTAL, json={"return_url": "http://localhost:3000/settings"}
        )

        assert response.status_code == 503


@pytest.mark.asyncio
class TestStatusReflectsTheSubscription:
    async def test_an_entitled_subscription_reports_its_tier(
        self, async_authorized_client, setup_database
    ):
        await Subscription(
            user_id=TEST_USER,
            plan_tier=PlanTier.PRO,
            status=SubscriptionStatus.ACTIVE,
        ).insert()

        body = (await async_authorized_client.get(STATUS)).json()

        assert body["tier"] == PlanTier.PRO.value
        assert body["status"] == "active"

    async def test_a_cancelled_subscription_reports_free(
        self, async_authorized_client, setup_database
    ):
        """`effective_tier`, not `plan_tier` — the UI must not offer PRO limits to
        someone whose subscription has lapsed."""
        await Subscription(
            user_id=TEST_USER,
            plan_tier=PlanTier.PRO,
            status=SubscriptionStatus.CANCELED,
        ).insert()

        body = (await async_authorized_client.get(STATUS)).json()

        assert body["tier"] == PlanTier.FREE.value
        assert body["status"] == "canceled"

    async def test_unlimited_is_reported_as_the_sentinel(
        self, async_authorized_client, setup_database
    ):
        """Passed through rather than omitted, so the client can tell "no ceiling"
        from "not reported"."""
        await Subscription(
            user_id=TEST_USER,
            plan_tier=PlanTier.ENTERPRISE,
            status=SubscriptionStatus.ACTIVE,
        ).insert()

        body = (await async_authorized_client.get(STATUS)).json()

        assert body["limits"]["training_runs"] == -1


@pytest.mark.asyncio
class TestCheckout:
    @pytest.fixture(autouse=True)
    def _stripe_on(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)

    async def test_the_free_tier_is_rejected(
        self, async_authorized_client, setup_database
    ):
        response = await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "free",
                "success_url": "http://localhost:3000/ok",
                "cancel_url": "http://localhost:3000/no",
            },
        )

        assert response.status_code == 400

    async def test_a_tier_with_no_configured_price_is_503(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """Configuration, not a client error — the caller asked for something
        perfectly valid that this deployment cannot sell."""
        monkeypatch.setattr(
            settings, "STRIPE_PRICE_ENTERPRISE", None, raising=False
        )

        response = await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "enterprise",
                "success_url": "http://localhost:3000/ok",
                "cancel_url": "http://localhost:3000/no",
            },
        )

        assert response.status_code == 503

    async def test_the_session_carries_both_tenant_markers(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """The webhook reads `client_reference_id` off the checkout session and
        `subscription_data.metadata.user_id` off the subscription object. Setting
        only one would silently drop half the events (#367)."""
        captured: dict = {}

        def _fake_create(**kwargs):
            captured.update(kwargs)
            return {"id": "cs_1", "url": "https://checkout.stripe.test/cs_1"}

        monkeypatch.setattr(
            stripe_client,
            "_client",
            lambda: type(
                "S",
                (),
                {"checkout": type("C", (), {"Session": type("Sess", (), {"create": staticmethod(_fake_create)})})},
            ),
        )

        response = await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "pro",
                "success_url": "http://localhost:3000/ok",
                "cancel_url": "http://localhost:3000/no",
            },
        )

        assert response.status_code == 200
        assert response.json()["url"].startswith("https://checkout.stripe.test/")
        assert captured["client_reference_id"] == TEST_USER
        assert captured["subscription_data"]["metadata"]["user_id"] == TEST_USER

    async def test_an_existing_customer_is_reused(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """A second subscription must not create a duplicate customer with its own
        billing history."""
        await Subscription(
            user_id=TEST_USER, stripe_customer_id="cus_existing"
        ).insert()

        captured: dict = {}

        def _fake_create(**kwargs):
            captured.update(kwargs)
            return {"id": "cs_2", "url": "https://checkout.stripe.test/cs_2"}

        monkeypatch.setattr(
            stripe_client,
            "_client",
            lambda: type(
                "S",
                (),
                {"checkout": type("C", (), {"Session": type("Sess", (), {"create": staticmethod(_fake_create)})})},
            ),
        )

        await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "pro",
                "success_url": "http://localhost:3000/ok",
                "cancel_url": "http://localhost:3000/no",
            },
        )

        assert captured["customer"] == "cus_existing"

    async def test_the_tenant_id_cannot_be_supplied_by_the_caller(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """The request schema has no tenant field, and an attempt to smuggle one
        must not reach Stripe. Otherwise anyone could subscribe on someone else's
        behalf — or, on /status, read their usage."""
        captured: dict = {}

        def _fake_create(**kwargs):
            captured.update(kwargs)
            return {"id": "cs_3", "url": "https://checkout.stripe.test/cs_3"}

        monkeypatch.setattr(
            stripe_client,
            "_client",
            lambda: type(
                "S",
                (),
                {"checkout": type("C", (), {"Session": type("Sess", (), {"create": staticmethod(_fake_create)})})},
            ),
        )

        await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "pro",
                "success_url": "http://localhost:3000/ok",
                "cancel_url": "http://localhost:3000/no",
                "user_id": "somebody-else",
                "client_reference_id": "somebody-else",
            },
        )

        assert captured["client_reference_id"] == TEST_USER


@pytest.mark.asyncio
class TestRedirectValidation:
    """Redirect targets must be this app's own origins (#365 review).

    Unvalidated, they are an open redirect wearing a legitimate costume: an
    authenticated caller walks a victim through the REAL Stripe checkout — which
    looks right, because it is — and lands them on a phishing page at the end.
    Authentication does not help; the attacker is a valid user.
    """

    @pytest.fixture(autouse=True)
    def _stripe_on(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)

    @pytest.mark.parametrize(
        "bad_url",
        [
            "https://phishing.example/steal",
            "http://localhost:3000.evil.test/",
            "javascript:alert(1)",
            "//protocol-relative.example",
            "/relative/only",
            "",
        ],
    )
    async def test_checkout_rejects_a_foreign_redirect(
        self, async_authorized_client, setup_database, bad_url
    ):
        response = await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "pro",
                "success_url": bad_url,
                "cancel_url": "http://localhost:3000/ok",
            },
        )

        assert response.status_code == 400, response.text

    async def test_checkout_rejects_a_foreign_cancel_url_too(
        self, async_authorized_client, setup_database
    ):
        """Both URLs are attacker-controllable; validating only one is no
        validation at all."""
        response = await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "pro",
                "success_url": "http://localhost:3000/ok",
                "cancel_url": "https://phishing.example/steal",
            },
        )

        assert response.status_code == 400

    async def test_portal_rejects_a_foreign_return_url(
        self, async_authorized_client, setup_database
    ):
        await Subscription(
            user_id=TEST_USER, stripe_customer_id="cus_x"
        ).insert()

        response = await async_authorized_client.post(
            PORTAL, json={"return_url": "https://phishing.example/steal"}
        )

        assert response.status_code == 400

    async def test_the_wildcard_default_explains_itself(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """BACKEND_CORS_ORIGINS defaults to `["*"]` — fine for CORS in dev, useless
        as a redirect allowlist. Refusing is correct; refusing with "origin is not
        allowed" would send someone hunting the wrong problem (#365 review).
        """
        monkeypatch.setenv("BACKEND_CORS_ORIGINS", "")

        response = await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "pro",
                "success_url": f"{APP_ORIGIN}/ok",
                "cancel_url": f"{APP_ORIGIN}/no",
            },
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "BACKEND_CORS_ORIGINS" in detail
        assert "unset" in detail

    async def test_a_known_origin_is_accepted(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """The guard must not reject the app's own URLs, or it breaks the feature
        rather than protecting it."""
        captured: dict = {}

        def _fake_create(**kwargs):
            captured.update(kwargs)
            return {"id": "cs_ok", "url": "https://checkout.stripe.test/ok"}

        monkeypatch.setattr(
            stripe_client,
            "_client",
            lambda: type(
                "S",
                (),
                {"checkout": type("C", (), {"Session": type("Sess", (), {"create": staticmethod(_fake_create)})})},
            ),
        )

        response = await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "pro",
                "success_url": "http://localhost:3000/settings/billing?checkout=success",
                "cancel_url": "http://localhost:3000/settings/billing",
            },
        )

        assert response.status_code == 200, response.text


@pytest.mark.asyncio
class TestProviderErrors:
    """A Stripe failure is 502, not 500 (#365 review)."""

    @pytest.fixture(autouse=True)
    def _stripe_on(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)

    async def test_a_stripe_failure_is_a_502(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        def _boom(**_kwargs):
            raise RuntimeError("stripe is unreachable")

        monkeypatch.setattr(
            stripe_client,
            "_client",
            lambda: type(
                "S",
                (),
                {"checkout": type("C", (), {"Session": type("Sess", (), {"create": staticmethod(_boom)})})},
            ),
        )

        response = await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "pro",
                "success_url": "http://localhost:3000/ok",
                "cancel_url": "http://localhost:3000/no",
            },
        )

        assert response.status_code == 502
        # The provider's message stays in the log, not the response body.
        assert "unreachable" not in response.text


@pytest.mark.asyncio
class TestPortal:
    @pytest.fixture(autouse=True)
    def _stripe_on(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)

    async def test_a_tenant_with_no_customer_gets_503(
        self, async_authorized_client, setup_database
    ):
        """The portal manages an existing relationship; there is nothing to open."""
        response = await async_authorized_client.post(
            PORTAL, json={"return_url": "http://localhost:3000/settings"}
        )

        assert response.status_code == 503

    async def test_returns_a_portal_url_for_a_known_customer(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        await Subscription(
            user_id=TEST_USER, stripe_customer_id="cus_portal"
        ).insert()

        captured: dict = {}

        def _fake_create(**kwargs):
            captured.update(kwargs)
            return {"url": "https://billing.stripe.test/p/session"}

        monkeypatch.setattr(
            stripe_client,
            "_client",
            lambda: type(
                "S",
                (),
                {"billing_portal": type("B", (), {"Session": type("Sess", (), {"create": staticmethod(_fake_create)})})},
            ),
        )

        response = await async_authorized_client.post(
            PORTAL, json={"return_url": "http://localhost:3000/settings"}
        )

        assert response.status_code == 200
        assert response.json()["url"].startswith("https://billing.stripe.test/")
        assert captured["customer"] == "cus_portal"


class TestLazyInitialisation:
    """Importing must not require configuration (#365).

    Secret-less Docker builds and the free beta both run with no STRIPE_SECRET_KEY,
    and the router imports this module at startup.
    """

    def test_importing_does_not_touch_configuration(self):
        import importlib

        importlib.reload(stripe_client)  # must not raise

    def test_client_raises_a_typed_error_when_unset(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", None, raising=False)

        with pytest.raises(stripe_client.BillingNotConfigured):
            stripe_client._client()

    def test_is_configured_reflects_the_key(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", None, raising=False)
        assert not stripe_client.is_configured()

        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        assert stripe_client.is_configured()
