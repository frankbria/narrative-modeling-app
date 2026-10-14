#!/usr/bin/env python3
"""Give dataset rows written before #768 the ``file_size`` they never recorded (#781).

The FREE storage ceiling sums ``UserData.file_size``. Every writer has set it since
#768; a row from before has none and counts as nothing, so that tenant's stored data
is invisible to the ceiling. This reads the size of the object each such row points
at (one HEAD per row) and writes it.

Read-only by default; ``--apply`` writes. Output is counts only — no ids, no keys —
so it is safe to paste into a public issue. A row whose object cannot be read is
counted as ``unreadable`` and left as it is.

Usage (from apps/backend, with the backend's S3 settings; credentials: see the
operator's local runbook):

    PYTHONPATH=. MONGODB_URI=... MONGODB_DB=... uv run python scripts/backfill_dataset_file_sizes.py [--apply] [--json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.models.registry import DOCUMENT_MODELS
from app.models.user_data import UserData
from app.utils.s3 import object_size


async def _write(collection, doc_id, size: int, apply: bool) -> int:
    """A targeted $set, for the reason a move is one (#723): a save of this run's copy
    would write every other field back as it was when the run read it."""
    if not apply:
        return 0
    # Only a row still unsized: a move that landed since the scan has already written the
    # size of the file the dataset is on now, and that one is the truth. Counted only if
    # this write was the one that landed.
    result = await collection.update_one({"_id": doc_id, "file_size": None}, {"$set": {"file_size": size}})
    return result.modified_count


async def backfill(*, apply: bool) -> dict[str, int]:
    """Size every ``UserData`` row that has no ``file_size``. Returns the counts."""
    # The stored documents, not the models: only the three fields are needed, and a
    # model load would run every validator on rows this has no business touching.
    collection = UserData.get_motor_collection()
    counts = {"missing": 0, "sized": 0, "bytes": 0, "written": 0, "unreadable": 0}
    async for doc in collection.find({"file_size": None}, {"s3_url": 1}):
        counts["missing"] += 1
        size = await asyncio.to_thread(object_size, doc.get("s3_url") or "")
        if size is None:
            counts["unreadable"] += 1
            continue
        counts["sized"] += 1
        counts["bytes"] += size
        counts["written"] += await _write(collection, doc["_id"], size, apply)
    return counts


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the sizes (default: dry run)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    uri, db_name = os.getenv("MONGODB_URI"), os.getenv("MONGODB_DB")
    if not uri or not db_name:
        print("MONGODB_URI and MONGODB_DB must be set", file=sys.stderr)
        return 2

    client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
    try:
        await init_beanie(database=client[db_name], document_models=DOCUMENT_MODELS)
        counts = await backfill(apply=args.apply)
    finally:
        client.close()

    if args.json:
        print(json.dumps({**counts, "applied": args.apply}))
    else:
        print(" ".join(f"{name}={value}" for name, value in counts.items()), f"applied={args.apply}")
    # 1 while rows remain unsized: a dry run that found some, or objects that could not be read.
    return 1 if counts["missing"] - counts["written"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
