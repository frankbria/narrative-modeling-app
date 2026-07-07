"""
Data utilities for transformation service
"""
import asyncio
import logging
import os
import tempfile

import pandas as pd

from app.services.s3_service import download_file_from_s3
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
        # Download file from S3 (blocking boto3 — keep it off the event loop, #265)
        temp_file_path = await asyncio.to_thread(download_file_from_s3, s3_url)
        
        # Determine file type and read accordingly
        if temp_file_path.endswith('.parquet'):
            if nrows:
                # For parquet preview, read all then take head
                df = pd.read_parquet(temp_file_path)
                df = df.head(nrows)
            else:
                df = pd.read_parquet(temp_file_path)
        elif temp_file_path.endswith('.csv'):
            df = pd.read_csv(temp_file_path, nrows=nrows)
        elif temp_file_path.endswith('.xlsx') or temp_file_path.endswith('.xls'):
            df = pd.read_excel(temp_file_path, nrows=nrows)
        else:
            # Try to infer format
            try:
                df = pd.read_csv(temp_file_path, nrows=nrows)
            except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, UnicodeDecodeError):
                df = pd.read_parquet(temp_file_path)
                if nrows:
                    df = df.head(nrows)
        
        # Clean up temp file
        os.unlink(temp_file_path)
        
        return df
        
    except Exception as e:
        logger.error(f"Error loading dataframe from S3: {str(e)}")
        raise


async def upload_dataframe_to_s3(df: pd.DataFrame, s3_key: str) -> str:
    """
    Upload a pandas DataFrame to S3
    
    Args:
        df: DataFrame to upload
        s3_key: S3 key for the file
    
    Returns:
        S3 URL of uploaded file
    """
    try:
        # Save dataframe to temporary file
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_file:
            df.to_parquet(tmp_file.name, index=False)
            temp_path = tmp_file.name
        
        # Upload to S3
        with open(temp_path, 'rb') as file:
            file_content = file.read()
            success, s3_url = upload_file_to_s3(
                file_content=file_content,
                s3_filename=s3_key,
                content_type='application/octet-stream'
            )

        # Clean up temp file
        os.unlink(temp_path)

        if not success or s3_url is None:
            raise Exception("Failed to upload dataframe to S3")

        return s3_url
        
    except Exception as e:
        logger.error(f"Error uploading dataframe to S3: {str(e)}")
        raise