"""
Data utilities for transformation service
"""
import asyncio
import logging

import pandas as pd

from app.services.s3_service import load_dataframe_from_s3
from app.utils.s3 import upload_file_to_s3

logger = logging.getLogger(__name__)


async def get_dataframe_from_s3(s3_url: str, nrows: int | None = None) -> pd.DataFrame:
    """
    Download a file from S3 and load it as a pandas DataFrame

    Args:
        s3_url: S3 URL of the file
        nrows: Number of rows to read (for preview)

    Returns:
        Pandas DataFrame
    """
    try:
        # Centralized download+parse+cleanup (blocking → off the event loop, #265/#280).
        # file_type=None infers csv→parquet; the helper always unlinks the temp file.
        return await asyncio.to_thread(load_dataframe_from_s3, s3_url, None, nrows)
    except Exception as e:
        logger.error(f"Error loading dataframe from S3: {str(e)}")
        raise


async def upload_dataframe_to_s3(df: pd.DataFrame, s3_key: str) -> str:
    """Upload a DataFrame to S3 as parquet and return the object's URL."""
    return await upload_parquet_bytes(df.to_parquet(index=False), s3_key)


async def upload_parquet_bytes(content: bytes, s3_key: str) -> str:
    """Upload already-encoded parquet bytes and return the object's URL.

    For a caller that also needs the stored size (#768's storage ceiling), so the
    frame is encoded once rather than once to upload and again to measure.
    """
    try:
        success, s3_url = upload_file_to_s3(
            file_content=content,
            s3_filename=s3_key,
            content_type='application/octet-stream'
        )
        if not success or s3_url is None:
            raise Exception("Failed to upload dataframe to S3")
        return s3_url
    except Exception as e:
        logger.error(f"Error uploading dataframe to S3: {str(e)}")
        raise