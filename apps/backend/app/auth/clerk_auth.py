# backend/app/auth/clerk_auth.py

import os
import httpx
import json
import base64
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, jwk
from jose.exceptions import JWTError, ExpiredSignatureError
import logging
from dotenv import load_dotenv
from inspect import signature, Signature

# Set up logging
logger = logging.getLogger(__name__)

# Try to load environment variables if not already loaded
load_dotenv(override=True)

# Get Clerk issuer from environment variable
CLERK_ISSUER = os.getenv("CLERK_ISSUER")
if not CLERK_ISSUER:
    logger.error(
        "CLERK_ISSUER environment variable is not set. Authentication will fail."
    )
else:
    # Remove any trailing slashes
    CLERK_ISSUER = CLERK_ISSUER.rstrip("/")
    logger.info(f"Using CLERK_ISSUER: {CLERK_ISSUER}")

    # Ensure the issuer URL has a protocol
    if not CLERK_ISSUER.startswith("http://") and not CLERK_ISSUER.startswith(
        "https://"
    ):
        CLERK_ISSUER = f"https://{CLERK_ISSUER}"
        logger.info(f"Added protocol to CLERK_ISSUER: {CLERK_ISSUER}")

# Construct the JWKS URL
CLERK_JWKS_URL = f"{CLERK_ISSUER}/.well-known/jwks.json" if CLERK_ISSUER else None
if CLERK_JWKS_URL:
    logger.info(f"Using CLERK_JWKS_URL: {CLERK_JWKS_URL}")
else:
    logger.error("CLERK_JWKS_URL is not set because CLERK_ISSUER is missing")

security = HTTPBearer()


def clean_signature(fn) -> Signature:
    # Get the original signature.
    sig = signature(fn)
    # Filter out any parameters named 'args' or 'kwargs'
    new_params = [
        param
        for param in sig.parameters.values()
        if param.name not in ("args", "kwargs")
    ]
    return sig.replace(parameters=new_params)


# Override the __signature__ attribute of security’s __call__ method.
security.__signature__ = clean_signature(security.__call__)


def get_unverified_header(token: str):
    headers_b64 = token.split(".")[0]
    headers_json = base64.urlsafe_b64decode(headers_b64 + "==")
    return json.loads(headers_json)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    # Check if Clerk configuration is available
    if not CLERK_ISSUER or not CLERK_JWKS_URL:
        logger.error(
            "Clerk configuration is missing. Please set CLERK_ISSUER environment variable."
        )
        raise HTTPException(
            status_code=500,
            detail="Authentication service is not properly configured. Please contact the administrator.",
        )

    token = credentials.credentials

    try:
        # Create client with redirect following enabled
        async with httpx.AsyncClient(follow_redirects=True) as client:
            logger.info(f"Fetching JWKS from: {CLERK_JWKS_URL}")
            response = await client.get(CLERK_JWKS_URL)

            if not response.is_success:
                logger.error(
                    f"Failed to fetch JWKS: {response.status_code} {response.text}"
                )
                if response.status_code == 301:
                    logger.error(
                        "Received 301 redirect. Please check if CLERK_ISSUER is correct."
                    )
                elif response.status_code == 404:
                    logger.error(
                        "Received 404 Not Found. The JWKS endpoint does not exist. Please check CLERK_ISSUER."
                    )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to fetch JWKS: {response.status_code}",
                )

            try:
                jwks = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JWKS response: {str(e)}")
                logger.error(
                    f"Response content: {response.text[:500]}..."
                )  # Log only the first 500 chars
                raise HTTPException(
                    status_code=500,
                    detail="Invalid JWKS response format. Please check CLERK_ISSUER configuration.",
                )

        # Use jose to verify and decode the JWT
        unverified_header = get_unverified_header(token)
        kid = unverified_header["kid"]
        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)

        if not key:
            logger.error(f"Invalid signing key: {kid}")
            raise HTTPException(status_code=401, detail="Invalid signing key")

        # Use jose's built-in jwk functionality
        public_key = jwk.construct(key)

        # Decode the JWT
        payload = jwt.decode(
            token,
            public_key.to_pem(),
            algorithms=[key["alg"]],
            audience=CLERK_ISSUER,
            issuer=CLERK_ISSUER,
        )

        # Extract user ID from the payload
        user_id = payload.get("sub")
        if not user_id:
            logger.error("No user ID found in token")
            raise HTTPException(status_code=401, detail="No user ID found in token")

        return user_id

    except ExpiredSignatureError:
        logger.error("Token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as e:
        logger.error(f"JWT validation error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")
