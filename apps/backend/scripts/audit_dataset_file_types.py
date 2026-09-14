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
to the extension-derived type (the same derivation `record_new_file` uses). Rows
whose location has no recognizable extension are reported as ``undetermined`` and
never changed.

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
from app.services.dataset_link import _file_type_of


async def _audit(model, *, apply: bool) -> dict[str, int]:
    checked = mismatched = fixed = undetermined = 0
    async for doc in model.find_all():
        location = doc.s3_url or getattr(doc, "file_path", None)
        if not location:
            continue
        checked += 1
        expected = _file_type_of(location)
        if expected is None:
            undetermined += 1
            continue
        if (doc.file_type or "").lower() != expected:
            mismatched += 1
            if apply:
                doc.file_type = expected
                await doc.save()
                fixed += 1
    return {
        "checked": checked,
        "mismatched": mismatched,
        "fixed": fixed,
        "undetermined": undetermined,
    }


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
                f"fixed={r['fixed']} undetermined(no extension)={r['undetermined']}"
            )
        print(f"applied={args.apply}")

    remaining = (user_data["mismatched"] - user_data["fixed"]) + (
        metadata["mismatched"] - metadata["fixed"]
    )
    return 1 if remaining > 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
