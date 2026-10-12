#!/usr/bin/env python3
"""Find (and optionally fix) dataset rows whose ``file_type`` disagrees with the
extension of the object it points at (#524).

A transformation once rewrote ``s3_url`` to a ``.parquet`` object while
``file_type`` stayed ``"csv"``, so every reader that dispatches on ``file_type``
parsed parquet bytes as CSV. #524's `record_new_file` fix keeps the two in step
going forward; this reconciles rows already written with a mismatched pair, across
both dual-written twins (``UserData`` and ``DatasetMetadata``).

The object's extension (``s3_url``, then ``file_path``) is authoritative — it names
the bytes that actually exist — so a mismatch is corrected by setting ``file_type``
to the extension-derived type (the same derivation `record_new_file` uses). The one
exception is a version object (``…/versions/…``) not named ``.parquet``: until #888
those held parquet under the upload's name, so the script downloads it and the bytes
decide. That needs the S3 settings the backend runs with. Rows whose location has no
recognizable extension, or whose version object cannot be read, are reported as
``undetermined`` and never changed.

Read-only by default; ``--apply`` writes the corrected ``file_type``. Output is
counts only — no ids, no keys — so it is safe to paste into a public issue. Exit
status is 1 while any mismatch remains (a dry run that found some, or a failed apply).

Usage (from apps/backend; credentials: see the operator's local runbook):

    MONGODB_URI=... MONGODB_DB=... uv run python scripts/audit_dataset_file_types.py [--apply] [--json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.models.dataset import DatasetMetadata
from app.models.registry import DOCUMENT_MODELS
from app.models.user_data import UserData
from app.services.dataset_link import file_type_at


async def _expected_type(location: str) -> str | None:
    """What the object at ``location`` holds, by its extension; None when that cannot be told."""
    try:
        return await file_type_at(location)
    except Exception as e:
        # A version object that could not be read: its name proves nothing (#888).
        # Say why, by class only (this output gets pasted into public issues), so
        # missing S3 settings do not pass for "nothing to fix".
        print(f"unreadable version object: {type(e).__name__}", file=sys.stderr)
        return None


async def _audit(model, *, apply: bool) -> dict[str, int]:
    # The stored documents, not the models: a model shows a row stored as "excel"
    # under its extension (#902), which is exactly the row this has to find.
    collection = model.get_motor_collection()
    counts = {"checked": 0, "mismatched": 0, "fixed": 0, "undetermined": 0}
    async for doc in collection.find({}, {"file_type": 1, "s3_url": 1, "file_path": 1}):
        for outcome in await _outcomes(collection, doc, apply):
            counts[outcome] += 1
    return counts


def _location(doc: dict) -> str | None:
    return doc.get("s3_url") or doc.get("file_path")


def _stored_type(doc: dict) -> str:
    return (doc.get("file_type") or "").lower()


async def _outcomes(collection, doc: dict, apply: bool) -> list[str]:
    """What one stored row adds to the counts."""
    location = _location(doc)
    if not location:
        return []
    expected = await _expected_type(location)
    if expected is None:
        return ["checked", "undetermined"]
    if _stored_type(doc) == expected:
        return ["checked"]
    return ["checked", "mismatched", *await _fix(collection, doc["_id"], expected, apply)]


async def _fix(collection, doc_id, expected: str, apply: bool) -> list[str]:
    """A targeted $set, for the reason a move is one (#723): a save of this run's copy
    would write every other field back as it was when the audit read it."""
    if not apply:
        return []
    await collection.update_one({"_id": doc_id}, {"$set": {"file_type": expected}})
    return ["fixed"]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the corrected file_type (default: dry run)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    uri, db_name = os.getenv("MONGODB_URI"), os.getenv("MONGODB_DB")
    if not uri or not db_name:
        print("MONGODB_URI and MONGODB_DB must be set", file=sys.stderr)
        return 2

    client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
    try:
        await init_beanie(database=client[db_name], document_models=DOCUMENT_MODELS)
        user_data = await _audit(UserData, apply=args.apply)
        metadata = await _audit(DatasetMetadata, apply=args.apply)
    finally:
        client.close()

    result = {"user_data": user_data, "dataset_metadata": metadata, "applied": args.apply}
    if args.json:
        print(json.dumps(result))
    else:
        for name, r in (("UserData", user_data), ("DatasetMetadata", metadata)):
            print(
                f"{name}: checked={r['checked']} mismatched={r['mismatched']} "
                f"fixed={r['fixed']} undetermined={r['undetermined']}"
            )
        print(f"applied={args.apply}")

    remaining = (user_data["mismatched"] - user_data["fixed"]) + (
        metadata["mismatched"] - metadata["fixed"]
    )
    return 1 if remaining > 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
