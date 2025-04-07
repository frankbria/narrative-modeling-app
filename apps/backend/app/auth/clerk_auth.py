# backend/app/auth/clerk_auth.py

import os
import httpx
import json
import base64
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError
from jose.utils import base64url_decode

CLERK_ISSUER = os.getenv("CLERK_ISSUER")  # e.g. https://clerk.yourdomain.com
CLERK_JWKS_URL = f"{CLERK_ISSUER}/.well-known/jwks.json"

security = HTTPBearer()


def get_unverified_header(token: str):
    headers_b64 = token.split(".")[0]
    headers_json = base64.urlsafe_b64decode(headers_b64 + "==")
    return json.loads(headers_json)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials

    async with httpx.AsyncClient() as client:
        jwks = (await client.get(CLERK_JWKS_URL)).json()

    # Use jose to verify and decode the JWT
    # from jose import jwt
    # from jose.exceptions import JWTError, ExpiredSignatureError
    # from jwt.utils import get_unverified_header

    try:
        unverified_header = get_unverified_header(token)
        kid = unverified_header["kid"]
        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)

        if not key:
            raise HTTPException(status_code=401, detail="Invalid signing key")

        public_key = jwt.construct_rsa_public_key(key)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[key["alg"]],
            audience=os.getenv(
                "CLERK_FRONTEND_API"
            ),  # Check this matches your Clerk config
            issuer=CLERK_ISSUER,
        )

        return payload["sub"]  # Clerk user ID
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
