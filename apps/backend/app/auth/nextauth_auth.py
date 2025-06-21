# backend/app/auth/nextauth_auth.py

import os
import httpx
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging
from dotenv import load_dotenv

# Set up logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

# Get NextAuth configuration
NEXTAUTH_SECRET = os.getenv("NEXTAUTH_SECRET")
NEXTAUTH_URL = os.getenv("NEXTAUTH_URL", "http://localhost:3000")
SKIP_AUTH = os.getenv("SKIP_AUTH", "false").lower() == "true"

if not NEXTAUTH_SECRET and not SKIP_AUTH:
    logger.error("NEXTAUTH_SECRET environment variable is not set. Authentication will fail.")
    
if SKIP_AUTH:
    logger.warning("⚠️  SKIP_AUTH is enabled! Authentication is bypassed in development mode.")

security = HTTPBearer()

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Validate NextAuth JWT token and extract user ID
    """
    # Skip authentication in development if SKIP_AUTH is true
    if SKIP_AUTH:
        # Extract a dev user ID from the token or use a default
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
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")

# For backward compatibility during migration
def get_current_user_id_optional(
    authorization: Optional[str] = Header(None)
) -> Optional[str]:
    """
    Optional authentication - returns user ID if authenticated, None otherwise
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    try:
        token = authorization.split(" ")[1]
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        return get_current_user_id(credentials)
    except:
        return None