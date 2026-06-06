# utils/aws.py
import os
from dotenv import load_dotenv

from app.utils.s3 import create_s3_client

load_dotenv()

s3_client = create_s3_client()


# utils/aws.py (continued)
def create_presigned_url(file_name: str, content_type: str, expires_in: int = 3600):
    try:
        response = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": os.getenv("AWS_BUCKET_NAME"),
                "Key": file_name,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )
        return response
    except Exception as e:
        print("Error generating presigned URL:", e)
        return None
