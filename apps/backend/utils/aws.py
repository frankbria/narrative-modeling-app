# utils/aws.py
import boto3
import os
from dotenv import load_dotenv

load_dotenv()

s3_client = boto3.client(
    "s3",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)


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
