# app/api/routes/column_stats.py

import io
import logging
import os

import pandas as pd
from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.auth.nextauth_auth import get_current_user_id
from app.models.column_stats import ColumnStats
from app.models.user_data import UserData
from app.utils.column_stats import calculate_and_store_column_stats
from app.utils.s3 import create_s3_client, parse_s3_url

router = APIRouter()
logger = logging.getLogger(__name__)


async def _require_owned_dataset(dataset_id: str, user_id: str) -> UserData:
    """Resolve the caller's dataset, or 404 (issue #449).

    Unknown, malformed and foreign ids all answer 404: a 403 would confirm the
    dataset exists, and an unparseable id would otherwise raise out of
    ``PydanticObjectId`` as a 500.

    Call this OUTSIDE the handlers' ``try`` blocks — both catch bare
    ``Exception``, which previously swallowed this refusal into a 500.
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
    column_stats = await ColumnStats.find(
        ColumnStats.dataset_id == PydanticObjectId(dataset_id),
        ColumnStats.user_id == user_id,
    ).to_list()

    # If no stats exist, calculate them
    if not column_stats:
        try:
            # Download the data from S3
            s3_client = create_s3_client()

            # Extract bucket and key from S3 URL (handles all persisted
            # shapes: s3://, presigned amazonaws, endpoint-style)
            bucket, key = parse_s3_url(dataset.s3_url)
            if bucket is None:
                bucket = os.getenv("AWS_BUCKET_NAME")
                logger.debug(
                    "Could not determine bucket from URL %r; falling back to AWS_BUCKET_NAME=%r",
                    dataset.s3_url, bucket,
                )

            # Download the file
            response = s3_client.get_object(Bucket=bucket, Key=key)
            file_content = response["Body"].read()

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

            # Calculate and store column stats
            column_stats = await calculate_and_store_column_stats(
                df, dataset_id, user_id
            )

            # Only once fresh rows exist: drop unservable legacy rows for this
            # dataset. Rows written before #449 carry no user_id, so the scoped
            # read above can never return them and they would otherwise pile up
            # on every recompute. Deliberately after the recompute, not before —
            # deleting first would destroy them for good if the S3 download or
            # parse failed, and every later request would recompute from nothing.
            # Scoped to a dataset whose ownership is already established and to
            # null-owner rows only, so a real row is never touched. Note this is
            # a no-op against production data until #543 lands: `dataset_id` is
            # persisted as a DBRef, which this bare-ObjectId query does not match.
            await ColumnStats.find(
                ColumnStats.dataset_id == PydanticObjectId(dataset_id),
                ColumnStats.user_id == None,  # noqa: E711 — Beanie needs ==, not `is`
            ).delete()

        except HTTPException:
            raise
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
        # Delete existing column stats. Intentionally NOT scoped by user_id,
        # unlike the read in get_column_stats: ownership of this dataset is
        # already established above, and a recalculate should also clear any
        # stray or legacy rows sitting under it. (Also a no-op against
        # production data until #543 — see the note in get_column_stats.)
        await ColumnStats.find(
            ColumnStats.dataset_id == PydanticObjectId(dataset_id)
        ).delete()

        # Download the data from S3
        s3_client = create_s3_client()

        # Extract bucket and key from S3 URL (handles all persisted
        # shapes: s3://, presigned amazonaws, endpoint-style)
        bucket, key = parse_s3_url(dataset.s3_url)
        if bucket is None:
            bucket = os.getenv("AWS_BUCKET_NAME")
            logger.debug(
                "Could not determine bucket from URL %r; falling back to AWS_BUCKET_NAME=%r",
                dataset.s3_url, bucket,
            )

        # Download the file
        response = s3_client.get_object(Bucket=bucket, Key=key)
        file_content = response["Body"].read()

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

        # Calculate and store column stats
        await calculate_and_store_column_stats(df, dataset_id, user_id)

        return {"message": "Column statistics recalculated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recalculating column stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error recalculating column stats: {str(e)}"
        )
