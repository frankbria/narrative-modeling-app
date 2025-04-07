# routes/s3.py
from fastapi import APIRouter, Query
from utils.aws import create_presigned_url

router = APIRouter()


@router.get("/s3/upload-url")
async def get_upload_url(
    file_name: str = Query(...), content_type: str = Query("application/octet-stream")
):
    url = create_presigned_url(file_name, content_type)
    if url:
        return {"upload_url": url}
    return {"error": "Failed to generate pre-signed URL"}
