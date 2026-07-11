"""Production observability wiring (issue #273): structured logging + Sentry.

Deliberately small — a LOG_LEVEL/LOG_FORMAT toggle and a no-op-without-DSN Sentry
init. Metrics live in ``app.middleware.metrics`` (Prometheus); request-id stamping
in ``app.middleware.error_handlers`` (this module only *reads* the request id for
log correlation).
"""

import json
import logging
import os
import sys

from app.middleware.error_handlers import request_id_ctx

_TEXT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] %(message)s"

# Libraries whose INFO/DEBUG chatter we never want, regardless of root level.
_NOISY_LIBRARIES = ("boto3", "botocore", "s3transfer", "urllib3")


class RequestIdFilter(logging.Filter):
    """Attach the current request id (or ``-``) to every record so both the text
    and JSON formatters can include it, correlating a log line to a request."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """Minimal structured formatter — one JSON object per line, no extra dep."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _resolve_level(raw: str | None) -> int:
    """Map a LOG_LEVEL string to a logging level int, defaulting to INFO."""
    level = logging.getLevelNamesMapping().get((raw or "INFO").strip().upper())
    return level if isinstance(level, int) else logging.INFO


def configure_logging(level: str | None = None, log_format: str | None = None) -> None:
    """Configure root logging from ``LOG_LEVEL`` / ``LOG_FORMAT`` (args override env).

    - ``LOG_LEVEL``: DEBUG/INFO/WARNING/... (default INFO) — honored, unlike the
      old hardcoded ``basicConfig`` which ignored it (issue #273).
    - ``LOG_FORMAT``: ``json`` for structured logs, else human-readable text.

    Idempotent: replaces the root handler so re-calling (or a prior ``basicConfig``)
    can't stack duplicate handlers.
    """
    resolved_level = _resolve_level(
        level if level is not None else os.getenv("LOG_LEVEL")
    )
    fmt = (
        log_format if log_format is not None else os.getenv("LOG_FORMAT", "text")
    ).strip().lower()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        JsonFormatter() if fmt == "json" else logging.Formatter(_TEXT_FORMAT)
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(resolved_level)

    for noisy in _NOISY_LIBRARIES:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def init_sentry() -> bool:
    """Initialize Sentry error tracking + APM when ``SENTRY_DSN`` is set.

    No-op (returns ``False``) when the DSN is unset — so dev/CI/test run clean —
    or when sentry-sdk isn't installed (slim images). Safe to call once at startup.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logging.getLogger(__name__).warning(
            "SENTRY_DSN is set but sentry-sdk is not installed; skipping Sentry init"
        )
        return False

    try:
        traces = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0"))
    except ValueError:
        traces = 0.0

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("ENVIRONMENT", "development"),
        release=os.getenv("APP_VERSION") or None,
        traces_sample_rate=max(0.0, min(1.0, traces)),
        # This app handles user PII (#259); don't let Sentry attach request bodies.
        send_default_pii=False,
    )
    logging.getLogger(__name__).info("Sentry initialized (environment=%s)", os.getenv("ENVIRONMENT", "development"))
    return True
