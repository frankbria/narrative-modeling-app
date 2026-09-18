# backend/app/auth/nextauth_auth.py

import logging
import os

from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

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

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Validate NextAuth JWT token and extract user ID
    """
    # Skip authentication in development if SKIP_AUTH is true
    if SKIP_AUTH:
        # Every request maps to a single fixed dev identity. The old "dev-"
        # prefix branch returned the bearer string verbatim as the user id,
        # which let any caller impersonate an arbitrary dev identity by forging
        # the token (issue #272). SKIP_AUTH is confined to localhost dev/test
        # (issue #149); real multi-user testing uses a signed JWT (the frontend
        # mints one via mintApiToken) or a FastAPI dependency override.
        return "dev-user-default"
    
    if not NEXTAUTH_SECRET:
        logger.error("NextAuth configuration is missing.")
        raise HTTPException(
            status_code=500,
            detail="Authentication service is not properly configured.",
        )

    token = credentials.credentials

    try:
        # Decode the JWT token using the NextAuth secret
        # NextAuth uses HS256 algorithm by default
        payload = jwt.decode(
            token,
            NEXTAUTH_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False}  # NextAuth doesn't use audience by default
        )

        # Extract user ID from the payload
        # NextAuth stores user info in the token
        user_id = payload.get("sub") or payload.get("id")
        
        if not user_id:
            # If no user ID in token, might be a session token
            # In that case, we'd need to validate with the NextAuth API
            logger.error("No user ID found in token")
            raise HTTPException(status_code=401, detail="Invalid authentication token")

        # Signup gate (#261, #768): defense-in-depth mirror of the NextAuth
        # signIn callback. SIGNUP_MODE decides; invite mode checks the email
        # claim (minted by the frontend) against INVITE_ALLOWLIST. Reads the env
        # per request so a revoked invitee is refused within the token TTL.
        allowlist = parse_invite_allowlist(os.getenv("INVITE_ALLOWLIST"))
        if not signup_admits(payload.get("email"), current_signup_mode(), allowlist):
            logger.warning("Invite gate: rejected non-allowlisted user")
            raise HTTPException(
                status_code=403,
                detail="Access is limited to invited beta users.",
            )

        return user_id

    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as e:
        # Log library internals server-side; return a fixed message (issue #269
        # — never echo JWT/stack details to the client).
        logger.error(f"JWT validation error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except HTTPException:
        # Deliberate auth failures (e.g. missing user id claim -> 401) must not
        # be converted into 500s by the generic handler below
        raise
    except Exception as e:
        # An unexpected decode/verify failure is still an auth failure: return a
        # fixed 401 (not a leaky 500 — issue #269; 401 also keeps genuine auth
        # rejections out of the 5xx error-rate metrics).
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")

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
    not_found = HTTPException(status_code=404, detail="Not Found")
    if credentials is None or SKIP_AUTH or not NEXTAUTH_SECRET:
        raise not_found
    try:
        payload = jwt.decode(
            credentials.credentials,
            NEXTAUTH_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        raise not_found from None
    if not is_admin_email(payload.get("email")):
        raise not_found
