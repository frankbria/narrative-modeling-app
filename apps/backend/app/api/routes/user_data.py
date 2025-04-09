# backend/app/api/routes/user_data.py

from fastapi import APIRouter, HTTPException, Depends
from beanie import PydanticObjectId
from typing import List, Dict, Any
from app.models.user_data import UserData
from app.auth.clerk_auth import get_current_user_id
import pandas as pd
import io
import boto3
import os

router = APIRouter()


@router.post("/", response_model=UserData)
async def create_user_data(
    user_data: UserData, user_id: str = Depends(get_current_user_id)
):
    user_data.user_id = user_id
    await user_data.insert()
    return user_data


@router.get("/", response_model=List[UserData])
async def get_user_data_for_user(user_id: str = Depends(get_current_user_id)):
    return await UserData.find(UserData.user_id == user_id).to_list()


@router.get("/{id}", response_model=UserData)
async def get_user_data(
    id: PydanticObjectId, user_id: str = Depends(get_current_user_id)
):
    doc = await UserData.get(id)
    if not doc or doc.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return doc


@router.get("/preview/{user_id}", response_model=Dict[str, Any])
async def get_preview_data(user_id: str = Depends(get_current_user_id)):
    """
    Get the most recent uploaded file's preview data for a user.
    """
    try:
        # Get the most recent user data document
        user_data = (
            await UserData.find(UserData.user_id == user_id)
            .sort(-UserData.created_at)
            .first_or_none()
        )

        if not user_data:
            raise HTTPException(status_code=404, detail="No data found for user")

        # Initialize S3 client
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )

        # Extract the key from the S3 URL
        s3_url = user_data.s3_url
        print(f"Original S3 URL: {s3_url}")

        # Handle different S3 URL formats
        if "?" in s3_url:
            # URL with query parameters
            s3_key = s3_url.split("?")[0].split("/")[-1]
        else:
            # Simple URL
            s3_key = s3_url.split("/")[-1]

        print(f"Extracted S3 key: {s3_key}")
        print(f"Attempting to get S3 object with key: {s3_key}")

        # Get the file from S3
        try:
            response = s3_client.get_object(
                Bucket=os.getenv("AWS_BUCKET_NAME"),
                Key=s3_key,
            )
        except Exception as e:
            print(f"Error getting S3 object: {e}")
            # If we can't get the file from S3, return the metadata without preview data
            return {
                "headers": [],
                "previewData": [],
                "fileName": user_data.filename,
                "fileType": "text/csv",  # Default to CSV for now
                "id": str(user_data.id),
                "s3_url": user_data.s3_url,
                "schema": user_data.data_schema,
                "error": f"Could not retrieve file from S3: {str(e)}",
                "num_rows": user_data.num_rows,
                "num_columns": user_data.num_columns,
                "created_at": (
                    user_data.created_at.isoformat() if user_data.created_at else None
                ),
                "updated_at": (
                    user_data.updated_at.isoformat() if user_data.updated_at else None
                ),
            }

        # Read the file content
        file_content = response["Body"].read()

        # Determine file type and read accordingly
        if user_data.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_content))
        elif user_data.filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(file_content))
        elif user_data.filename.endswith(".txt"):
            df = pd.read_csv(io.BytesIO(file_content), sep="\t")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        # Get preview data
        preview_data = df.head(10).values.tolist()
        headers = df.columns.tolist()

        return {
            "headers": headers,
            "previewData": preview_data,
            "fileName": user_data.filename,
            "fileType": "text/csv",  # Default to CSV for now
            "id": str(user_data.id),
            "s3_url": user_data.s3_url,
            "schema": user_data.data_schema,
            "num_rows": user_data.num_rows,
            "num_columns": user_data.num_columns,
            "created_at": (
                user_data.created_at.isoformat() if user_data.created_at else None
            ),
            "updated_at": (
                user_data.updated_at.isoformat() if user_data.updated_at else None
            ),
        }

    except Exception as e:
        print(f"Error in get_preview_data: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting preview data: {str(e)}"
        )


@router.put("/{id}", response_model=UserData)
async def update_user_data(
    id: PydanticObjectId, updated: UserData, user_id: str = Depends(get_current_user_id)
):
    doc = await UserData.get(id)
    if not doc or doc.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    updated.id = id
    updated.user_id = user_id  # ensure this isn't overwritten
    await updated.save()
    return updated


@router.delete("/{id}")
async def delete_user_data(
    id: PydanticObjectId, user_id: str = Depends(get_current_user_id)
):
    doc = await UserData.get(id)
    if not doc or doc.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await doc.delete()
    return {"success": True}
