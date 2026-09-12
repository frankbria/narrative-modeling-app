#!/usr/bin/env python3
"""Move bucket-root dataset objects under their owner's prefix (#581).

Until #581 the ``/upload/secure``, ``/upload/confirm-pii-upload`` and ``/upload/``
routes keyed every object as a bare ``{uuid4}.{ext}`` (``masked_{uuid4}.{ext}`` for a
PII-masked copy). The strict downloader, ``DatasetErasureService`` and any per-tenant
lifecycle rule all key on ``datasets/{user_id}/``, so those objects are unreachable,
survive account erasure, and cannot be expired — 155 of them sat in the production
bucket when the issue was filed.

For each such object this script finds the owning ``UserData``/``DatasetMetadata``
rows by ``s3_url`` (through the app's own ``parse_s3_url``, so every stored URL shape
resolves), copies the object to ``datasets/{owner}/{same basename}``, verifies the
copy (ContentLength and ETag), rewrites the rows' ``s3_url``/``file_path``, and only
then deletes the original. An object with **no** owning row is reported and never
touched — nothing here deletes data it cannot attribute. Rows that disagree about
the owner are treated the same way.

Read-only by default; ``--apply`` writes. Output is counts only — no keys, no user
ids — so it is safe to paste into a public issue. Exit status is 1 while any
unreconciled object remains (planned-but-not-applied, orphaned or conflicting).

Usage (from apps/backend, against whichever bucket/cluster you want to check):

    MONGODB_URI=... MONGODB_DB=... AWS_BUCKET_NAME=... \\
    AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=... \\
        uv run python scripts/reconcile_unprefixed_s3_keys.py
    # ... same environment, plus --apply, to move the objects
"""

import asyncio
import os
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_UNPREFIXED = re.compile(rf"^(masked_)?{_UUID}(\.[A-Za-z0-9]+)?$")


def is_unprefixed_dataset_key(key: str) -> bool:
    """True for the exact shape the old helper produced, at the bucket root."""
    return bool(key) and _UNPREFIXED.match(key) is not None


def new_key_for(old_key: str, user_id: str) -> str:
    return f"datasets/{user_id}/{old_key}"


@dataclass(frozen=True)
class Move:
    old_key: str
    new_key: str
    user_id: str


@dataclass
class Plan:
    moves: list[Move] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)


def plan(keys: Iterable[str], owner_by_key: Mapping[str, str | None]) -> Plan:
    """Partition unprefixed keys into moves (owner known) and orphans (owner unknown)."""
    result = Plan()
    for key in keys:
        owner = owner_by_key.get(key)
        if owner:
            result.moves.append(Move(key, new_key_for(key, owner), owner))
        else:
            result.orphans.append(key)
    return result


@dataclass
class Report:
    unprefixed: int = 0
    planned: int = 0
    moved: int = 0
    rows_rewritten: int = 0
    orphans: int = 0
    conflicts: int = 0
    copy_failures: int = 0
    applied: bool = False

    @property
    def exit_code(self) -> int:
        unreconciled = self.orphans + self.conflicts + self.copy_failures
        if not self.applied:
            unreconciled += self.planned
        return 1 if unreconciled else 0


_ROW_COLLECTIONS = ("user_data", "dataset_metadata")


def _list_root_candidates(s3, bucket: str) -> list[str]:
    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    # Delimiter="/" returns only bucket-root objects in Contents; prefixed
    # objects fold into CommonPrefixes and are never candidates.
    for page in paginator.paginate(Bucket=bucket, Delimiter="/"):
        keys.extend(o["Key"] for o in page.get("Contents", []))
    return [k for k in keys if is_unprefixed_dataset_key(k)]


async def _owners(db, bucket: str, keys: list[str]) -> tuple[dict[str, str | None], dict[str, list[tuple[str, object, str]]], int]:
    """Map key -> owner (None if unknown/conflicting) and key -> [(collection, _id, s3_url)].

    Matching goes through the app's own URL parser: a stored URL is attributed to
    this bucket and key exactly the way production reads it.
    """
    from app.utils.s3 import parse_s3_url

    wanted = set(keys)
    owner_by_key: dict[str, str | None] = {}
    rows_by_key: dict[str, list[tuple[str, object, str]]] = {k: [] for k in keys}
    conflicts = 0
    for coll in _ROW_COLLECTIONS:
        cursor = db[coll].find(
            {"s3_url": {"$type": "string"}}, {"s3_url": 1, "user_id": 1, "file_path": 1}
        )
        async for doc in cursor:
            try:
                b, key = parse_s3_url(doc["s3_url"])
            except ValueError:
                continue
            if key not in wanted or (b is not None and b != bucket):
                continue
            rows_by_key[key].append((coll, doc["_id"], doc["s3_url"]))
            owner = doc.get("user_id")
            if key in owner_by_key and owner_by_key[key] != owner:
                owner_by_key[key] = None  # rows disagree about the owner
                conflicts += 1
            else:
                owner_by_key.setdefault(key, owner)
    return owner_by_key, rows_by_key, conflicts


def _copy_and_verify(s3, bucket: str, move: Move) -> bool:
    src = s3.head_object(Bucket=bucket, Key=move.old_key)
    s3.copy_object(
        Bucket=bucket,
        Key=move.new_key,
        CopySource={"Bucket": bucket, "Key": move.old_key},
        MetadataDirective="COPY",
    )
    dst = s3.head_object(Bucket=bucket, Key=move.new_key)
    return dst["ContentLength"] == src["ContentLength"] and dst["ETag"] == src["ETag"]


async def _rewrite_rows(db, rows: list[tuple[str, object, str]], move: Move) -> int:
    rewritten = 0
    for coll, _id, s3_url in rows:
        # Replace the final occurrence of the key so the URL keeps its shape
        # (s3://, virtual-host or endpoint-style) and any query string.
        head, sep, tail = s3_url.rpartition(move.old_key)
        new_url = f"{head}{move.new_key}{tail}" if sep else s3_url
        result = await db[coll].update_one(
            {"_id": _id},
            [
                {
                    "$set": {
                        "s3_url": new_url,
                        "file_path": {
                            "$cond": [
                                {"$eq": ["$file_path", move.old_key]},
                                move.new_key,
                                "$file_path",
                            ]
                        },
                    }
                }
            ],
        )
        rewritten += result.modified_count
    return rewritten


async def reconcile(s3, bucket: str, db, *, apply: bool) -> Report:
    report = Report(applied=apply)
    candidates = _list_root_candidates(s3, bucket)
    report.unprefixed = len(candidates)
    if not candidates:
        return report

    owner_by_key, rows_by_key, report.conflicts = await _owners(db, bucket, candidates)
    the_plan = plan(candidates, owner_by_key)
    report.planned = len(the_plan.moves)
    report.orphans = len(the_plan.orphans) - report.conflicts
    if not apply:
        return report

    for move in the_plan.moves:
        try:
            ok = _copy_and_verify(s3, bucket, move)
        except Exception:  # noqa: BLE001 - one bad object must not stop the run
            ok = False
        if not ok:
            report.copy_failures += 1
            continue
        report.rows_rewritten += await _rewrite_rows(db, rows_by_key[move.old_key], move)
        s3.delete_object(Bucket=bucket, Key=move.old_key)
        report.moved += 1
    return report


def _print(report: Report) -> None:
    mode = "APPLIED" if report.applied else "DRY RUN"
    print(f"[{mode}] unprefixed objects at bucket root: {report.unprefixed}")
    print(f"  attributable to an owner (planned moves): {report.planned}")
    print(f"  moved (copied, verified, rows rewritten, original deleted): {report.moved}")
    print(f"  rows rewritten: {report.rows_rewritten}")
    print(f"  orphans (no owning row; left in place): {report.orphans}")
    print(f"  conflicts (rows disagree on owner; left in place): {report.conflicts}")
    print(f"  copy failures (left in place): {report.copy_failures}")
    if not report.applied and report.planned:
        print("  re-run with --apply to move them")


async def main() -> int:
    from motor.motor_asyncio import AsyncIOMotorClient

    from app.config import resolve_s3_bucket
    from app.utils.s3 import get_s3_client

    apply = "--apply" in sys.argv[1:]
    uri, db_name = os.getenv("MONGODB_URI"), os.getenv("MONGODB_DB")
    bucket = resolve_s3_bucket()
    if not uri or not db_name or not bucket:
        print("Set MONGODB_URI, MONGODB_DB and AWS_BUCKET_NAME.", file=sys.stderr)
        return 2
    s3 = get_s3_client()
    if s3 is None:
        print("S3 client unavailable: set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY.", file=sys.stderr)
        return 2
    client = AsyncIOMotorClient(uri)
    try:
        report = await reconcile(s3, bucket, client[db_name], apply=apply)
    finally:
        client.close()
    _print(report)
    return report.exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
