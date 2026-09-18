"""Operator-only readouts (#769 AC2). Every route is behind the ADMIN_EMAILS allowlist."""

from fastapi import APIRouter, Depends, Query

from app.auth.nextauth_auth import require_admin
from app.services import product_events

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/funnel")
async def funnel(days: int = Query(30, ge=1, le=395)):
    """Signups, 7-day activation, 402s by metric and checkouts over the last `days`."""
    return await product_events.funnel(days)
