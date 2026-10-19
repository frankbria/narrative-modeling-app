"""Operator-only readouts (#769 AC2). Every route is behind the ADMIN_EMAILS allowlist."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth.nextauth_auth import require_admin
from app.billing.refunds import is_in_refund_window, refund_window_ends_at
from app.models.subscription import Subscription
from app.services import product_events
from app.utils.datetime import as_utc

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/funnel")
async def funnel(days: int = Query(30, ge=1, le=395)):
    """Signups, 7-day activation, 402s by metric and checkouts over the last `days`."""
    return await product_events.funnel(days)


class RefundWindow(BaseModel):
    refund_eligible: bool
    refund_window_ends_at: str | None
    first_paid_at: str | None


@router.get("/billing/{user_id}/refund", response_model=RefundWindow)
async def refund_window(user_id: str):
    """Whether a tenant is inside the published refund window (#746). Read-only; the
    same `app/billing/refunds.py` rule `GET /billing/status` shows the tenant. A tenant
    with no subscription row (free or unknown) is a 404 so a mistyped id is not read as
    "never paid"."""
    sub = await Subscription.find_one(Subscription.user_id == user_id)
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no subscription for that user")
    ends = refund_window_ends_at(sub.first_paid_at)
    return RefundWindow(
        refund_eligible=is_in_refund_window(sub.first_paid_at),
        refund_window_ends_at=ends.isoformat() if ends else None,
        first_paid_at=as_utc(sub.first_paid_at).isoformat() if sub.first_paid_at else None,
    )
