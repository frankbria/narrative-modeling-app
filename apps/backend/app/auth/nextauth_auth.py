# backend/app/auth/nextauth_auth.py

import logging
import os

import jwt
from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Set up logging
logger = logging.getLogger(__name__)

# Load environment variables (real environment takes precedence over .env,
# matching app.config — a stray .env must not override production settings)
load_dotenv()

from app.config import (  # noqa: E402
    current_signup_mode,
    is_admin_email,
    parse_invite_allowlist,
    signup_admits,
    validate_skip_auth,
)

# Get NextAuth configuration
NEXTAUTH_SECRET = os.getenv("NEXTAUTH_SECRET")
NEXTAUTH_URL = os.getenv("NEXTAUTH_URL", "http://localhost:3000")
SKIP_AUTH = os.getenv("SKIP_AUTH", "false").lower() == "true"

# Hard gate (issue #149): refuse to start with auth bypassed outside an
# explicit development/test environment. Raises RuntimeError at import time,
# which aborts app startup. Logs a warning when the bypass is permitted.
validate_skip_auth(skip_auth=SKIP_AUTH)

if not NEXTAUTH_SECRET and not SKIP_AUTH:
    logger.error("NEXTAUTH_SECRET environment variable is not set. Authentication will fail.")

security = HTTPBearer()
_optional_bearer = HTTPBearer(auto_error=False)


def _verify(token: str, secret: str) -> dict:
    """Verify an API token as the frontend mints it (`lib/api-token.ts`): HS256 only,
    signed with NEXTAUTH_SECRET, carrying `sub` and an unexpired `exp`. Raises a
    ``jwt.PyJWTError`` otherwise (``ExpiredSignatureError`` for expiry); callers catch
    that base, since a key error such as ``InvalidKeyError`` is not an
    ``InvalidTokenError``. PyJWT since #844: python-jose had an unpatched critical CVE.
    """
    return jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})


def _configured_secret() -> str:
    if not NEXTAUTH_SECRET:
        logger.error("NextAuth configuration is missing.")
        raise HTTPException(
            status_code=500,
            detail="Authentication service is not properly configured.",
        )
    return NEXTAUTH_SECRET


def _verified_payload(token: str) -> dict:
    """The token's claims, or a 401 with a fixed message: library internals are
    logged server-side, never echoed (issue #269), and an unexpected failure is
    still an auth failure, not a leaky 500 that pollutes the error-rate metrics."""
    secret = _configured_secret()
    try:
        return _verify(token, secret)
    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError as e:
        logger.error(f"JWT validation error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")


def _admit_signup(payload: dict) -> None:
    """Signup gate (#261, #768): defense-in-depth mirror of the NextAuth signIn
    callback. SIGNUP_MODE decides; invite mode checks the email claim (minted by the
    frontend) against INVITE_ALLOWLIST. Reads the env per request so a revoked
    invitee is refused within the token TTL."""
    allowlist = parse_invite_allowlist(os.getenv("INVITE_ALLOWLIST"))
    if not signup_admits(payload.get("email"), current_signup_mode(), allowlist):
        logger.warning("Invite gate: rejected non-allowlisted user")
        raise HTTPException(status_code=403, detail="Access is limited to invited beta users.")


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Validate the API token the frontend minted and return its `sub`."""
    if SKIP_AUTH:
        # Every request maps to a single fixed dev identity. The old "dev-"
        # prefix branch returned the bearer string verbatim as the user id,
        # which let any caller impersonate an arbitrary dev identity by forging
        # the token (issue #272). SKIP_AUTH is confined to localhost dev/test
        # (issue #149); real multi-user testing uses a signed JWT (the frontend
        # mints one via mintApiToken) or a FastAPI dependency override.
        return "dev-user-default"
    payload = _verified_payload(credentials.credentials)
    _admit_signup(payload)
    return payload["sub"]

# For backward compatibility during migration
async def get_current_user_id_optional(
    authorization: str | None = Header(None)
) -> str | None:
    """
    Optional authentication - returns user ID if authenticated, None otherwise
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    try:
        token = authorization.split(" ")[1]
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        return await get_current_user_id(credentials)
    except (IndexError, ValueError, HTTPException):
        # Catch HTTPException from get_current_user_id() - for optional auth,
        # invalid/expired tokens should return None, not raise to the client
        return None


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
) -> None:
    """Admit only a verified token whose email is on ``ADMIN_EMAILS`` (#768 AC6).

    Everyone else — anonymous, a forged or expired token, a signed-in tenant —
    gets the same 404 as a path that does not exist, like the frontend's
    ``/admin`` rewrite (#477): the endpoint's existence is not advertised.
    """
    payload = _admin_payload(credentials)
    if payload is None or not is_admin_email(payload.get("email")):
        raise HTTPException(status_code=404, detail="Not Found")


def _admin_payload(credentials: HTTPAuthorizationCredentials | None) -> dict | None:
    """The verified claims, or None for anything that is not a valid token."""
    if credentials is None or SKIP_AUTH or not NEXTAUTH_SECRET:
        return None
    try:
        return _verify(credentials.credentials, NEXTAUTH_SECRET)
    except jwt.PyJWTError:
        return None
