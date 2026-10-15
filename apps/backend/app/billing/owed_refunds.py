"""A refund that a crash between two writes cannot lose (#1032).

Settling a job (marking it FAILED, or its remainder refunded) and returning its
units are writes to two collections, and no ordering of two writes survives a crash
between them: refund first and a retry pays twice, settle first and the refund is
lost. So the write that settles a job also records, on the job's row, the refund it
owes (`owed(...)` is the value to `$push` onto `refunds_owed`: a list, so a second
settle of a retried job never replaces a refund still unpaid). `settle` then pays it
under its refund id, which `metering.refund` applies at most once, and removes it. A
worker that dies in between leaves it on the row, and the reaper's `settle_pending`
pays it on its next pass.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorCollection

from app.billing import metering


def owed(user_id: str, metric: str, amount: int, period_key: str) -> dict[str, Any]:
    """The `refunds_owed` entry for a job whose settling write owes this refund. Its id
    is its own: the settling write is exclusive, so only a re-pay of this record can
    meet it again."""
    return {"user_id": user_id, "metric": metric, "amount": amount, "period_key": period_key, "id": uuid4().hex}


async def settle(collection: AsyncIOMotorCollection, row: dict[str, Any], refund: dict[str, Any]) -> None:
    """Pay `refund`, then remove it from the row `row` matches."""
    paid = refund["amount"] <= 0 or await metering.refund(
        refund["user_id"], refund["metric"], refund["amount"], refund["period_key"], refund_id=refund["id"]
    )
    if paid:
        await collection.update_one(row, {"$pull": {"refunds_owed": {"id": refund["id"]}}})


async def settle_pending(collection: AsyncIOMotorCollection) -> int:
    """Pay every refund a crash left owed in `collection`; how many were paid."""
    count = 0
    async for row in collection.find({"refunds_owed.0": {"$exists": True}}, {"refunds_owed": 1}):
        for refund in row["refunds_owed"]:
            await settle(collection, {"_id": row["_id"]}, refund)
            count += 1
    return count
