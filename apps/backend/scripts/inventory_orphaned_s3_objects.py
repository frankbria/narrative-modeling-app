#!/usr/bin/env python3
"""Inventory orphaned dataset/transformation S3 objects — report count and total size (#525 AC4).

Every transformation writes a new object and repoints ``s3_url`` at it; the upload
routes write the object before ``insert()``. Before #467/#525 the superseded and
failed-insert objects were referenced by nothing, so they accumulated cost and were
unreachable to GDPR erasure. #525 makes erasure sweep the tracked intermediates
(``DatasetVersion`` S3 objects); this script measures what already leaked — objects
under the dataset namespaces that NO document references.

An object under ``datasets/`` or ``transformed/`` is an orphan when its key matches
none of: ``UserData``/``DatasetMetadata`` ``s3_url``/``file_path``,
``DatasetMetadata.source_s3_url``, or ``DatasetVersion`` ``s3_url``/``file_path``
(all resolved to keys via the app's own ``parse_s3_url``). Model artifacts under
``models/`` are covered by ``reconcile_model_artifacts.py`` instead.

Read-only always (never deletes — an S3 lifecycle rule, #529/P2.32, is the reclaim
path). Output is counts + bytes only (no keys/ids) unless ``--dump`` is given, so it
is safe to paste into a public issue. An object younger than ``--min-age-seconds``
is excluded as possibly-in-flight. Exit status is 1 while any orphan remains.

Usage (from apps/backend; credentials: see the operator's local runbook):

    MONGODB_URI=... MONGODB_DB=... AWS_BUCKET_NAME=... AWS_ACCESS_KEY_ID=... \\
    AWS_SECRET_ACCESS_KEY=... AWS_REGION=... \\
        uv run python scripts/inventory_orphaned_s3_objects.py [--json] [--dump orphans.txt]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorClient

from app.models.dataset import DatasetMetadata
from app.models.registry import DOCUMENT_MODELS
from app.models.user_data import UserData
from app.models.version import DatasetVersion
from app.services.s3_service import S3Service
from app.utils.s3 import configured_bucket, parse_s3_url

PREFIXES = ("datasets/", "transformed/")


def _key(location: str | None) -> str | None:
    if not location:
        return None
    try:
        return parse_s3_url(location)[1]
    except Exception:
        return location if not location.startswith(("s3://", "http")) else None


async def _referenced_keys() -> set[str]:
    keys: set[str] = set()
    async for d in UserData.find_all():
        keys |= {k for k in (_key(d.s3_url), _key(getattr(d, "file_path", None))) if k}
    async for d in DatasetMetadata.find_all():
        keys |= {k for k in (_key(d.s3_url), _key(getattr(d, "file_path", None)),
                             _key(getattr(d, "source_s3_url", None))) if k}
    async for d in DatasetVersion.find_all():
        keys |= {k for k in (_key(getattr(d, "s3_url", None)),
                             _key(getattr(d, "file_path", None))) if k}
    return keys


def _list_objects(s3: S3Service, bucket: str) -> list[tuple[str, int, object]]:
    objs: list[tuple[str, int, object]] = []
    paginator = s3.s3_client.get_paginator("list_objects_v2")
    for prefix in PREFIXES:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for o in page.get("Contents", []):
                objs.append((o["Key"], o.get("Size", 0), o.get("LastModified")))
    return objs


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dump", metavar="PATH", help="write orphan keys to this file for operator review")
    parser.add_argument("--min-age-seconds", type=int, default=3600,
                        help="exclude objects younger than this as possibly in-flight (default 3600)")
    args = parser.parse_args()

    uri, db_name = os.getenv("MONGODB_URI"), os.getenv("MONGODB_DB")
    if not uri or not db_name:
        print("MONGODB_URI and MONGODB_DB must be set", file=sys.stderr)
        return 2

    s3 = S3Service()
    if s3.is_mock_mode or s3.s3_client is None:
        print("S3 is not configured (mock mode); set real AWS credentials", file=sys.stderr)
        return 2
    bucket = configured_bucket()
    if not bucket:
        print("No S3 bucket configured", file=sys.stderr)
        return 2

    from beanie import init_beanie

    client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
    try:
        await init_beanie(database=client[db_name], document_models=DOCUMENT_MODELS)
        referenced = await _referenced_keys()
        objects = await asyncio.to_thread(_list_objects, s3, bucket)
    finally:
        client.close()

    cutoff = datetime.now(UTC) - timedelta(seconds=args.min_age_seconds)
    orphans = [(k, size) for (k, size, lm) in objects
               if k not in referenced and not (lm is not None and lm > cutoff)]
    recent = sum(1 for (k, _s, lm) in objects
                 if k not in referenced and lm is not None and lm > cutoff)
    if args.dump and orphans:
        with open(args.dump, "w") as fh:
            fh.write("\n".join(k for k, _ in orphans) + "\n")

    total_bytes = sum(size for _, size in orphans)
    result = {
        "objects_scanned": len(objects),
        "referenced_keys": len(referenced),
        "orphans": len(orphans),
        "orphan_bytes": total_bytes,
        "orphan_mib": round(total_bytes / (1024 * 1024), 1),
        "recent_unreferenced_excluded": recent,
    }
    if args.json:
        print(json.dumps(result))
    else:
        print(
            f"scanned {result['objects_scanned']} objects under {PREFIXES}; "
            f"referenced={result['referenced_keys']}; "
            f"ORPHANS={result['orphans']} ({result['orphan_mib']} MiB); "
            f"recent-excluded={result['recent_unreferenced_excluded']}"
            + (f"; keys -> {args.dump}" if (args.dump and orphans) else "")
        )
    return 1 if orphans else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
