# backend/app/api/routes/user_data.py

import io
import logging
import os
from typing import Any

import pandas as pd
from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData, get_current_time
from app.schemas.user_data import UserDataResponse, UserDataUpdate
from app.services.eda_summary import generate_eda_summary
from app.utils.s3 import create_s3_client, parse_s3_url

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", status_code=410)
async def create_user_data_gone() -> None:
    """Retired (issue #451).

    This route took the `UserData` document as its request body, so a client
    chose every field — including `s3_url`, which the visualization and preview
    endpoints fetch. Registering a metadata row against a caller-named S3 object
    was the endpoint's whole purpose, so there is no version of it that both
    works as designed and is safe. Datasets are created by uploading them, which
    derives the storage location server-side.
    """
    raise HTTPException(
        status_code=410,
        detail=(
            "Create datasets with POST /api/v1/upload. This route accepted a "
            "client-supplied s3_url and has been retired."
        ),
    )


@router.get("/", response_model=list[UserDataResponse])
async def get_user_data_for_user(user_id: str = Depends(get_current_user_id)) -> list[UserDataResponse]:
    user_data_list = await UserData.find(UserData.user_id == user_id).to_list()
    # Convert to response models with proper ID handling
    response_list = []
    for doc in user_data_list:
        doc_dict = doc.model_dump(by_alias=True)
        if '_id' in doc_dict and hasattr(doc_dict['_id'], '__str__'):
            doc_dict['_id'] = str(doc_dict['_id'])
        response_list.append(UserDataResponse.model_validate(doc_dict))
    return response_list


@router.get("/latest", response_model=UserDataResponse)
async def get_latest_user_data(user_id: str = Depends(get_current_user_id)) -> UserDataResponse:
    """
    Get the most recent dataset for the current user.
    """
    try:
        # Get the most recent user data document
        user_data = (
            await UserData.find(UserData.user_id == user_id)
            .sort("-created_at")
            .first_or_none()
        )

        if not user_data:
            raise HTTPException(status_code=404, detail="No data found for user")

        # Convert to response model with proper ID handling
        doc_dict = user_data.model_dump(by_alias=True)
        if '_id' in doc_dict and hasattr(doc_dict['_id'], '__str__'):
            doc_dict['_id'] = str(doc_dict['_id'])
        return UserDataResponse.model_validate(doc_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest user data: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error getting latest user data: {str(e)}"
        )

@router.get("/preview", response_model=dict[str, Any])
async def get_preview_data(user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    """
    Get the most recent uploaded file's preview data for a user.
    """
    try:
        # Get the most recent user data document
        user_data = (
            await UserData.find(UserData.user_id == user_id)
            .sort("-created_at")
            .first_or_none()
        )

        if not user_data:
            raise HTTPException(status_code=404, detail="No data found for user")

        # Initialize S3 client
        s3_client = create_s3_client()

        # Extract the key from the S3 URL (handles all persisted URL shapes).
        # Upload persists placeholders like "s3_not_configured" when S3 is
        # unavailable — return metadata without preview for those instead of
        # erroring, matching the S3-failure fallback below.
        s3_url = user_data.s3_url
        try:
            _, s3_key = parse_s3_url(s3_url)
        except ValueError:
            logger.warning(f"No object key in stored S3 URL for dataset {user_data.id}")
            return {
                "headers": [],
                "previewData": [],
                "fileName": user_data.filename,
                "fileType": "text/csv",  # Default to CSV for now
                "id": str(user_data.id),
                "s3_url": user_data.s3_url,
                "schema": user_data.data_schema,
                "error": "File is not available in storage",
                "num_rows": user_data.num_rows,
                "num_columns": user_data.num_columns,
                "created_at": (
                    user_data.created_at.isoformat() if user_data.created_at else None
                ),
                "updated_at": (
                    user_data.updated_at.isoformat() if user_data.updated_at else None
                ),
            }

        logger.debug(f"Fetching S3 object for preview: {s3_key}")

        # Get the file from S3
        try:
            response = s3_client.get_object(
                Bucket=os.getenv("AWS_BUCKET_NAME"),
                Key=s3_key,
            )
        except Exception as e:
            logger.error(f"Error getting S3 object {s3_key}: {e}")
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_preview_data: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting preview data: {str(e)}"
        )


@router.get("/{id}", response_model=UserDataResponse)
async def get_user_data(
    id: str, user_id: str = Depends(get_current_user_id)
) -> UserDataResponse:
    try:
        logger.info(f"Fetching user data - ID: {id}, User: {user_id}")
        
        # Convert string ID to PydanticObjectId
        try:
            object_id = PydanticObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ObjectId format: {id} - {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid dataset ID format: {id}")
            
        doc = await UserData.get(object_id)
        
        if not doc:
            logger.error(f"Document not found for ID: {id}")
            raise HTTPException(status_code=404, detail="Dataset not found")
            
        # 404, not 403: a 403 here confirms the dataset exists and belongs to
        # someone else. Matches the PUT below (issue #451).
        if doc.user_id != user_id:
            logger.warning(f"Access denied - Doc user: {doc.user_id}, Request user: {user_id}")
            raise HTTPException(status_code=404, detail="Dataset not found")
            
        # Convert to response model with proper ID handling
        doc_dict = doc.model_dump(by_alias=True)
        # Ensure _id is converted to string
        if '_id' in doc_dict and hasattr(doc_dict['_id'], '__str__'):
            doc_dict['_id'] = str(doc_dict['_id'])
        return UserDataResponse.model_validate(doc_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting user data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving dataset: {str(e)}")



@router.put("/{id}", response_model=UserData)
async def update_user_data(
    id: PydanticObjectId,
    updated: UserDataUpdate,
    user_id: str = Depends(get_current_user_id),
) -> UserData:
    """Update the client-settable fields of the caller's own dataset.

    The body is `UserDataUpdate`, not the document: fields it does not name are
    server-authoritative and cannot be assigned from a request (issue #451).
    Only the fields actually sent are applied, so an omitted field is left
    alone rather than erased — this used to overwrite the whole document.
    """
    doc = await UserData.get(id)
    # 404 rather than 403: a 403 confirms the row exists and belongs to someone.
    if not doc or doc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Dataset not found")

    for field, value in updated.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    doc.updated_at = get_current_time()
    await doc.save()
    return doc


@router.delete("/{id}")
async def delete_user_data(
    id: PydanticObjectId, user_id: str = Depends(get_current_user_id)
) -> dict[str, bool]:
    doc = await UserData.get(id)
    if not doc or doc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await doc.delete()
    return {"success": True}


@router.get("/{id}/ai-summary", response_model=dict[str, Any])
async def get_ai_summary(
    id: PydanticObjectId, user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    """
    Get the AI summary for a specific user data entry.
    Returns the raw markdown and a structured context string for the frontend chat.
    """
    try:
        # Get the UserData document
        user_data = await UserData.get(id)
        if not user_data or user_data.user_id != user_id:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Check if AI summary exists
        if not user_data.aiSummary:
            raise HTTPException(status_code=404, detail="AI summary not found")

        # Create a structured context string for the frontend chat
        context_string = f"""
        Dataset: {user_data.filename}
        Rows: {user_data.num_rows}
        Columns: {user_data.num_columns}
        
        Overview: {user_data.aiSummary.overview}
        
        Issues:
        {chr(10).join([f"- {issue}" for issue in user_data.aiSummary.issues])}
        
        Relationships:
        {chr(10).join([f"- {rel}" for rel in user_data.aiSummary.relationships])}
        
        Suggestions:
        {chr(10).join([f"- {sug}" for sug in user_data.aiSummary.suggestions])}
        
        Column Information:
        """

        # Add column information
        for field in user_data.data_schema:
            context_string += f"""
            {field.field_name}:
            - Type: {field.field_type}
            - Data Type: {field.data_type or 'Not specified'}
            - Unique Values: {field.unique_values}
            - Missing Values: {field.missing_values}
            - Example Values: {', '.join([str(val) for val in field.example_values[:3]])}
            """

        # Return the response
        return {
            "rawMarkdown": user_data.aiSummary.rawMarkdown,
            "contextString": context_string,
            "overview": user_data.aiSummary.overview,
            "issues": user_data.aiSummary.issues,
            "relationships": user_data.aiSummary.relationships,
            "suggestions": user_data.aiSummary.suggestions,
            "createdAt": (
                user_data.aiSummary.createdAt.isoformat()
                if user_data.aiSummary.createdAt
                else None
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AI summary: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error getting AI summary: {str(e)}"
        )


@router.get("/{id}/eda-summary", response_model=dict[str, Any])
async def get_eda_summary(
    id: PydanticObjectId, user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    """
    Generate and return an Exploratory Data Analysis (EDA) summary for a specific dataset.
    This endpoint will analyze the dataset and provide insights about its structure and content.
    """
    try:
        # Get the UserData document
        user_data = await UserData.get(id)
        if not user_data or user_data.user_id != user_id:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Generate EDA summary using the service
        eda_summary = await generate_eda_summary(user_data)

        return {
            "summary": eda_summary,
            "dataset_id": str(id),
            "created_at": (
                user_data.created_at.isoformat() if user_data.created_at else None
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating EDA summary: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error generating EDA summary: {str(e)}"
        )
