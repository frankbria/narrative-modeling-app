"""Tests for app.observability (issue #273): structured logging + Sentry init."""

import json
import logging

import pytest

from app.middleware.error_handlers import request_id_ctx
from app.observability import (
    JsonFormatter,
    RequestIdFilter,
    _resolve_level,
    _scrub_sentry_event,
    configure_logging,
    init_sentry,
)


@pytest.fixture(autouse=True)
def _restore_root_logging():
    """configure_logging mutates the root logger — snapshot and restore it so
    these tests don't leak handler/level changes into the rest of the suite."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


class TestResolveLevel:
    def test_defaults_to_info(self):
        assert _resolve_level(None) == logging.INFO
        assert _resolve_level("") == logging.INFO

    def test_honors_named_levels_case_insensitively(self):
        assert _resolve_level("DEBUG") == logging.DEBUG
        assert _resolve_level("warning") == logging.WARNING
        assert _resolve_level("  Error ") == logging.ERROR

    def test_unknown_level_falls_back_to_info(self):
        assert _resolve_level("not-a-level") == logging.INFO


class TestRequestIdFilter:
    def test_injects_current_request_id(self):
        token = request_id_ctx.set("abc123")
        try:
            record = logging.LogRecord("t", logging.INFO, __file__, 1, "hi", None, None)
            RequestIdFilter().filter(record)
            assert record.request_id == "abc123"
        finally:
            request_id_ctx.reset(token)

    def test_defaults_to_dash_outside_request(self):
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "hi", None, None)
        RequestIdFilter().filter(record)
        assert record.request_id == "-"


class TestJsonFormatter:
    def test_emits_structured_json_with_request_id(self):
        token = request_id_ctx.set("req-42")
        try:
            record = logging.LogRecord(
                "svc", logging.WARNING, __file__, 10, "something happened", None, None
            )
            RequestIdFilter().filter(record)
            payload = json.loads(JsonFormatter().format(record))
        finally:
            request_id_ctx.reset(token)

        assert payload["level"] == "WARNING"
        assert payload["logger"] == "svc"
        assert payload["message"] == "something happened"
        assert payload["request_id"] == "req-42"
        assert "timestamp" in payload

    def test_includes_stack_info_when_present(self):
        record = logging.LogRecord(
            "svc", logging.INFO, __file__, 1, "trace me", None, None,
            sinfo="Stack (most recent call last):\n  <fake frame>",
        )
        payload = json.loads(JsonFormatter().format(record))
        assert "stack_info" in payload
        assert "Stack (most recent call last)" in payload["stack_info"]

    def test_includes_exception_when_present(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = logging.LogRecord(
                "svc", logging.ERROR, __file__, 1, "failed", None, sys.exc_info()
            )
        payload = json.loads(JsonFormatter().format(record))
        assert "ValueError: boom" in payload["exception"]


class TestConfigureLogging:
    def test_explicit_level_overrides_and_is_honored(self):
        configure_logging(level="DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_reads_log_level_from_env(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        configure_logging()
        assert logging.getLogger().level == logging.WARNING

    def test_json_format_installs_json_formatter(self):
        configure_logging(level="INFO", log_format="json")
        handlers = logging.getLogger().handlers
        assert len(handlers) == 1
        assert isinstance(handlers[0].formatter, JsonFormatter)

    def test_text_format_is_default(self):
        configure_logging(level="INFO", log_format="text")
        handler = logging.getLogger().handlers[0]
        assert isinstance(handler.formatter, logging.Formatter)
        assert not isinstance(handler.formatter, JsonFormatter)

    def test_is_idempotent_no_duplicate_handlers(self):
        configure_logging(level="INFO")
        configure_logging(level="INFO")
        assert len(logging.getLogger().handlers) == 1


class TestInitSentry:
    def test_noop_without_dsn(self, monkeypatch):
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        assert init_sentry() is False

    def test_noop_when_dsn_blank(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "   ")
        assert init_sentry() is False

    def test_initializes_when_dsn_set(self, monkeypatch):
        import sentry_sdk

        captured = {}

        def fake_init(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(sentry_sdk, "init", fake_init)
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.ingest.sentry.io/1")
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")

        assert init_sentry() is True
        assert captured["dsn"].endswith("/1")
        assert captured["environment"] == "staging"
        assert captured["traces_sample_rate"] == 0.25
        assert captured["send_default_pii"] is False

    def test_noop_when_sentry_sdk_absent(self, monkeypatch):
        """Slim images built with --no-group observability have no sentry-sdk;
        init_sentry must degrade to False instead of raising (ImportError guard)."""
        import sys

        monkeypatch.setenv("SENTRY_DSN", "https://key@example.ingest.sentry.io/1")
        # Make `import sentry_sdk` raise ImportError inside init_sentry.
        monkeypatch.setitem(sys.modules, "sentry_sdk", None)
        assert init_sentry() is False

    def test_clamps_invalid_traces_sample_rate(self, monkeypatch):
        import sentry_sdk

        captured = {}
        monkeypatch.setattr(sentry_sdk, "init", lambda **kw: captured.update(kw))
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.ingest.sentry.io/1")
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "not-a-float")
        assert init_sentry() is True
        assert captured["traces_sample_rate"] == 0.0

    def test_registers_before_send_scrubber(self, monkeypatch):
        import sentry_sdk

        captured = {}
        monkeypatch.setattr(sentry_sdk, "init", lambda **kw: captured.update(kw))
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.ingest.sentry.io/1")
        assert init_sentry() is True
        assert captured["before_send"] is _scrub_sentry_event


class TestScrubSentryEvent:
    def test_strips_query_string_and_url_query(self):
        event = {
            "request": {
                "url": "https://app/api/v1/data/secret.csv?token=abc&user=42",
                "query_string": "token=abc&user=42",
            }
        }
        out = _scrub_sentry_event(event, {})
        assert "query_string" not in out["request"]
        assert out["request"]["url"] == "https://app/api/v1/data/secret.csv"

    def test_tolerates_missing_request(self):
        assert _scrub_sentry_event({}, {}) == {}
