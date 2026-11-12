"""#494 AC1, AC4: mail goes out through Resend's HTTP API, and only when configured.

The transport is the seam: every test hands the service an `httpx.MockTransport`, so the
request that would reach api.resend.com is the thing asserted on.
"""

import json
import logging

import httpx
import pytest

from app.services import email_service


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("EMAIL_FROM", "SheetPredict <jobs@mail.example>")


def _resend(monkeypatch, handler) -> list[httpx.Request]:
    """Route the service's client to `handler` and collect what it was sent."""
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(
        email_service,
        "_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(record)),
    )
    return seen


def _accepted(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"id": "email_1"})


# Resend's documented answer to a key reused with different content
# (https://resend.com/docs/dashboard/emails/idempotency-keys).
_KEY_REUSED = {
    "statusCode": 409,
    "name": "invalid_idempotent_request",
    "message": "Same idempotency key used with a different request payload.",
}


class TestConfiguration:
    def test_no_key_means_not_configured(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "")
        monkeypatch.setenv("EMAIL_FROM", "jobs@mail.example")

        assert email_service.is_configured() is False
        assert "RESEND_API_KEY" in (email_service.configuration_warning() or "")

    def test_a_key_without_a_sender_is_not_configured(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        monkeypatch.setenv("EMAIL_FROM", "   ")

        assert email_service.is_configured() is False
        assert "EMAIL_FROM" in (email_service.configuration_warning() or "")

    def test_key_and_sender_are_configured(self, configured):
        assert email_service.is_configured() is True
        assert email_service.configuration_warning() is None


class TestSend:
    async def test_an_unconfigured_send_makes_no_request(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "")
        seen = _resend(monkeypatch, _accepted)

        sent = await email_service.send("a@b.example", "Hello", "Body", idempotency_key="k")

        assert sent is False
        assert seen == []

    async def test_a_send_posts_the_message_to_resend(self, configured, monkeypatch):
        seen = _resend(monkeypatch, _accepted)

        sent = await email_service.send(
            "a@b.example", "Hello", "Body", idempotency_key="training-m1-completed"
        )

        assert sent is True
        (request,) = seen
        assert str(request.url) == "https://api.resend.com/emails"
        assert request.headers["authorization"] == "Bearer re_test_key"
        assert request.headers["idempotency-key"] == "training-m1-completed"
        assert json.loads(request.content) == {
            "from": "SheetPredict <jobs@mail.example>",
            "to": ["a@b.example"],
            "subject": "Hello",
            "text": "Body",
        }

    async def test_a_padded_key_is_sent_without_its_padding(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", " re_test_key\n")
        monkeypatch.setenv("EMAIL_FROM", "jobs@mail.example")
        seen = _resend(monkeypatch, _accepted)

        await email_service.send("a@b.example", "Hello", "Body", idempotency_key="k")

        assert seen[0].headers["authorization"] == "Bearer re_test_key"

    async def test_a_refusal_is_false_not_an_exception(self, configured, monkeypatch, caplog):
        _resend(monkeypatch, lambda _: httpx.Response(422, json={"message": "bad a@b.example"}))

        with caplog.at_level(logging.WARNING, logger=email_service.logger.name):
            sent = await email_service.send("a@b.example", "Hello", "Body", idempotency_key="k")

        assert sent is False
        assert "HTTPStatusError" in caplog.text

    async def test_a_refused_reuse_of_a_key_is_a_duplicate_not_a_lost_mail(
        self, configured, monkeypatch, caplog
    ):
        # #1204: the task and the reaper report one failure in different words under one
        # key. Resend refuses the second; the first is the mail the owner got.
        _resend(monkeypatch, lambda _: httpx.Response(409, json=_KEY_REUSED))

        with caplog.at_level(logging.INFO, logger=email_service.logger.name):
            sent = await email_service.send("a@b.example", "Hello", "Body", idempotency_key="k")

        assert sent is True
        # Only this service's lines: httpx logs each request itself once the app has
        # configured logging, which depends on what ran earlier in the session.
        own = [record for record in caplog.records if record.name == email_service.logger.name]
        assert [record.levelname for record in own] == ["INFO"]
        assert "not sent" not in caplog.text
        assert "already used" in caplog.text
        assert "a@b.example" not in caplog.text

    @pytest.mark.parametrize(
        "refusal",
        [
            # The first request is still in flight: whether it delivers is not known here.
            httpx.Response(409, json={"statusCode": 409, "name": "concurrent_idempotent_requests"}),
            httpx.Response(422, json={"statusCode": 422, "name": "invalid_idempotent_request"}),
            httpx.Response(409, text="<html>conflict</html>"),
            httpx.Response(409, json=["invalid_idempotent_request"]),
        ],
        ids=["first-still-in-flight", "another-status", "not-json", "not-an-object"],
    )
    async def test_any_other_refusal_is_still_a_mail_that_was_not_sent(
        self, configured, monkeypatch, caplog, refusal
    ):
        _resend(monkeypatch, lambda _: refusal)

        with caplog.at_level(logging.INFO, logger=email_service.logger.name):
            sent = await email_service.send("a@b.example", "Hello", "Body", idempotency_key="k")

        assert sent is False
        assert "Email not sent: HTTPStatusError" in caplog.text

    async def test_an_unreachable_provider_is_false_not_an_exception(self, configured, monkeypatch):
        def unreachable(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route", request=request)

        _resend(monkeypatch, unreachable)

        assert await email_service.send("a@b.example", "Hello", "Body", idempotency_key="k") is False

    async def test_a_failure_logs_neither_the_address_nor_the_key(
        self, configured, monkeypatch, caplog
    ):
        _resend(monkeypatch, lambda _: httpx.Response(500, text="boom a@b.example"))

        with caplog.at_level(logging.DEBUG, logger=email_service.logger.name):
            await email_service.send("a@b.example", "Hello", "Body", idempotency_key="k")

        assert "a@b.example" not in caplog.text
        assert "re_test_key" not in caplog.text
