#!/usr/bin/env python3
"""#455 AC3 — find (and optionally correct) APIKey rows with an out-of-range rate_limit.

A stored ``rate_limit`` of 0 or less removes rate limiting entirely on the paid
serving surface, because the limiter store reads ``limit <= 0`` as "no
enforcement". Creation now rejects <1 and clamps to the tenant's plan ceiling,
but rows written before that fix are still out there.

Read-only by default. Reports counts only — no key ids, no hashes, no user ids —
so its output is safe to paste into a public issue.

Usage (from apps/backend, against whichever cluster you want to check):

    MONGODB_URI=... MONGODB_DB=... uv run python scripts/fix_api_key_rate_limits.py
    MONGODB_URI=... MONGODB_DB=... uv run python scripts/fix_api_key_rate_limits.py --apply

``--apply`` raises every non-positive value to the FREE ceiling and lowers every
value above the ENTERPRISE ceiling down to it. The per-tenant ceiling is not used
here on purpose: resolving each key's owner's subscription would turn a one-shot
audit into a per-row join, and the goal is to close the hole, not to re-tier
anyone. A tenant on a higher plan can recreate a key to get their real ceiling.

Exit status is 1 when uncorrected out-of-range rows remain, so it can gate a deploy.
"""

import asyncio
import os
import sys


async def main() -> int:
    from motor.motor_asyncio import AsyncIOMotorClient

    from app.billing.plans import api_key_rate_limit_ceiling
    from app.models.subscription import PlanTier

    apply = "--apply" in sys.argv[1:]

    uri, db_name = os.getenv("MONGODB_URI"), os.getenv("MONGODB_DB")
    if not uri or not db_name:
        print("Set MONGODB_URI and MONGODB_DB.", file=sys.stderr)
        return 2

    floor = api_key_rate_limit_ceiling(PlanTier.FREE)
    ceiling = max(floor, api_key_rate_limit_ceiling(PlanTier.ENTERPRISE))

    client = AsyncIOMotorClient(uri)
    try:
        return await _audit(client[db_name]["api_keys"], floor, ceiling, apply)
    finally:
        client.close()


async def _audit(collection, floor: int, ceiling: int, apply: bool) -> int:
    total = await collection.count_documents({})
    non_positive = await collection.count_documents({"rate_limit": {"$lte": 0}})
    # `$type: "int"` rather than `$exists`: a hand-written `null` exists but is
    # just as unusable, and `$lte`/`$gt` match neither.
    missing = await collection.count_documents(
        {"rate_limit": {"$not": {"$type": "number"}}}
    )
    above = await collection.count_documents({"rate_limit": {"$gt": ceiling}})

    print(f"api_keys scanned:              {total}")
    print(f"rate_limit <= 0 (UNLIMITED):   {non_positive}")
    print(f"rate_limit missing/non-numeric: {missing}")
    print(f"rate_limit > {ceiling} (ceiling):   {above}")

    if not apply:
        if non_positive or missing or above:
            print("\nOut-of-range rows found. Re-run with --apply to correct them.")
            return 1
        print("\nNo out-of-range rate_limit values.")
        return 0

    raised = await collection.update_many(
        {
            "$or": [
                {"rate_limit": {"$lte": 0}},
                {"rate_limit": {"$not": {"$type": "number"}}},
            ]
        },
        {"$set": {"rate_limit": floor}},
    )
    lowered = await collection.update_many(
        {"rate_limit": {"$gt": ceiling}},
        {"$set": {"rate_limit": ceiling}},
    )
    print(f"\nraised to {floor}:  {raised.modified_count}")
    print(f"lowered to {ceiling}: {lowered.modified_count}")

    remaining = await collection.count_documents(
        {
            "$or": [
                {"rate_limit": {"$lte": 0}},
                {"rate_limit": {"$not": {"$type": "number"}}},
                {"rate_limit": {"$gt": ceiling}},
            ]
        }
    )
    print(f"still out of range:  {remaining}")
    return 1 if remaining else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
