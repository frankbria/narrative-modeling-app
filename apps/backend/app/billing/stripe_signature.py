"""Stripe webhook signature verification (#367).

Implemented against Stripe's documented scheme with stdlib `hmac` rather than the
Stripe SDK. The scheme is small and fully specified — HMAC-SHA256 over
`{timestamp}.{raw body}`, compared in constant time, with a replay tolerance — and
keeping it here means:

* the webhook has no SDK dependency in its security path, and
* the tests exercise the real verification rather than a mocked `construct_event`,
  which is the only version of this test worth having.

`stripe.Webhook.construct_event` does exactly this. If the SDK arrives for Checkout
(#365), this can be swapped for it without changing any caller.

Header format:

    Stripe-Signature: t=1614556800,v1=<hex hmac>,v1=<hex hmac>,v0=<ignored>
"""

import hashlib
import hmac
import time

#: Stripe's own default. Rejecting older events bounds how long a captured request
#: stays replayable.
DEFAULT_TOLERANCE_SECONDS = 300


class SignatureVerificationError(Exception):
    """The request did not carry a valid, current signature for this secret."""


def _parse_header(header: str) -> tuple[int | None, list[str]]:
    """Pull the timestamp and every v1 signature out of a Stripe-Signature header.

    Stripe sends multiple `v1` entries during a secret rotation, so all of them are
    returned and any one matching is enough. `v0` entries are a different scheme and
    are ignored rather than compared.
    """
    timestamp: int | None = None
    signatures: list[str] = []

    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                return None, []
        elif key == "v1":
            signatures.append(value)

    return timestamp, signatures


def verify_signature(
    payload: bytes,
    header: str | None,
    secret: str,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: float | None = None,
) -> None:
    """Raise `SignatureVerificationError` unless `payload` is signed by `secret`.

    Takes the RAW body, not parsed JSON: re-serialising changes whitespace and key
    order, and the signature is over the exact bytes Stripe sent.
    """
    if not secret:
        # Refusing to verify is not the same as verifying. Without a secret there is
        # nothing to check, and treating that as "valid" would leave the endpoint
        # open to anyone who found the URL.
        raise SignatureVerificationError("no webhook secret configured")

    if not header:
        raise SignatureVerificationError("missing Stripe-Signature header")

    timestamp, signatures = _parse_header(header)
    if timestamp is None or not signatures:
        raise SignatureVerificationError("malformed Stripe-Signature header")

    current = time.time() if now is None else now
    if abs(current - timestamp) > tolerance_seconds:
        # Bounds replay: a captured request stops being usable once it ages out.
        raise SignatureVerificationError("timestamp outside the tolerance window")

    expected = hmac.new(
        secret.encode("utf-8"),
        b"%d.%s" % (timestamp, payload),
        hashlib.sha256,
    ).hexdigest()

    # compare_digest, not `==`: a short-circuiting comparison leaks how much of a
    # forged signature was correct, one byte at a time.
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise SignatureVerificationError("signature mismatch")
