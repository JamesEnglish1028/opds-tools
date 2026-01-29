import boto3
import os
from botocore.exceptions import ClientError

# Load env vars if using dotenv
from dotenv import load_dotenv
load_dotenv()

def get_r2_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        endpoint_url=os.getenv("R2_ENDPOINT_URL"),
        region_name="auto"
    )

def main():
    s3 = get_r2_client()
    bucket = os.getenv("R2_BUCKET_NAME")
    key = "uploads/test-file.txt"
    content = b"This is a test file from test_r2_upload.py"

    try:
        print(f"Uploading to bucket: {bucket}, key: {key}")
        s3.put_object(Bucket=bucket, Key=key, Body=content, ContentType="text/plain")
        print("✅ Upload reported as successful.")

        # Confirm upload exists
        print("🔍 Verifying existence of uploaded file...")
        response = s3.head_object(Bucket=bucket, Key=key)
        print("📁 File exists in R2 with metadata:")
        print(response)

    except ClientError as e:
        print("❌ Upload failed with error:")
        print(e)

if __name__ == "__main__":
    main()
