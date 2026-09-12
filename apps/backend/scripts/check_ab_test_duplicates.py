"""Pre-deploy check for the unique ``experiment_id`` index on ``ab_tests`` (#565 AC2).

Beanie builds ``experiment_id_unique`` at ``init_beanie``. Two things make that
build fail and the app refuse to start: duplicate ids already in the collection,
and (not this index, but worth knowing) an index of the *same name* with other
options. This script reports the first and, on request, drops the pre-#565
plain ``experiment_id_1`` index the unique one supersedes.

Usage (credentials: see the operator's local runbook):
    MONGODB_URI=... MONGODB_DB=... uv run python scripts/check_ab_test_duplicates.py [--drop-legacy-index] [--json]

Exit code 1 when duplicates exist (the deploy must not proceed), 0 otherwise.
Output carries counts and experiment ids only — no user identifiers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

LEGACY_INDEX = "experiment_id_1"


async def find_duplicates(collection: AsyncIOMotorCollection) -> list[dict]:
    """``[{"experiment_id": ..., "count": n}]`` for every id held by more than one document."""
    pipeline: list[dict[str, Any]] = [
        {"$group": {"_id": "$experiment_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
    ]
    return [
        {"experiment_id": row["_id"], "count": row["count"]}
        async for row in collection.aggregate(pipeline)
    ]


async def drop_legacy_index(collection: AsyncIOMotorCollection) -> bool:
    """Drop the plain ``experiment_id_1`` index if present; True when something was dropped."""
    if LEGACY_INDEX not in await collection.index_information():
        return False
    await collection.drop_index(LEGACY_INDEX)
    return True


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--drop-legacy-index", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    client: AsyncIOMotorClient[Any] = AsyncIOMotorClient(os.environ["MONGODB_URI"])
    collection = client[os.environ["MONGODB_DB"]]["ab_tests"]
    duplicates = await find_duplicates(collection)
    dropped = await drop_legacy_index(collection) if args.drop_legacy_index else False
    report = {
        "documents": await collection.estimated_document_count(),
        "duplicate_ids": len(duplicates),
        "duplicates": duplicates,
        "legacy_index_dropped": dropped,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"ab_tests documents: {report['documents']}")
        print(f"duplicate experiment_ids: {report['duplicate_ids']}")
        for d in duplicates:
            print(f"  {d['experiment_id']}  x{d['count']}")
        if args.drop_legacy_index:
            print(f"legacy index {LEGACY_INDEX} dropped: {dropped}")
    return 1 if duplicates else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
