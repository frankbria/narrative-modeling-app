"""Transactional email through Resend's HTTP API (#494, ADR-004).

Sending is optional. With `RESEND_API_KEY` or `EMAIL_FROM` unset the app runs as it did
before and `send` does nothing, which is what keeps a secret-less build and the test suite
from needing a provider. Both are read on every call (blank means unset, as compose passes
`${RESEND_API_KEY:-}`), so importing this module touches no configuration.

`send` never raises: a notification is never worth failing the work it reports on.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

RESEND_EMAILS_URL = "https://api.resend.com/emails"
_SETTINGS = ("RESEND_API_KEY", "EMAIL_FROM")


def _setting(name: str) -> str:
    return os.getenv(name, "").strip()


def configuration_warning() -> str | None:
    """Why no mail will be sent, or None when it will."""
    missing = [name for name in _SETTINGS if not _setting(name)]
    if not missing:
        return None
    return f"not sending mail ({' and '.join(missing)} unset)"


def is_configured() -> bool:
    return configuration_warning() is None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=10.0)


async def send(to: str, subject: str, text: str, *, idempotency_key: str) -> bool:
    """Send one plain-text message; True when Resend accepted it.

    Resend delivers one message per `idempotency_key` (a repeat is answered without
    sending, or refused if its content differs), so two paths that both see a job end
    (its own task and the stale-job reaper) mail once.
    """
    if not is_configured():
        return False
    try:
        async with _client() as client:
            response = await client.post(
                RESEND_EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {_setting('RESEND_API_KEY')}",
                    "Idempotency-Key": idempotency_key,
                },
                json={
                    "from": _setting("EMAIL_FROM"),
                    "to": [to],
                    "subject": subject,
                    "text": text,
                },
            )
            response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - a failed notification must never raise
        # The class only: the message of an HTTP error quotes the response, which can
        # quote the recipient, and WARNING lines are kept.
        logger.warning("Email not sent: %s", type(exc).__name__)
        return False
    return True
