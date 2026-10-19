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
import asyncio
import contextlib
import functools
import inspect
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.models.column_stats import ColumnStats
from app.models.dataset import DatasetMetadata
from app.models.transformation import TransformationConfig
from app.models.user_data import UserData
from app.models.visualization_cache import VisualizationCache
from app.services.dataset_lease import LeaseBusy, dataset_lease
from app.services.exceptions import NotFoundError
from app.services.redis_cache import cache_service
from app.utils.s3 import object_size

logger = logging.getLogger(__name__)


_KNOWN_TYPES = {"parquet", "csv", "json", "xlsx", "xls"}


def file_type_of(url: str) -> str | None:
    """The stored `file_type` value for a location, from its extension; None if unknown."""
    path = url.split("?", 1)[0]
    # A masked copy is CSV whatever its name says: until #937 it kept the upload's extension.
    if path.rsplit("/", 1)[-1].startswith("masked_"):
        return "csv"
    ext = path.rsplit(".", 1)[-1].lower()
    return ext if ext in _KNOWN_TYPES else None


# What the caller may have changed on the document for the new file (#723: these and the
# link fields are the only ones the move writes). The twin gets the same shape, not the schema.
_SHAPE_FIELDS = ("num_rows", "num_columns", "columns", "file_type", "file_size")

Dataset = DatasetMetadata | UserData


async def record_new_file(doc: Dataset, new_url: str, *, in_history: bool = False) -> None:
    """Point `doc` AND its dual-written twin at `new_url` (a full, downloadable URL).

    `in_history` is for the two callers the transformation history itself drives: the
    apply that records a step for this move, and undo/redo. Every other move is an edit
    no step describes, so the history is closed behind it (`_close_history`, #851).
    The default is the safe one: a writer that says nothing cannot be undone past.

    The twin is found through the *old* `(user_id, s3_url)` before either changes. A
    dataset with no twin (only one side was ever written) moves alone. The original
    upload is kept in `DatasetMetadata.source_s3_url` the first time.

    Each document gets one targeted `$set` of the fields the move owns, never a
    full-document save: a save of the caller's in-memory snapshot reverted whatever
    another writer had changed since it was loaded (#723, the class #520 fixed).
    """
    # Every writer uploads the transformed frame as parquet, so a dataset uploaded as CSV
    # would otherwise be parsed as CSV by readers that dispatch on file_type (#524, codex).
    file_type = file_type_of(new_url) or doc.file_type
    # What the storage ceiling sums (#781): the size of the file the dataset is on now,
    # not of the upload it started from. Asked of S3 here, so every writer that moves a
    # dataset is covered, undo and redo included; unreadable, the recorded size stays.
    file_size = await asyncio.to_thread(object_size, new_url)
    # Look the twin up at the dataset's CURRENT stored location, not the one this
    # in-memory `doc` was loaded with: two overlapping transformations each load the
    # dataset, the first moves both twins, and the second would otherwise search the
    # stale URL, find nothing, and move its own side alone — re-severing the link (codex).
    current = await _stored(doc)
    old_url = _current_url(current, doc)
    twin = await _find_twin(doc, old_url)
    doc.file_type = file_type
    if file_size is not None:
        doc.file_size = file_size
    docs = _erasure_order(doc, twin)
    await _move_all(docs, doc, current, old_url, new_url)
    await _forget_what_was_computed(docs)
    if not in_history:
        await _close_history(docs)


async def _forget_what_was_computed(docs: list[Dataset]) -> None:
    """Drop everything cached from the file the dataset has just left (#960).

    The chart caches (Redis, and the `VisualizationCache` rows, which never expire) and
    the column statistics are keyed by the upload's id and say nothing about which file
    they were computed from, so after a move they kept answering with the old data.
    Every writer that moves a dataset comes through `record_new_file`, which makes this
    the one place to clear them.

    Best effort: the move has already happened. An entry that could not be cleared is
    logged, never raised into a transformation that succeeded.
    """
    for upload in docs:
        if not isinstance(upload, UserData):
            continue
        try:
            await VisualizationCache.find({"dataset_id.$id": upload.id}).delete()
            await ColumnStats.find({"dataset_id.$id": upload.id}).delete()
            await cache_service.delete_pattern(f"viz:{upload.id}:*")
        except Exception:
            logger.exception("Could not clear what was computed from dataset %s before it moved", upload.id)


def _history_id(d: Dataset) -> str:
    """The id a transformation request names the dataset by: its own, in either id space."""
    return d.dataset_id if isinstance(d, DatasetMetadata) else str(d.id)


async def _close_history(docs: list[Dataset]) -> None:
    """Make every step up to now unrestorable, and drop the redo tail (#851).

    The dataset has just been changed by an edit the history holds no step for. Undo
    restores a step's saved version, so going back to the current step or any earlier
    one would silently discard that edit; a step recorded later can still be undone,
    down to the first one recorded after it. One pipeline update on the stored
    document, so it cannot revert a step another request is recording.

    A second write, after the move: if it fails the caller's request fails with the
    dataset already moved and the history still open, which is the state every such
    move left before #851. No transaction spans the two collections.
    """
    kept = {"$max": [{"$add": ["$current_position", 1]}, 0]}
    # At the start (before the first step: reachable since #962 by undoing it) no step
    # describes the edited file, so none is kept, and the version recorded for "before
    # the first step" is no longer where the dataset is. `$slice` cannot take zero.
    at_the_start = {"$eq": [kept, 0]}
    await TransformationConfig.get_motor_collection().update_many(
        {"user_id": docs[0].user_id, "dataset_id": {"$in": [_history_id(d) for d in docs]}},
        [
            {"$set": {
                "undo_floor": kept,
                "transformation_steps": {
                    "$cond": [at_the_start, [], {"$slice": ["$transformation_steps", 0, {"$max": [kept, 1]}]}]
                },
                "base_version_id": {"$cond": [at_the_start, None, "$base_version_id"]},
            }},
            {"$set": {"total_transformations": {"$size": "$transformation_steps"}}},
        ],
    )


async def close_history(doc: Dataset) -> None:
    """Close the history of `doc` and its twin behind the file they are on now (#1060):
    for a move whose steps could not be recorded after it."""
    await _close_history(_erasure_order(doc, await _find_twin(doc, doc.s3_url)))


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


async def ensure_metadata_twin(dataset_id: str, user_id: str) -> DatasetMetadata | None:
    """The `DatasetMetadata` a transformation runs on, for either id space (#850).

    The UI uploads through `/upload/secure` and chunked `complete`, which write only a
    `UserData` row, and hands its ObjectId to the Prepare stage. The transformation
    service and its history are keyed on `DatasetMetadata`, so every transformation on a
    UI upload answered 404. An id that names the caller's `UserData` resolves to its
    twin (joined on `(user_id, s3_url)`), created with a base version on first use.
    None when the caller owns neither.
    """
    meta = await DatasetMetadata.find_one({"dataset_id": dataset_id, "user_id": user_id})
    if meta:
        return meta
    upload = await _owned_upload(dataset_id, user_id)
    if upload is None:
        return None
    twin = await _twin_of(upload)
    if twin:
        return twin
    # Two first requests for one upload both found no twin and both made one (#853).
    # One at a time, and look again once it is our turn.
    async with dataset_lease(f"twin:{user_id}:{upload.id}"):
        return await _twin_of(upload) or await _create_twin(upload)


async def _twin_of(upload: UserData) -> DatasetMetadata | None:
    return await DatasetMetadata.find_one(
        DatasetMetadata.user_id == upload.user_id, DatasetMetadata.s3_url == upload.s3_url
    )


async def owns_dataset(dataset_id: str, user_id: str) -> bool:
    """Whether the caller owns a dataset of this id, in either id space (#847).

    Read-only: a caller that only needs to know must not create a twin. Someone
    else's dataset and one that does not exist are the same answer.
    """
    if await DatasetMetadata.find_one({"dataset_id": dataset_id, "user_id": user_id}):
        return True
    return await _owned_upload(dataset_id, user_id) is not None


async def history_key(dataset_id: str, user_id: str) -> str:
    """The id a dataset's history is kept under, whichever id the request named it by (#851).

    That is its `DatasetMetadata` id. Read-only, unlike `ensure_metadata_twin`: reading a
    history must not create a twin. An id that names no upload comes back as it is.
    """
    upload = await _owned_upload(dataset_id, user_id)
    if upload is None:
        return dataset_id
    twin = await DatasetMetadata.find_one(
        DatasetMetadata.user_id == user_id, DatasetMetadata.s3_url == upload.s3_url
    )
    return twin.dataset_id if twin else dataset_id


#: What a writer that could not take the dataset's lease reports, in its own shape.
DATASET_BUSY = "Another change to this dataset is still being applied. Try again in a moment."


@contextlib.asynccontextmanager
async def holding_the_dataset(dataset_id: str, user_id: str) -> AsyncIterator[None]:
    """The dataset's apply lease (#853), for every writer that moves it to a new file
    (#1022): an apply, an undo, redo or jump, a data-issue fix, a feature
    added in place. Held for the whole read-modify-write, so a writer reads the file the
    one before it left. Keyed by `history_key`, so both id spaces take the same lease.

    Raises:
        LeaseBusy: another writer still held it when the wait ran out. The caller
            reports `DATASET_BUSY` in its own failure shape and writes nothing.
    """
    async with dataset_lease(f"apply:{user_id}:{await history_key(dataset_id, user_id)}"):
        yield


def holds_the_dataset(
    dataset_id_of: Callable[[dict[str, Any]], str | None], busy: Callable[[dict[str, Any]], Any]
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """For a route that moves a dataset: run the handler holding the dataset's lease
    (#1022), so it reads the file the last writer left. `dataset_id_of(arguments)` names the
    dataset from the handler's arguments by name; `busy(arguments)` is the route's own failure answer
    when the lease is still held after the wait, and nothing has been written then.
    A request that moves nothing (a preview) names no dataset (`None`) and takes no lease.
    Place it directly above the handler, under the other decorators.
    """

    def wrap(handler: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        signature = inspect.signature(handler)
        if "current_user_id" not in signature.parameters:
            raise TypeError(f"{handler.__name__} takes no current_user_id, so its lease cannot be named")

        @functools.wraps(handler)
        async def run(*args: Any, **kwargs: Any) -> Any:
            # By name, however the handler was called: FastAPI passes keywords, a test
            # calling the handler directly may not.
            named = signature.bind_partial(*args, **kwargs).arguments
            dataset_id = dataset_id_of(named)
            if dataset_id is None:
                return await handler(*args, **kwargs)
            try:
                async with holding_the_dataset(dataset_id, named["current_user_id"]):
                    return await handler(*args, **kwargs)
            except LeaseBusy:
                return busy(named)

        return run

    return wrap


async def _owned_upload(dataset_id: str, user_id: str) -> UserData | None:
    if not ObjectId.is_valid(dataset_id):
        return None
    return await UserData.find_one(UserData.id == ObjectId(dataset_id), UserData.user_id == user_id)


async def _create_twin(upload: UserData) -> DatasetMetadata:
    """The upload's metadata twin, keyed by the upload's own id so the id the UI holds
    resolves directly from now on."""
    twin = await DatasetMetadata(
        user_id=upload.user_id,
        dataset_id=str(upload.id),
        filename=upload.filename,
        original_filename=upload.original_filename,
        file_type=_twin_file_type(upload),
        file_path=upload.file_path or upload.s3_url,
        s3_url=upload.s3_url,
        file_size=upload.file_size,
        num_rows=upload.num_rows,
        num_columns=upload.num_columns,
        columns=list(upload.columns or []),
    ).insert()
    # No base version here: the first apply writes it from the frame it transforms
    # (TransformationService._version_for), which also heals a failed write later.
    return twin




# What the transformation reader parses safely. It goes by the file's bytes (#858), which
# tell CSV, Excel, JSON and Parquet apart; a TSV still reads as one junk column.
_TRANSFORMABLE = {"csv", "parquet", "json", "xlsx", "xls"}


def _twin_file_type(upload: UserData) -> str:
    """The upload's file type, if a transformation can read it.

    An apply on a misread frame overwrites the live file on both twins (#857 review: a
    TSV typed "csv" collapsed into one column), so anything else is refused with its
    type named. A row stored as "excel" before #902 reads as its extension through the
    model; the URL's extension is still consulted for a type the model does not rewrite.
    """
    kind = _transformable_kind(upload)
    if kind is None:
        raise _not_transformable(upload)
    return kind


def _transformable_kind(upload: UserData) -> str | None:
    for candidate in ((upload.file_type or "").lower(), file_type_of(upload.s3_url)):
        if candidate in _TRANSFORMABLE:
            return candidate
    return None


def _not_transformable(upload: UserData) -> NotFoundError:
    kind = upload.file_type or file_type_of(upload.s3_url) or "of an unknown type"
    return NotFoundError(
        resource_type="Dataset",
        resource_id=str(upload.id),
        message=f"Transformations support CSV, Excel, JSON and Parquet files; this upload is {kind}. "
        "Re-upload it as CSV to transform it.",
    )
