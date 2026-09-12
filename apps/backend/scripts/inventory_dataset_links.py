"""Inventory the dual-written dataset twins whose link is broken (#467 AC4).

``DatasetMetadata`` and legacy ``UserData`` are joined only by ``(user_id, s3_url)``.
Before #467 a transformation rewrote ``s3_url`` on one side, so some pairs no longer
match. This counts, per side, documents with no partner at their location — read-only,
counts only (no ids, no URLs, no user identifiers in the output).

Usage (see the operator's local runbook for credentials):

    MONGODB_URI=... MONGODB_DB=... uv run python scripts/inventory_dataset_links.py [--json]

Exit code 0 always; the numbers are the deliverable. A non-zero "broken" count is the
input to a repair migration, which is its own issue.
"""
import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.models.dataset import DatasetMetadata
from app.models.registry import DOCUMENT_MODELS
from app.models.user_data import UserData


@dataclass
class Inventory:
    dataset_metadata_total: int = 0
    user_data_total: int = 0
    linked_pairs: int = 0
    #: DatasetMetadata rows with no UserData at their (user_id, s3_url)
    metadata_without_twin: int = 0
    #: ...of which the metadata has moved (source_s3_url set) — a pre-#467 severed link
    #: is the *other* case: moved before the field existed, so it shows as plain "without twin"
    metadata_moved_with_twin_intact: int = 0
    #: UserData rows with no DatasetMetadata at their (user_id, s3_url)
    user_data_without_twin: int = 0


async def inventory() -> Inventory:
    inv = Inventory()
    user_data_locations: set[tuple[str, str]] = set()
    ud: UserData
    async for ud in UserData.find_all():
        inv.user_data_total += 1
        if ud.s3_url:
            user_data_locations.add((ud.user_id, ud.s3_url))
    metadata_locations: set[tuple[str, str]] = set()
    meta: DatasetMetadata
    async for meta in DatasetMetadata.find_all():
        inv.dataset_metadata_total += 1
        loc = (meta.user_id, meta.s3_url)
        metadata_locations.add(loc)
        if loc in user_data_locations:
            inv.linked_pairs += 1
            if meta.source_s3_url:
                inv.metadata_moved_with_twin_intact += 1
        else:
            inv.metadata_without_twin += 1
    inv.user_data_without_twin = sum(1 for loc in user_data_locations if loc not in metadata_locations)
    return inv


async def _main(as_json: bool) -> int:
    uri, db = os.getenv("MONGODB_URI"), os.getenv("MONGODB_DB")
    if not uri or not db:
        print("MONGODB_URI and MONGODB_DB are required", file=sys.stderr)
        return 2
    client = AsyncIOMotorClient(uri)
    await init_beanie(database=client[db], document_models=DOCUMENT_MODELS)
    inv = await inventory()
    if as_json:
        print(json.dumps(asdict(inv), indent=2))
    else:
        for k, v in asdict(inv).items():
            print(f"{k:34} {v}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args.json)))
