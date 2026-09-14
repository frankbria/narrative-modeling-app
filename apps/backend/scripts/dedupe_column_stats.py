"""Pre-deploy dedupe for the unique ``(dataset_id, column_name)`` index on ``column_stats`` (#543).

Before #543 the cache query never matched the DBRef ``dataset_id``, so every GET
recomputed and RE-INSERTED a full set of stats — the collection grew without bound with
duplicate ``(dataset_id, column_name)`` rows. Beanie builds the ``dataset_column_unique``
index at ``init_beanie``; it cannot build (and the app refuses to start) while duplicates
exist, so run this first.

Keeps the newest row per ``(dataset_id, column_name)`` (max ``_id``) and deletes the rest.
Dry-run by default; pass ``--apply`` to delete. ``--drop-legacy-index`` drops the pre-#543
non-unique ``dataset_id_1_column_name_1`` the unique index supersedes.

Usage (credentials: see the operator's local runbook):
    MONGODB_URI=... MONGODB_DB=... uv run python scripts/dedupe_column_stats.py [--apply] [--drop-legacy-index] [--json]

Exit code 1 when duplicates remain (a dry run that found some, or a failed apply); 0 otherwise.
Output carries counts only — no user identifiers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

LEGACY_INDEX = "dataset_id_1_column_name_1"


async def _duplicate_groups(collection: AsyncIOMotorCollection) -> list[dict[str, Any]]:
    """Groups of >1 row sharing a (dataset_id, column_name), with the ids to keep/drop."""
    pipeline: list[dict[str, Any]] = [
        {"$group": {
            "_id": {"dataset_id": "$dataset_id", "column_name": "$column_name"},
            "ids": {"$push": "$_id"},
            "count": {"$sum": 1},
        }},
        {"$match": {"count": {"$gt": 1}}},
    ]
    return [row async for row in collection.aggregate(pipeline)]


async def dedupe(collection: AsyncIOMotorCollection, *, apply: bool) -> dict[str, int]:
    groups = await _duplicate_groups(collection)
    duplicate_rows = sum(g["count"] - 1 for g in groups)
    deleted = 0
    if apply:
        for g in groups:
            ids = sorted(g["ids"])  # ObjectIds sort by creation time; keep the newest
            to_delete = ids[:-1]
            res = await collection.delete_many({"_id": {"$in": to_delete}})
            deleted += res.deleted_count
    return {
        "duplicate_groups": len(groups),
        "excess_rows": duplicate_rows,
        "deleted": deleted,
    }


async def drop_legacy_index(collection: AsyncIOMotorCollection) -> bool:
    if LEGACY_INDEX not in await collection.index_information():
        return False
    await collection.drop_index(LEGACY_INDEX)
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete duplicate rows (default: dry run)")
    parser.add_argument("--drop-legacy-index", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    uri, db_name = os.getenv("MONGODB_URI"), os.getenv("MONGODB_DB")
    if not uri or not db_name:
        print("MONGODB_URI and MONGODB_DB must be set", file=sys.stderr)
        return 2

    client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
    collection = client[db_name]["column_stats"]
    try:
        stats = await dedupe(collection, apply=args.apply)
        dropped = await drop_legacy_index(collection) if args.drop_legacy_index else False
    finally:
        client.close()

    result = {**stats, "applied": args.apply, "legacy_index_dropped": dropped}
    if args.json:
        print(json.dumps(result))
    else:
        print(
            f"duplicate groups: {result['duplicate_groups']}, excess rows: {result['excess_rows']}, "
            f"deleted: {result['deleted']}, applied: {result['applied']}, "
            f"legacy index dropped: {result['legacy_index_dropped']}"
        )
    # Non-zero only when duplicates remain (dry run that found some, or an incomplete apply).
    remaining = result["excess_rows"] - result["deleted"]
    return 1 if remaining > 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
