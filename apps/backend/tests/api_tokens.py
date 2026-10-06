"""The API token exactly as the frontend mints it (`apps/frontend/lib/api-token.ts`).

Built by hand with `hmac`, not with the JWT library the backend verifies with, so
a library quirk cannot make both sides agree on a token the frontend never sends
(#844: the backend moved from python-jose to PyJWT).
"""
import base64
import hashlib
import hmac
import json
import time

TEST_SECRET = "test-secret"
TTL_SECONDS = 60 * 60  # API_TOKEN_TTL_SECONDS in api-token.ts


def _b64(data: dict | bytes) -> str:
    raw = data if isinstance(data, bytes) else json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def mint_api_token(
    sub: str,
    email: str | None = None,
    *,
    secret: str = TEST_SECRET,
    ttl: int = TTL_SECONDS,
    header: dict | None = None,
) -> str:
    """`{sub, iat, exp[, email]}`, HS256-signed. `ttl` < 0 mints an expired token;
    `header` swaps the JOSE header to forge a token the frontend would never mint."""
    now = int(time.time())
    claims: dict = {"sub": sub, "iat": now, "exp": now + ttl}
    if email:
        claims["email"] = email
    signing_input = f"{_b64(header or {'alg': 'HS256', 'typ': 'JWT'})}.{_b64(claims)}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"
