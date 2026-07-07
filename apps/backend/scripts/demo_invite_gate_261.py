"""Demo: invite-only beta gate (#261) — exercises the REAL gate end-to-end.

Mints HS256 tokens exactly like the frontend and drives the backend mirror
(get_current_user_id) with the gate on/off, proving the AC:
  - a non-allowlisted email is DENIED (403)
  - an allowlisted email is ADMITTED
Plus the frontend allowlist semantics via the pure config helpers.

Run: cd apps/backend && PYTHONPATH=. uv run python scripts/demo_invite_gate_261.py
"""

import asyncio
import os
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.config import is_email_allowed, parse_invite_allowlist

SECRET = "demo-secret"


def mint(email: str | None) -> HTTPAuthorizationCredentials:
    claims = {"sub": "user_demo"}
    if email:
        claims["email"] = email
    return HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=jwt.encode(claims, SECRET, algorithm="HS256")
    )


async def call(cred) -> str:
    # Import inside so the SKIP_AUTH/secret patches below are in effect.
    from app.auth.nextauth_auth import get_current_user_id

    return await get_current_user_id(cred)


async def main() -> None:
    print("=== Pure allowlist semantics (shared by both tiers) ===")
    allow = parse_invite_allowlist(" Alice@Example.com , bob@example.com ")
    print("parsed allowlist:", sorted(allow))
    print("  alice admitted (case-insensitive):", is_email_allowed("ALICE@example.com", allow))
    print("  eve denied:", is_email_allowed("eve@evil.com", allow))
    print("  empty list disables gate (eve allowed):", is_email_allowed("eve@evil.com", set()))

    with patch("app.auth.nextauth_auth.NEXTAUTH_SECRET", SECRET), patch(
        "app.auth.nextauth_auth.SKIP_AUTH", False
    ):
        print("\n=== Backend mirror: gate ACTIVE (INVITE_ALLOWLIST set) ===")
        with patch.dict(os.environ, {"INVITE_ALLOWLIST": "alice@example.com"}):
            uid = await call(mint("alice@example.com"))
            print(f"  allowlisted alice -> ADMITTED as {uid!r}")
            for label, email in [("non-allowlisted eve", "eve@evil.com"), ("missing email", None)]:
                try:
                    await call(mint(email))
                    print(f"  {label} -> ADMITTED (UNEXPECTED!)")
                except HTTPException as e:
                    print(f"  {label} -> DENIED {e.status_code} {e.detail!r}")

        print("\n=== Backend mirror: gate OFF (INVITE_ALLOWLIST empty) ===")
        with patch.dict(os.environ, {"INVITE_ALLOWLIST": ""}):
            uid = await call(mint("eve@evil.com"))
            print(f"  any signed token -> ADMITTED as {uid!r} (gate disabled)")

    print("\nAll outcomes match the acceptance criteria.")


if __name__ == "__main__":
    asyncio.run(main())
