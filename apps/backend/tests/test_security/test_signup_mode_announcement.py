"""#880: invite mode with nobody on the list admits nobody, and the log says so.

A hand-run `docker compose up` skips the deploy preflight that refuses this. The
backend then logged "Signup mode: invite" exactly as it does with a populated list.
"""

import logging

import pytest

from app import main

pytestmark = pytest.mark.unit

ADDRESSES = "alice@example.com,bob@example.com"


def _announced(monkeypatch, caplog, mode: str, allowlist: str) -> list[logging.LogRecord]:
    monkeypatch.setenv("SIGNUP_MODE", mode)
    monkeypatch.setenv("INVITE_ALLOWLIST", allowlist)
    with caplog.at_level(logging.INFO, logger=main.logger.name):
        main._announce_signup_mode()
    return [r for r in caplog.records if "Signup mode" in r.getMessage()]


def test_invite_with_an_empty_list_warns_that_nobody_can_sign_in(monkeypatch, caplog):
    (record,) = _announced(monkeypatch, caplog, "invite", "")

    assert record.levelno == logging.WARNING
    assert "nobody can sign in" in record.getMessage()


def test_invite_with_a_list_is_said_without_naming_anyone(monkeypatch, caplog):
    (record,) = _announced(monkeypatch, caplog, "invite", ADDRESSES)

    assert record.levelno == logging.INFO
    assert "nobody" not in record.getMessage()
    assert "example.com" not in caplog.text


def test_open_mode_keeps_its_own_warning(monkeypatch, caplog):
    (record,) = _announced(monkeypatch, caplog, "open", "")

    assert record.levelno == logging.WARNING
    assert "OPEN" in record.getMessage()


def test_the_startup_announcement_says_it(monkeypatch, caplog):
    """`_announce_configuration` is what the lifespan calls."""
    monkeypatch.setenv("SIGNUP_MODE", "invite")
    monkeypatch.setenv("INVITE_ALLOWLIST", "")
    with caplog.at_level(logging.INFO, logger=main.logger.name):
        main._announce_configuration()

    assert "nobody can sign in" in caplog.text
    assert "Auth mode" in caplog.text
