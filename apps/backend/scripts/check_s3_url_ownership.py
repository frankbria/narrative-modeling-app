#!/usr/bin/env python3
"""#451 AC5 — look for UserData rows whose s3_url points outside the deployment.

Read-only. Reports counts and per-user summaries; prints no object keys and no
credentials, so its output is safe to paste into a public issue.

Usage (from apps/backend, against whichever cluster you want to check):

    MONGODB_URI=... MONGODB_DB=... AWS_BUCKET_NAME=... \
        uv run python scripts/check_s3_url_ownership.py

Exit status is 1 if anything suspicious is found, so it can gate a deploy.

Endpoint-style deployments are handled: URL parsing reuses the app's own
`parse_s3_url`, so set AWS_ENDPOINT_URL here to whatever the deployment uses and
`{endpoint}/{bucket}/{key}` URLs resolve to their real bucket.
"""
import asyncio
import os
import sys
from collections import Counter


def bucket_of(s3_url: str) -> str | None:
    """Bucket for a stored URL, using the app's own parser.

    Deliberately not a second implementation: an audit that disagrees with
    production about what a URL means reports the wrong thing. `parse_s3_url`
    already handles s3://, path-style endpoint URLs, virtual-host and presigned
    shapes, so this stays correct as those evolve.
    """
    from app.utils.s3 import parse_s3_url

    try:
        bucket, _ = parse_s3_url(s3_url)
    except ValueError:
        return None
    return bucket


async def main() -> int:
    from motor.motor_asyncio import AsyncIOMotorClient

    uri, db_name = os.getenv("MONGODB_URI"), os.getenv("MONGODB_DB")
    if not uri or not db_name:
        print("Set MONGODB_URI and MONGODB_DB.", file=sys.stderr)
        return 2

    allowed = {b for b in (
        os.getenv("AWS_BUCKET_NAME"),
        os.getenv("S3_BUCKET_NAME"),
        os.getenv("AWS_S3_BUCKET"),
    ) if b}
    if not allowed:
        print("Set AWS_BUCKET_NAME (the bucket this deployment owns).", file=sys.stderr)
        return 2

    collection = AsyncIOMotorClient(uri)[db_name]["user_data"]

    total = 0
    foreign_bucket: Counter[str] = Counter()
    unparseable = 0
    placeholders = 0
    users_with_foreign: set[str] = set()

    async for doc in collection.find({}, {"user_id": 1, "s3_url": 1}):
        total += 1
        url = doc.get("s3_url") or ""
        if url in ("s3_not_configured", "s3_upload_failed", ""):
            placeholders += 1
            continue
        bucket = bucket_of(url)
        if bucket is None:
            unparseable += 1
            continue
        if bucket not in allowed:
            foreign_bucket[bucket] += 1
            users_with_foreign.add(str(doc.get("user_id")))

    print(f"rows scanned:            {total}")
    print(f"allowed bucket(s):       {sorted(allowed)}")
    print(f"placeholder / empty:     {placeholders}")
    print(f"unparseable s3_url:      {unparseable}")
    print(f"rows in a FOREIGN bucket: {sum(foreign_bucket.values())}")
    for bucket, count in foreign_bucket.most_common():
        print(f"    {bucket}: {count}")
    print(f"distinct users affected: {len(users_with_foreign)}")

    if foreign_bucket:
        print("\nFOREIGN BUCKET REFERENCES FOUND — evidence of use, not just exposure.")
        return 1
    if unparseable:
        print("\nUNPARSEABLE s3_url VALUES — needs manual review; a URL whose bucket"
              "\ncannot be determined has not been cleared, only skipped.")
        return 1
    print("\nNo s3_url outside the configured bucket(s).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
