# app/api/routes/column_stats.py

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from beanie import PydanticObjectId
from app.models.column_stats import ColumnStats
from app.auth.clerk_auth import get_current_user_id
import pandas as pd
import io
import boto3
import os
import logging

from app.utils.column_stats import calculate_and_store_column_stats

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/dataset/{dataset_id}", response_model=List[ColumnStats])
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
    # Get column stats from database
    column_stats = await ColumnStats.find(
        ColumnStats.dataset_id == PydanticObjectId(dataset_id)
    ).to_list()

    # If no stats exist, calculate them
    if not column_stats:
        try:
            # Get the dataset
            from shared.models.user_data import UserData

            dataset = await UserData.get(dataset_id)

            if not dataset:
                raise HTTPException(status_code=404, detail="Dataset not found")

            # Verify the user owns the dataset
            if dataset.user_id != user_id:
                raise HTTPException(
                    status_code=403, detail="Not authorized to access this dataset"
                )

            # Download the data from S3
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1"),
            )

            # Extract bucket and key from S3 URL
            s3_url = dataset.s3_url
            if s3_url.startswith("http"):
                # This is a signed URL, we need to get the actual S3 path
                # For now, we'll use a placeholder
                bucket = os.getenv("AWS_BUCKET_NAME")
                key = f"user_data/{user_id}/{dataset.filename}"
            else:
                # This is a direct S3 path
                parts = s3_url.replace("s3://", "").split("/", 1)
                bucket = parts[0]
                key = parts[1]

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
                except:
                    raise HTTPException(
                        status_code=400,
                        detail="Unsupported file format. Please upload a CSV or Excel file.",
                    )

            # Calculate and store column stats
            column_stats = await calculate_and_store_column_stats(
                df, dataset_id, user_id
            )

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
    try:
        # Get the dataset
        from shared.models.user_data import UserData

        dataset = await UserData.get(dataset_id)

        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Verify the user owns the dataset
        if dataset.user_id != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this dataset"
            )

        # Delete existing column stats
        await ColumnStats.find(
            ColumnStats.dataset_id == PydanticObjectId(dataset_id)
        ).delete()

        # Download the data from S3
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )

        # Extract bucket and key from S3 URL
        s3_url = dataset.s3_url
        if s3_url.startswith("http"):
            # This is a signed URL, we need to get the actual S3 path
            # For now, we'll use a placeholder
            bucket = os.getenv("AWS_BUCKET_NAME")
            key = f"user_data/{user_id}/{dataset.filename}"
        else:
            # This is a direct S3 path
            parts = s3_url.replace("s3://", "").split("/", 1)
            bucket = parts[0]
            key = parts[1]

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
            except:
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported file format. Please upload a CSV or Excel file.",
                )

        # Calculate and store column stats
        await calculate_and_store_column_stats(df, dataset_id, user_id)

        return {"message": "Column statistics recalculated successfully"}

    except Exception as e:
        logger.error(f"Error recalculating column stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error recalculating column stats: {str(e)}"
        )
