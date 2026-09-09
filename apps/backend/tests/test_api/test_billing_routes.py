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


class TestConfigurationVisibility:
    """#457: an unconfigured deployment must SAY so, not just quietly answer 503.

    Billing degrading gracefully with no Stripe keys is deliberate (ADR-002), so a
    deployment that was never given the keys looks identical to one that does not
    want them — which is how staging shipped with billing inert and nothing noticed.
    `missing_configuration()` is what makes the difference visible in the startup
    log, and a log line is the only checklist that survives a hand-maintained box
    (#594) or a compose file someone edits by hand.
    """

    def test_reports_every_unset_variable(self, monkeypatch):
        for var in (
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "STRIPE_PRICE_PRO",
            "STRIPE_PRICE_ENTERPRISE",
        ):
            monkeypatch.setattr(settings, var, None, raising=False)

        assert stripe_client.missing_configuration() == [
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "STRIPE_PRICE_PRO",
            "STRIPE_PRICE_ENTERPRISE",
        ]

    def test_reports_nothing_when_fully_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)
        monkeypatch.setattr(
            settings, "STRIPE_PRICE_ENTERPRISE", "price_ent", raising=False
        )

        assert stripe_client.missing_configuration() == []

    def test_a_half_configured_deployment_is_the_interesting_case(self, monkeypatch):
        """A secret key with no webhook secret takes money and never entitles anyone.

        `is_configured()` is true here, so `/billing/status` reports `configured: true`
        and checkout works — while every webhook is rejected for want of a signing
        secret. That is strictly worse than no Stripe at all, and it is the case a
        single `is_configured()` boolean cannot express.
        """
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", None, raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)
        monkeypatch.setattr(
            settings, "STRIPE_PRICE_ENTERPRISE", "price_ent", raising=False
        )

        assert stripe_client.is_configured()
        assert stripe_client.missing_configuration() == ["STRIPE_WEBHOOK_SECRET"]

    def test_empty_string_counts_as_unset(self, monkeypatch):
        """Compose passes `${STRIPE_SECRET_KEY:-}`, so an absent value arrives as ''.

        `os.getenv` then returns the empty string rather than None, so a `is not None`
        check would report a blank deployment as fully configured — the exact failure
        this whole guard exists to prevent.
        """
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "", raising=False)
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "  ", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)
        monkeypatch.setattr(
            settings, "STRIPE_PRICE_ENTERPRISE", "price_ent", raising=False
        )

        assert stripe_client.missing_configuration() == [
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
        ]


class TestConfigurationWarning:
    """The startup line must not lie about the one state it exists to catch (#457).

    Saying "checkout answers 503" when `STRIPE_SECRET_KEY` is set is exactly
    backwards: checkout sells, the customer is charged, and the webhook that would
    have entitled them is rejected. An operator reading that line would conclude no
    money can move, which is the opposite of what is happening.
    """

    def test_silent_when_fully_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)
        monkeypatch.setattr(
            settings, "STRIPE_PRICE_ENTERPRISE", "price_ent", raising=False
        )

        assert stripe_client.configuration_warning() is None

    def test_billing_off_says_nothing_can_be_sold(self, monkeypatch):
        for var in (
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "STRIPE_PRICE_PRO",
            "STRIPE_PRICE_ENTERPRISE",
        ):
            monkeypatch.setattr(settings, var, None, raising=False)

        warning = stripe_client.configuration_warning()
        assert warning is not None
        assert "503" in warning
        assert "FREE" in warning
        assert "STRIPE_SECRET_KEY" in warning

    def test_half_configured_says_checkout_can_still_charge(self, monkeypatch):
        """Secret key set, webhook secret missing — the dangerous state."""
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", None, raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)
        monkeypatch.setattr(
            settings, "STRIPE_PRICE_ENTERPRISE", "price_ent", raising=False
        )

        warning = stripe_client.configuration_warning()
        assert warning is not None
        assert "STRIPE_WEBHOOK_SECRET" in warning
        # The claim that must NOT appear: checkout is live here.
        assert "503" not in warning
        assert "charge" in warning.lower()

    def test_a_missing_price_alone_still_warns(self, monkeypatch):
        """One price id missing sells the other tier fine and 503s only that tier."""
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_ENTERPRISE", None, raising=False)

        warning = stripe_client.configuration_warning()
        assert warning is not None
        assert "STRIPE_PRICE_ENTERPRISE" in warning
        assert "STRIPE_PRICE_PRO" not in warning

    def test_the_consequence_matches_what_is_actually_missing(self, monkeypatch):
        """A price-only gap must not be described as a webhook problem.

        Naming every consequence unconditionally points the operator at the wrong
        fix, which for a startup line is the same as being wrong: with the webhook
        secret present, entitlement works fine and only one tier is unsellable.
        """
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_ENTERPRISE", None, raising=False)

        warning = stripe_client.configuration_warning()
        assert warning is not None
        assert "webhook" not in warning.lower(), warning
        assert "enterprise" in warning.lower()

    def test_a_webhook_only_gap_does_not_mention_unsellable_tiers(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", None, raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)
        monkeypatch.setattr(
            settings, "STRIPE_PRICE_ENTERPRISE", "price_ent", raising=False
        )

        warning = stripe_client.configuration_warning()
        assert warning is not None
        assert "tier" not in warning.lower(), warning
        assert "entitle" in warning.lower()

    def test_a_whitespace_only_key_is_not_a_live_checkout(self, monkeypatch):
        """A trailing newline out of an env file must not read as a working key.

        `is_configured()` said yes to any non-empty string, so a blank key took the
        "checkout is live" branch and produced a sentence with no consequence at
        all — while every Stripe call would fail on an invalid API key.
        """
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "  \n", raising=False)
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)
        monkeypatch.setattr(
            settings, "STRIPE_PRICE_ENTERPRISE", "price_ent", raising=False
        )

        assert not stripe_client.is_configured()
        warning = stripe_client.configuration_warning()
        assert warning is not None
        assert "503" in warning
        assert not warning.endswith("but .")

    def test_a_whitespace_only_key_cannot_build_a_client(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "  \n", raising=False)

        with pytest.raises(stripe_client.BillingNotConfigured):
            stripe_client._client()


class TestBlankAndPaddedSettingsAtTheConsumers:
    """The normalisation must reach the code that USES the values, not only the
    code that reports on them (#457, found by claude-review on #597).

    `_setting()` closed this for `STRIPE_SECRET_KEY`, but `_price_for`,
    `tier_for_price` and the webhook's signature check still read `settings.X`
    raw. A trailing newline out of an env file is the ordinary way to get one of
    these, and each consumer fails differently and silently.
    """

    async def test_a_blank_price_is_configuration_not_a_stripe_call(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """`if not price_id` is skipped by whitespace, so the blank goes to Stripe.

        The clean 503 "this deployment cannot sell that tier" becomes an opaque 502
        from the provider rejecting a nonsense price.
        """
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "   ", raising=False)

        resp = await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "pro",
                "success_url": f"{APP_ORIGIN}/ok",
                "cancel_url": f"{APP_ORIGIN}/no",
            },
        )
        assert resp.status_code == 503

    async def test_a_padded_price_still_reaches_stripe_intact(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """`STRIPE_PRICE_PRO=price_pro\\n` must buy the pro plan, not 502."""
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_x", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", " price_pro\n", raising=False)

        seen: dict[str, str] = {}

        async def fake_session(user_id, price_id, success_url, cancel_url):
            seen["price_id"] = price_id
            return {"url": "https://checkout.stripe.com/c/pay/cs", "id": "cs"}

        monkeypatch.setattr(stripe_client, "create_checkout_session", fake_session)

        resp = await async_authorized_client.post(
            CHECKOUT,
            json={
                "tier": "pro",
                "success_url": f"{APP_ORIGIN}/ok",
                "cancel_url": f"{APP_ORIGIN}/no",
            },
        )
        assert resp.status_code == 200
        assert seen["price_id"] == "price_pro"

    def test_a_padded_price_still_maps_back_to_its_tier(self, monkeypatch):
        """The quiet one: an enterprise subscriber silently entitled to PRO.

        `tier_for_price` compares the incoming price against the configured value
        with `==`, and falls back to PRO on no match. A trailing newline on
        STRIPE_PRICE_ENTERPRISE therefore downgrades every enterprise customer,
        with no error anywhere.
        """
        from app.api.routes.billing_webhook import tier_for_price

        monkeypatch.setattr(
            settings, "STRIPE_PRICE_ENTERPRISE", "price_ent\n", raising=False
        )
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)

        assert tier_for_price("price_ent") == PlanTier.ENTERPRISE

    def test_a_blank_configured_price_matches_nothing(self, monkeypatch):
        """A blank configured value must not be compared at all."""
        from app.api.routes.billing_webhook import tier_for_price

        monkeypatch.setattr(settings, "STRIPE_PRICE_ENTERPRISE", "  ", raising=False)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)

        assert tier_for_price("price_pro") == PlanTier.PRO

    def test_nothing_reads_a_stripe_setting_raw(self):
        """The audit that would have caught this, as a guard (#457).

        `settings.STRIPE_*` anywhere outside `stripe_client.setting()` is a reader
        that skips normalisation — which is how the blank/padded fix came to be
        applied to the reporting layer and not to the three consumers. Ten seconds
        of grep, twice missed by hand.
        """
        import re
        from pathlib import Path

        app_dir = Path(__file__).resolve().parents[2] / "app"
        offenders = [
            f"{path.relative_to(app_dir.parent)}:{i}"
            for path in app_dir.rglob("*.py")
            for i, line in enumerate(path.read_text().splitlines(), 1)
            if re.search(r"settings\.STRIPE_", line)
        ]
        assert not offenders, (
            "read these through stripe_client.setting() so a blank or padded env "
            f"value cannot mean different things in different places: {offenders}"
        )
