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

from app.config import validate_skip_auth  # noqa: E402

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

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Validate NextAuth JWT token and extract user ID
    """
    # Skip authentication in development if SKIP_AUTH is true
    if SKIP_AUTH:
        # Development mode user mapping:
        # - Tokens starting with "dev-" return the token itself as user ID
        # - All other tokens return "dev-user-default" as user ID
        # This ensures consistent data access in development
        token = credentials.credentials
        if token.startswith("dev-"):
            return token
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

        return user_id

    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as e:
        logger.error(f"JWT validation error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except HTTPException:
        # Deliberate auth failures (e.g. missing user id claim -> 401) must not
        # be converted into 500s by the generic handler below
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")

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