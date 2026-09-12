"""Keep the two dataset id-spaces linked when a dataset moves to a new file (#467, #627).

`DatasetMetadata` (string `dataset_id`) and legacy `UserData` (ObjectId) are dual-written
and joined only by `(user_id, s3_url)`. A transformation that rewrote `s3_url` on one side
severed that join: erasure lost the PII-carrying `UserData` twin, and training — which
reads `UserData.s3_url` — silently kept using the pre-transform file. Every writer that
moves a dataset to a new current file goes through here so both twins move together.

No multi-document transaction. The join is symmetric, so a failure between the two
writes leaves it broken whichever side went first: `erase_dataset` (which joins from the
metadata's `s3_url` to the twin) would then miss the PII-carrying `UserData` row. Writing
`UserData` first protects `erase_user`, which sweeps `UserData` rows by `user_id` without
the join. A half-failure is logged at ERROR with both locations so the operator can repair
it; `scripts/inventory_dataset_links.py` finds every pair in that state.
"""
import logging
from datetime import UTC, datetime

from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData

logger = logging.getLogger(__name__)


_KNOWN_TYPES = {"parquet", "csv", "json", "xlsx", "xls"}


def _file_type_of(url: str) -> str | None:
    """The stored `file_type` value for a location, from its extension; None if unknown."""
    ext = url.split("?", 1)[0].rsplit(".", 1)[-1].lower()
    return ext if ext in _KNOWN_TYPES else None


async def record_new_file(doc: DatasetMetadata | UserData, new_url: str) -> None:
    """Point `doc` AND its dual-written twin at `new_url` (a full, downloadable URL).

    The twin is found through the *old* `(user_id, s3_url)` before either changes. A
    dataset with no twin (only one side was ever written) moves alone. The original
    upload is kept in `DatasetMetadata.source_s3_url` the first time.
    """
    # Look the twin up at the dataset's CURRENT stored location, not the one this
    # in-memory `doc` was loaded with: two overlapping transformations each load the
    # dataset, the first moves both twins, and the second would otherwise search the
    # stale URL, find nothing, and move its own side alone — re-severing the link (codex).
    model: type[DatasetMetadata] | type[UserData] = (
        DatasetMetadata if isinstance(doc, DatasetMetadata) else UserData
    )
    current = await model.get(doc.id) if doc.id is not None else None
    old_url = (current.s3_url if current is not None else None) or doc.s3_url
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

    # Every writer uploads the transformed frame as parquet, so a dataset uploaded as CSV
    # would otherwise be parsed as CSV by readers that dispatch on file_type (#524, codex).
    new_type = _file_type_of(new_url)
    if new_type:
        doc.file_type = new_type

    # The caller set the new shape (rows/columns) on `doc`; the twin's legacy readers
    # (mode-recommendation, user_data preview) describe the same file, so it follows (codex).
    if twin is not None:
        for field in ("num_rows", "num_columns", "columns", "file_type"):
            value = getattr(doc, field, None)
            if value is not None:
                setattr(twin, field, value)

    # UserData first: it carries the PII erasure must be able to reach.
    if isinstance(doc, DatasetMetadata):
        ordered = [twin, doc]
    else:
        ordered = [doc, twin]
    moved: list[str] = []
    for d in ordered:
        if d is None:
            continue
        if isinstance(d, DatasetMetadata):
            if not d.source_s3_url:
                # a stale in-memory doc must not overwrite a source the DB already knows
                stored = current.source_s3_url if isinstance(current, DatasetMetadata) else None
                d.source_s3_url = stored or old_url
            d.file_path = new_url
            d.s3_url = new_url
            d.update_timestamp()
        else:
            d.file_path = new_url
            d.s3_url = new_url
            d.updated_at = datetime.now(UTC)
        try:
            await d.save()
        except Exception:
            if moved:
                logger.error(
                    "Dataset link half-moved: %s already at %s, %s still at %s (user %s) — "
                    "run scripts/inventory_dataset_links.py and repair",
                    ", ".join(moved), new_url, type(d).__name__, old_url, d.user_id,
                )
            raise
        moved.append(type(d).__name__)
