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
copy (ContentLength, then ETag or a streamed SHA-256 when the ETag is multipart), rewrites the rows' ``s3_url``/``file_path``, and only
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
import hashlib
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
    failures: int = 0  # copy/verify/rewrite/delete failed; object left in place
    leftover_duplicates: int = 0  # rows already rewritten by an earlier run; only the delete remained
    applied: bool = False

    @property
    def exit_code(self) -> int:
        unreconciled = self.orphans + self.conflicts + self.failures
        if not self.applied:
            unreconciled += self.planned + self.leftover_duplicates
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


@dataclass
class Attribution:
    owner_by_key: dict[str, str | None]
    rows_by_key: dict[str, list[tuple[str, object, str]]]
    conflicts: int
    #: root candidate -> prefixed key a row already points at: an earlier run
    #: copied and rewrote but its delete failed, leaving this duplicate behind.
    migrated_twin: dict[str, str]


async def _owners(db, bucket: str, keys: list[str]) -> Attribution:
    """Attribute each root candidate to its rows, or to the prefixed twin a row
    already points at.

    Matching goes through the app's own URL parser: a stored URL is attributed to
    this bucket and key exactly the way production reads it.
    """
    from app.utils.s3 import parse_s3_url

    wanted = set(keys)
    owner_by_key: dict[str, str | None] = {}
    rows_by_key: dict[str, list[tuple[str, object, str]]] = {k: [] for k in keys}
    conflicting: set[str] = set()  # counted once per key, however many rows disagree
    migrated_twin: dict[str, str] = {}
    for coll in _ROW_COLLECTIONS:
        cursor = db[coll].find(
            {"s3_url": {"$type": "string"}}, {"s3_url": 1, "user_id": 1, "file_path": 1}
        )
        async for doc in cursor:
            try:
                b, key = parse_s3_url(doc["s3_url"])
            except ValueError:
                continue
            if b is not None and b != bucket:
                continue
            if key.startswith("datasets/") and key.count("/") == 2:
                basename = key.rsplit("/", 1)[1]
                if basename in wanted:
                    migrated_twin.setdefault(basename, key)
                continue
            if key not in wanted:
                continue
            rows_by_key[key].append((coll, doc["_id"], doc["s3_url"]))
            owner = doc.get("user_id")
            if key in conflicting:
                continue
            if key in owner_by_key and owner_by_key[key] != owner:
                owner_by_key[key] = None  # rows disagree about the owner
                conflicting.add(key)
            else:
                owner_by_key.setdefault(key, owner)
    return Attribution(owner_by_key, rows_by_key, len(conflicting), migrated_twin)


def _sha256(s3, bucket: str, key: str) -> str:
    digest = hashlib.sha256()
    for chunk in s3.get_object(Bucket=bucket, Key=key)["Body"].iter_chunks(1 << 20):
        digest.update(chunk)
    return digest.hexdigest()


def _copy_and_verify(s3, bucket: str, move: Move) -> bool:
    """Copy, then prove the copy holds the same bytes before anything is deleted.

    ETag equality is only a proof for two single-part, unencrypted objects. The
    upload routes go through ``upload_fileobj``, which switches to multipart above
    8 MB and leaves a ``<md5>-<parts>`` ETag, while ``copy_object`` writes a
    single-part one — identical bytes, different ETags. Insisting on equality
    there would strand every large dataset as a "copy failure", so when either
    ETag is a multipart form (or they simply differ) the bytes are read back and
    hashed instead.
    """
    src = s3.head_object(Bucket=bucket, Key=move.old_key)
    s3.copy_object(
        Bucket=bucket,
        Key=move.new_key,
        CopySource={"Bucket": bucket, "Key": move.old_key},
        MetadataDirective="COPY",
    )
    dst = s3.head_object(Bucket=bucket, Key=move.new_key)
    if dst["ContentLength"] != src["ContentLength"]:
        return False
    single_part = "-" not in src["ETag"] and "-" not in dst["ETag"]
    if single_part and dst["ETag"] == src["ETag"]:
        return True
    return _sha256(s3, bucket, move.old_key) == _sha256(s3, bucket, move.new_key)


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

    attribution = await _owners(db, bucket, candidates)
    report.conflicts = attribution.conflicts

    # An earlier run may have copied and rewritten some or all rows, then failed
    # before the delete. Any row already pointing at the prefixed twin marks the
    # candidate as such a leftover — whether or not other rows (the dual-written
    # sibling collection) still point at the old key, because a rewrite can fail
    # between the two. Finishing it means: prove the twin holds the same bytes,
    # rewrite whatever rows are still stale, then delete the original.
    leftovers = [k for k in candidates if k in attribution.migrated_twin]
    report.leftover_duplicates = len(leftovers)
    if apply:
        for old_key in leftovers:
            twin = attribution.migrated_twin[old_key]
            try:
                if _sha256(s3, bucket, old_key) != _sha256(s3, bucket, twin):
                    report.failures += 1  # twin differs: leave both for a human
                    continue
                move = Move(old_key, twin, attribution.owner_by_key.get(old_key) or "")
                report.rows_rewritten += await _rewrite_rows(db, attribution.rows_by_key[old_key], move)
                s3.delete_object(Bucket=bucket, Key=old_key)
                report.moved += 1
            except Exception:  # noqa: BLE001
                report.failures += 1

    the_plan = plan([k for k in candidates if k not in attribution.migrated_twin], attribution.owner_by_key)
    report.planned = len(the_plan.moves)
    report.orphans = len(the_plan.orphans) - report.conflicts
    if not apply:
        return report

    for move in the_plan.moves:
        rows = attribution.rows_by_key[move.old_key]
        # One bad object must not stop the run — every step is guarded, and the
        # order (copy, verify, rewrite, delete) means a failure at any point leaves
        # either the original or a verified copy plus consistent rows, never
        # neither. Re-running picks the object up again.
        try:
            if not _copy_and_verify(s3, bucket, move):
                report.failures += 1
                continue
            report.rows_rewritten += await _rewrite_rows(db, rows, move)
            s3.delete_object(Bucket=bucket, Key=move.old_key)
        except Exception:  # noqa: BLE001
            report.failures += 1
            continue
        report.moved += 1
    return report


def _print(report: Report) -> None:
    mode = "APPLIED" if report.applied else "DRY RUN"
    print(f"[{mode}] unprefixed objects at bucket root: {report.unprefixed}")
    print(f"  attributable to an owner (planned moves): {report.planned}")
    print(f"  leftovers of an interrupted run (rows already rewritten; delete only): {report.leftover_duplicates}")
    print(f"  moved (copied, verified, rows rewritten, original deleted): {report.moved}")
    print(f"  rows rewritten: {report.rows_rewritten}")
    print(f"  orphans (no owning row; left in place): {report.orphans}")
    print(f"  conflicts (rows disagree on owner; left in place): {report.conflicts}")
    print(f"  failures — copy, verify, rewrite or delete (left in place): {report.failures}")
    if not report.applied and (report.planned or report.leftover_duplicates):
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
