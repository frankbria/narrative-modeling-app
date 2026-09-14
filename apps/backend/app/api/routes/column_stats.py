# app/api/routes/column_stats.py

import io
import logging

import pandas as pd
from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import BulkWriteError, DuplicateKeyError

from app.auth.nextauth_auth import get_current_user_id
from app.models.column_stats import ColumnStats
from app.models.user_data import UserData
from app.utils.column_stats import calculate_and_store_column_stats
from app.utils.s3 import get_file_from_s3

router = APIRouter()
logger = logging.getLogger(__name__)


def _ref_filter(dataset_id: str) -> dict:
    """Match ColumnStats rows by their stored DBRef ``dataset_id`` (#543).

    ``dataset_id`` is a Beanie ``Link``, persisted as a DBRef (``{$ref, $id}``); a bare
    ``dataset_id == ObjectId`` equality never matched it — so the cache never hit, stats
    were re-inserted on every GET, and ``recalculate``'s delete cleared nothing. Query the
    DBRef's ``$id`` (exactly how the erasure cascade deletes Link-keyed children).
    """
    return {"dataset_id.$id": PydanticObjectId(dataset_id)}


def _dedupe_by_column(rows: list[ColumnStats]) -> list[ColumnStats]:
    """Return one row per column_name, keeping the FIRST seen — callers pass a query
    sorted newest-first (``-_id``), so a pre-#543 duplicate set yields the freshest row,
    never a stale one. Defensive until the operator runs scripts/dedupe_column_stats.py
    and the unique index binds."""
    seen: set[str] = set()
    out: list[ColumnStats] = []
    for r in rows:
        if r.column_name not in seen:
            seen.add(r.column_name)
            out.append(r)
    return out


async def _read_scoped_stats(dataset_id: str, user_id: str) -> list[ColumnStats]:
    """The caller's cached rows for a dataset, newest-first and deduped by column."""
    return _dedupe_by_column(
        await ColumnStats.find(
            _ref_filter(dataset_id),
            ColumnStats.user_id == user_id,
        )
        .sort("-_id")  # newest first, so _dedupe_by_column keeps the freshest of any pre-#543 dupes
        .to_list()
    )


async def _require_owned_dataset(dataset_id: str, user_id: str) -> UserData:
    """Resolve the caller's dataset, or 404 (issue #449).

    Unknown, malformed and foreign ids all answer 404: a 403 would confirm the
    dataset exists, and an unparseable id would otherwise raise out of
    ``PydanticObjectId`` as a 500.

    Call this OUTSIDE the handlers' ``try`` blocks — both catch bare
    ``Exception``, which previously swallowed this refusal into a 500.

    A consequence of sitting outside those blocks: an unexpected failure from
    ``UserData.get`` no longer picks up the handlers' own ``logger.error``
    context and is left to the central 5xx handler in
    ``app/middleware/error_handlers.py``, which logs it with a request id.
    That is the project's convention (#269), and it is the right trade for not
    having the ownership refusal swallowed.
    """
    if not PydanticObjectId.is_valid(dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found")

    dataset = await UserData.get(dataset_id)
    if not dataset or dataset.user_id != user_id:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.get("/dataset/{dataset_id}", response_model=list[ColumnStats])
async def get_column_stats(
    dataset_id: str, user_id: str = Depends(get_current_user_id)
):
    """
    Get column statistics for a dataset.

    Args:
        dataset_id: The ID of the dataset
        user_id: The ID of the user who owns the dataset

    Returns:
        List of ColumnStats objects
    """
    # Ownership is checked BEFORE the cache is read. It used to live inside the
    # `if not column_stats:` branch below, so a cache hit returned another
    # tenant's distributions and sample values unchecked (issue #449).
    dataset = await _require_owned_dataset(dataset_id, user_id)

    # Get column stats from database, scoped to the caller. The owner predicate
    # is deliberately redundant with the check above (AC2): a stray foreign row
    # under this dataset_id must not be served even if that check is refactored.
    column_stats = await _read_scoped_stats(dataset_id, user_id)

    # If no stats exist, calculate them
    if not column_stats:
        try:
            # Download through the one validated reader (#531): bucket allowlist,
            # traversal and namespace checks, size cap.
            file_content = get_file_from_s3(dataset.s3_url).getvalue()

            # Read the data into a pandas DataFrame
            if dataset.filename.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(file_content))
            elif dataset.filename.endswith(".xlsx") or dataset.filename.endswith(
                ".xls"
            ):
                df = pd.read_excel(io.BytesIO(file_content))
            else:
                # Try to read as CSV with different settings
                try:
                    df = pd.read_csv(
                        io.BytesIO(file_content), sep=None, engine="python"
                    )
                except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, UnicodeDecodeError) as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unsupported file format or parsing error: {str(e)}. Please upload a valid CSV or Excel file.",
                    )

            # Drop unservable legacy rows for this dataset BEFORE recomputing.
            # Rows written before #449 carry no user_id, so the scoped read
            # above can never return them. Ordering is load-bearing twice over:
            #  - after the S3 download+parse (above), never before — deleting
            #    first would destroy the cached rows for good if the download or
            #    parse failed, leaving every later request to recompute from
            #    nothing.
            #  - before calculate_and_store_column_stats' insert_many (below) —
            #    the dataset_column_unique index (#543) keys on
            #    (dataset_id, column_name) WITHOUT user_id, so a surviving
            #    null-owner row for an existing column would DuplicateKeyError
            #    the owner-stamped insert and block the self-healing recompute.
            # Scoped to this (already-owned) dataset and to null-owner rows
            # only, so a real row is never touched. Matches the DBRef via
            # _ref_filter. NOT best-effort any more: with the unique index the
            # insert depends on this delete, so a failure here must surface
            # rather than be swallowed and then fail confusingly at insert.
            await ColumnStats.find(
                _ref_filter(dataset_id),
                ColumnStats.user_id == None,  # noqa: E711 — Beanie needs ==, not `is`
            ).delete()

            # Calculate and store column stats
            column_stats = await calculate_and_store_column_stats(
                df, dataset_id, user_id
            )

        except HTTPException:
            raise
        except (BulkWriteError, DuplicateKeyError):
            # Lost a concurrent recompute race: another request missed the cache
            # for this same dataset and inserted first, so this insert collided
            # on the dataset_column_unique index (#543). The winner's rows are
            # correct and complete — an ordered insert_many stops at the first
            # duplicate, so this loser wrote nothing partial — so just serve
            # them, rather than 500-ing on what is really a cache hit.
            column_stats = await _read_scoped_stats(dataset_id, user_id)
        except Exception as e:
            logger.error(f"Error calculating column stats: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error calculating column stats: {str(e)}"
            )

    return column_stats


@router.post("/dataset/{dataset_id}/recalculate")
async def recalculate_column_stats(
    dataset_id: str, user_id: str = Depends(get_current_user_id)
):
    """
    Recalculate column statistics for a dataset.

    Args:
        dataset_id: The ID of the dataset
        user_id: The ID of the user who owns the dataset

    Returns:
        Success message
    """
    dataset = await _require_owned_dataset(dataset_id, user_id)

    try:
        # Download through the one validated reader (#531): bucket allowlist,
        # traversal and namespace checks, size cap.
        file_content = get_file_from_s3(dataset.s3_url).getvalue()

        # Read the data into a pandas DataFrame
        if dataset.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_content))
        elif dataset.filename.endswith(".xlsx") or dataset.filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            # Try to read as CSV with different settings
            try:
                df = pd.read_csv(io.BytesIO(file_content), sep=None, engine="python")
            except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, UnicodeDecodeError) as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format or parsing error: {str(e)}. Please upload a valid CSV or Excel file.",
                )

        # Replace the existing rows only now that the new content is parsed and
        # in hand. Deleting before the S3 download (where this used to sit) meant
        # a failed download or parse wiped the caller's good cached stats and
        # left nothing behind — the same hazard fixed in get_column_stats, which
        # this handler was missing one function away.
        #
        # Intentionally NOT scoped by user_id, unlike the read in
        # get_column_stats: ownership of this dataset is already established
        # above, and a recalculate should also clear stray or legacy rows under
        # it. Matches the stored DBRef via _ref_filter (#543).
        await ColumnStats.find(_ref_filter(dataset_id)).delete()

        # Calculate and store column stats
        await calculate_and_store_column_stats(df, dataset_id, user_id)

        return {"message": "Column statistics recalculated successfully"}

    except HTTPException:
        raise
    except (BulkWriteError, DuplicateKeyError):
        # A concurrent recompute (another recalculate, or a GET cache-miss) won
        # the race and wrote fresh rows under the dataset_column_unique index
        # (#543) before this insert; the data is already recalculated, so report
        # success rather than 500 on the collision.
        return {"message": "Column statistics recalculated successfully"}
    except Exception as e:
        logger.error(f"Error recalculating column stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error recalculating column stats: {str(e)}"
        )
