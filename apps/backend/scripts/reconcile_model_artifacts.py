#!/usr/bin/env python3
"""Report orphaned model artifacts: S3 objects under ``models/`` that no MLModel
references (#521).

``delete_model`` used to swallow an S3 delete failure and delete the Mongo row
anyway, orphaning the artifact — unreferenced storage cost, and (since a model
artifact encodes its training data) customer-derived data that GDPR erasure could
never reach. #521 stops the leak going forward; this sweeper finds the objects
already orphaned by the old behavior.

For every object under the ``models/`` prefix it checks whether any MLModel's
``model_path`` / ``feature_transformer_path`` / ``evaluation_data_path`` /
``shap_values_path`` resolves (via the app's own ``parse_s3_url``) to that key. An
object referenced by no model is an orphan.

Read-only always (this script never deletes — deleting an "orphan" that is really a
mis-parsed reference would destroy a live model's artifact). Output is counts only —
no keys, no user ids — so it is safe to paste into a public issue. A sample of orphan
keys is written to a file only when ``--dump <path>`` is given, for the operator to
review before any manual cleanup. Exit status is 1 while any orphan remains.

Usage (from apps/backend, against whichever bucket/cluster you want to check;
credentials: see the operator's local runbook):

    MONGODB_URI=... MONGODB_DB=... AWS_BUCKET_NAME=... \\
    AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=... \\
        uv run python scripts/reconcile_model_artifacts.py [--json] [--dump orphans.txt]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient

# The app modules resolve bucket/keys exactly like the running service.
from app.models.ml_model import MLModel
from app.models.registry import DOCUMENT_MODELS
from app.services.model_storage import _key_of
from app.services.s3_service import S3Service
from app.utils.s3 import configured_bucket

MODELS_PREFIX = "models/"


def _referenced_keys_of(model: MLModel) -> set[str]:
    keys: set[str] = set()
    for path in (
        model.model_path,
        model.feature_transformer_path,
        model.evaluation_data_path,
        getattr(model, "shap_values_path", None),
    ):
        if path:
            try:
                keys.add(_key_of(path))
            except Exception:
                # An unparseable stored path is its own problem; skip it here so
                # one bad row doesn't hide every orphan.
                pass
    return keys


async def _all_referenced_keys() -> set[str]:
    referenced: set[str] = set()
    async for model in MLModel.find_all():
        referenced |= _referenced_keys_of(model)
    return referenced


def _list_model_objects(s3: S3Service, bucket: str) -> list[tuple[str, object]]:
    """(key, LastModified) for every object under the models/ prefix."""
    objs: list[tuple[str, object]] = []
    paginator = s3.s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=MODELS_PREFIX):
        for obj in page.get("Contents", []):
            objs.append((obj["Key"], obj.get("LastModified")))
    return objs


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dump", metavar="PATH", help="write orphan keys to this file for operator review")
    parser.add_argument(
        "--min-age-seconds", type=int, default=3600,
        help="an unreferenced object younger than this is 'recent' not 'orphan' — "
             "save_model writes artifacts BEFORE inserting the MLModel doc, so a "
             "just-written artifact of an in-flight training job has no reference yet "
             "(default 3600, ~ the training wall-clock ceiling)",
    )
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
        referenced = await _all_referenced_keys()
        objects = await asyncio.to_thread(_list_model_objects, s3, bucket)
    finally:
        client.close()

    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(seconds=args.min_age_seconds)
    unreferenced = [(k, lm) for (k, lm) in objects if k not in referenced]
    # A just-written artifact of an in-flight training job has no MLModel row yet
    # (save_model uploads before insert), so don't call it an orphan — flag it as
    # recent and exclude it from the cleanup candidates.
    recent = [k for (k, lm) in unreferenced if lm is not None and lm > cutoff]
    orphans = [k for (k, lm) in unreferenced if not (lm is not None and lm > cutoff)]
    if args.dump and orphans:
        with open(args.dump, "w") as fh:
            fh.write("\n".join(orphans) + "\n")

    result = {
        "models_prefix_objects": len(objects),
        "referenced_keys": len(referenced),
        "orphans": len(orphans),
        "recent_unreferenced_excluded": len(recent),
        "min_age_seconds": args.min_age_seconds,
        "dumped_to": args.dump if (args.dump and orphans) else None,
    }
    if args.json:
        print(json.dumps(result))
    else:
        print(
            f"objects under {MODELS_PREFIX}: {result['models_prefix_objects']}, "
            f"referenced by an MLModel: {result['referenced_keys']}, "
            f"orphans: {result['orphans']}, "
            f"recent-unreferenced excluded (< {args.min_age_seconds}s, likely in-flight): "
            f"{result['recent_unreferenced_excluded']}"
            + (f" (orphan keys written to {args.dump})" if result["dumped_to"] else "")
        )
    return 1 if orphans else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
