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


# What the caller may have changed on the document for the new file (#723: these and the
# link fields are the only ones the move writes). The twin gets the same shape, not the schema.
_SHAPE_FIELDS = ("num_rows", "num_columns", "columns", "file_type")

Dataset = DatasetMetadata | UserData


async def record_new_file(doc: Dataset, new_url: str) -> None:
    """Point `doc` AND its dual-written twin at `new_url` (a full, downloadable URL).

    The twin is found through the *old* `(user_id, s3_url)` before either changes. A
    dataset with no twin (only one side was ever written) moves alone. The original
    upload is kept in `DatasetMetadata.source_s3_url` the first time.

    Each document gets one targeted `$set` of the fields the move owns, never a
    full-document save: a save of the caller's in-memory snapshot reverted whatever
    another writer had changed since it was loaded (#723, the class #520 fixed).
    """
    # Look the twin up at the dataset's CURRENT stored location, not the one this
    # in-memory `doc` was loaded with: two overlapping transformations each load the
    # dataset, the first moves both twins, and the second would otherwise search the
    # stale URL, find nothing, and move its own side alone — re-severing the link (codex).
    current = await _stored(doc)
    old_url = _current_url(current, doc)
    twin = await _find_twin(doc, old_url)
    # Every writer uploads the transformed frame as parquet, so a dataset uploaded as CSV
    # would otherwise be parsed as CSV by readers that dispatch on file_type (#524, codex).
    doc.file_type = _file_type_of(new_url) or doc.file_type
    await _move_all(_erasure_order(doc, twin), doc, current, old_url, new_url)


def _current_url(current: Dataset | None, doc: Dataset) -> str | None:
    return (current.s3_url if current is not None else None) or doc.s3_url


async def _move_all(
    docs: list[Dataset], doc: Dataset, current: Dataset | None, old_url: str | None, new_url: str
) -> None:
    moved: list[str] = []
    for d in docs:
        try:
            await _write(d, _move_fields(d, doc, _fresh_copy(d, doc, current), old_url, new_url))
        except Exception:
            _log_half_move(moved, d, new_url, old_url)
            raise
        moved.append(type(d).__name__)


def _fresh_copy(d: Dataset, doc: Dataset, current: Dataset | None) -> Dataset:
    """d as the database holds it: the re-read copy for the caller's document (the twin
    was just read)."""
    return (current if d is doc else None) or d

async def _stored(doc: Dataset) -> Dataset | None:
    """The document as the database holds it now; None for one not yet inserted."""
    model: type[DatasetMetadata] | type[UserData] = (
        DatasetMetadata if isinstance(doc, DatasetMetadata) else UserData
    )
    return await model.get(doc.id) if doc.id is not None else None


async def _find_twin(doc: Dataset, old_url: str | None) -> Dataset | None:
    twin: Dataset | None = None
    if old_url:
        other = UserData if isinstance(doc, DatasetMetadata) else DatasetMetadata
        twin = await other.find_one(other.user_id == doc.user_id, other.s3_url == old_url)
    if twin is None:
        logger.info("No dual-written twin for %s at its current location; moving one side", type(doc).__name__)
    return twin


def _erasure_order(doc: Dataset, twin: Dataset | None) -> list[Dataset]:
    """UserData first: it carries the PII erasure must be able to reach."""
    pair = (twin, doc) if isinstance(doc, DatasetMetadata) else (doc, twin)
    return [d for d in pair if d is not None]


def _move_fields(d: Dataset, doc: Dataset, fresh: Dataset, old_url: str | None, new_url: str) -> dict:
    """The fields the move owns on `d`. `fresh` is d's freshest stored copy, so the
    superseded list and the recorded source build on what the database holds now."""
    fields: dict = {"file_path": new_url, "s3_url": new_url, "updated_at": datetime.now(UTC)}
    # The caller set the new shape on `doc`; the twin's legacy readers (mode
    # recommendation, user_data preview) describe the same file, so it follows (codex).
    fields.update(_shape_of(doc, with_schema=d is doc))
    # Record the object we're moving OFF so erasure can still find it (#525), and keep
    # "the current file is never in superseded": history undo/redo revisit URLs (#629).
    fields["superseded_s3_urls"] = _superseded(fresh.superseded_s3_urls or [], old_url, new_url)
    if isinstance(d, DatasetMetadata) and not getattr(fresh, "source_s3_url", None):
        fields["source_s3_url"] = old_url
    return fields


def _shape_of(doc: Dataset, with_schema: bool) -> dict:
    names = _SHAPE_FIELDS + (("data_schema",) if with_schema else ())
    return {name: value for name in names if (value := getattr(doc, name, None)) is not None}


def _superseded(existing: list[str], old_url: str | None, new_url: str) -> list[str]:
    kept = [u for u in existing if u != new_url]
    if _moved_off(old_url, new_url, kept):
        kept.append(old_url)  # type: ignore[arg-type]  # _moved_off guarantees a str
    return kept


def _moved_off(old_url: str | None, new_url: str, kept: list[str]) -> bool:
    return bool(old_url) and old_url != new_url and old_url not in kept


async def _write(d: Dataset, fields: dict) -> None:
    """One `$set` for a stored document; an unsaved one is inserted whole."""
    if d.id is None:
        for name, value in fields.items():
            setattr(d, name, value)
        await d.save()
        return
    await d.set(fields)


def _log_half_move(moved: list[str], d: Dataset, new_url: str, old_url: str | None) -> None:
    if moved:
        logger.error(
            "Dataset link half-moved: %s already at %s, %s still at %s (user %s) — "
            "run scripts/inventory_dataset_links.py and repair",
            ", ".join(moved), new_url, type(d).__name__, old_url, d.user_id,
        )
