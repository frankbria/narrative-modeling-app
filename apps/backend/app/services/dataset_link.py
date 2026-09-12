"""Keep the two dataset id-spaces linked when a dataset moves to a new file (#467, #627).

`DatasetMetadata` (string `dataset_id`) and legacy `UserData` (ObjectId) are dual-written
and joined only by `(user_id, s3_url)`. A transformation that rewrote `s3_url` on one side
severed that join: erasure lost the PII-carrying `UserData` twin, and training — which
reads `UserData.s3_url` — silently kept using the pre-transform file. Every writer that
moves a dataset to a new current file goes through here so both twins move together.

No multi-document transaction: the `UserData` twin is written first, so a failure between
the two writes leaves the erasure-critical side already moved.
"""
import logging
from datetime import UTC, datetime

from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData

logger = logging.getLogger(__name__)


async def record_new_file(doc: DatasetMetadata | UserData, new_url: str) -> None:
    """Point `doc` AND its dual-written twin at `new_url` (a full, downloadable URL).

    The twin is found through the *old* `(user_id, s3_url)` before either changes. A
    dataset with no twin (only one side was ever written) moves alone. The original
    upload is kept in `DatasetMetadata.source_s3_url` the first time.
    """
    old_url = doc.s3_url
    twin: DatasetMetadata | UserData | None = None
    if old_url:
        if isinstance(doc, DatasetMetadata):
            twin = await UserData.find_one(UserData.user_id == doc.user_id, UserData.s3_url == old_url)
        else:
            twin = await DatasetMetadata.find_one(
                DatasetMetadata.user_id == doc.user_id, DatasetMetadata.s3_url == old_url
            )
    if twin is None:
        logger.info("No dual-written twin for %s at its current location; moving one side", type(doc).__name__)

    # UserData first: it carries the PII erasure must be able to reach.
    ordered = sorted((d for d in (doc, twin) if d is not None), key=lambda d: isinstance(d, DatasetMetadata))
    for d in ordered:
        if isinstance(d, DatasetMetadata):
            if not d.source_s3_url:
                d.source_s3_url = old_url
            d.file_path = new_url
            d.s3_url = new_url
            d.update_timestamp()
        else:
            d.file_path = new_url
            d.s3_url = new_url
            d.updated_at = datetime.now(UTC)
        await d.save()
