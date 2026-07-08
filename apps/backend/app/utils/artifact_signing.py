"""HMAC signing/verification for serialized artifacts (issue #266).

``joblib.load``/``pickle.loads`` execute arbitrary code on deserialization, so
they are only safe on bytes we know we wrote. We authenticate artifacts with an
HMAC-SHA256 over a server-only secret: sign the bytes when we persist them, and
verify before we ever deserialize. A tamperer with write access to the store
(S3/Redis) can replace the bytes but cannot forge a valid signature without the
secret.

The signature is stored in a *trusted* location — for model artifacts, the
MongoDB ``MLModel`` document (the artifact itself lives in less-trusted S3); for
Redis, inline with the blob (the HMAC is what makes the inline copy trustworthy).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)

# Only used when neither ARTIFACT_SIGNING_KEY nor NEXTAUTH_SECRET is set — i.e.
# local dev/test. Any real deploy sets NEXTAUTH_SECRET (auth fails without it),
# so this constant never signs a production artifact.
_DEV_FALLBACK_KEY = "insecure-dev-artifact-signing-key"
_warned_dev_key = False


def get_signing_key() -> bytes:
    """Resolve the HMAC secret: ARTIFACT_SIGNING_KEY → NEXTAUTH_SECRET → dev fallback.

    Resolved per call so tests/rotations that mutate the env take effect without a
    process restart.
    """
    key = os.getenv("ARTIFACT_SIGNING_KEY") or os.getenv("NEXTAUTH_SECRET")
    if not key:
        global _warned_dev_key
        if not _warned_dev_key:
            logger.warning(
                "No ARTIFACT_SIGNING_KEY/NEXTAUTH_SECRET set; using insecure dev "
                "signing key. Set NEXTAUTH_SECRET (or ARTIFACT_SIGNING_KEY) in any "
                "non-development environment."
            )
            _warned_dev_key = True
        key = _DEV_FALLBACK_KEY
    return key.encode("utf-8")


def sign_bytes(data: bytes) -> str:
    """Return the hex HMAC-SHA256 of ``data`` under the signing key."""
    return hmac.new(get_signing_key(), data, hashlib.sha256).hexdigest()


def verify_bytes(data: bytes, signature: str | None) -> bool:
    """Constant-time check that ``signature`` is a valid HMAC for ``data``.

    Returns ``False`` for a missing/empty signature so callers can treat
    "unsigned" and "wrong signature" identically at trust boundaries.
    """
    if not signature:
        return False
    return hmac.compare_digest(sign_bytes(data), signature)
