import os
import boto3
from botocore.exceptions import ClientError


def get_r2_config():
    """Return a validated dict of R2 config values from environment variables."""
    config = {
        "endpoint": os.getenv("R2_ENDPOINT"),
        "bucket": os.getenv("R2_BUCKET"),
        "public_url": os.getenv("R2_PUBLIC_URL"),
        "access_key": os.getenv("R2_ACCESS_KEY_ID"),
        "secret_key": os.getenv("R2_SECRET_ACCESS_KEY")
    }
    missing = [key for key, val in config.items() if not val]
    if missing:
        raise RuntimeError(f"Missing R2 config values: {', '.join(missing)}")
    return config


def get_r2_client():
    """Create and return a boto3 S3 client for Cloudflare R2."""
    cfg = get_r2_config()
    return boto3.client(
        "s3",
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
        endpoint_url=cfg["endpoint"],
        region_name="auto"
    )


def upload_to_r2(file_stream, key, content_type="application/octet-stream"):
    """Upload a file-like object to R2 and return the public URL."""
    cfg = get_r2_config()
    s3 = get_r2_client()

    try:
        print(f"📤 Uploading to R2: bucket={cfg['bucket']}, key={key}, content_type={content_type}")
        s3.upload_fileobj(
            Fileobj=file_stream,
            Bucket=cfg["bucket"],
            Key=key,
            ExtraArgs={"ContentType": content_type}
        )
        public_url = f"{cfg['public_url'].rstrip('/')}/{key}"
        print(f"✅ R2 upload successful: {public_url}")
        return public_url
    except ClientError as e:
        print(f"❌ R2 upload error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected R2 upload error: {e}")
        return None


def delete_from_r2(key):
    """Delete an object from R2."""
    cfg = get_r2_config()
    s3 = get_r2_client()

    try:
        print(f"🗑️ Deleting from R2: bucket={cfg['bucket']}, key={key}")
        s3.delete_object(Bucket=cfg["bucket"], Key=key)
        print("✅ Deletion successful")
        return True
    except ClientError as e:
        print(f"❌ R2 delete error: {e}")
        return False


def object_exists_in_r2(key):
    """Check if an object exists in R2."""
    cfg = get_r2_config()
    s3 = get_r2_client()

    try:
        s3.head_object(Bucket=cfg["bucket"], Key=key)
        print(f"✅ Object exists: {key}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            print(f"🚫 Object not found: {key}")
            return False
        else:
            print(f"❌ Error checking object existence: {e}")
            return False


def download_from_r2(key):
    """Download an object from R2 and return its bytes."""
    cfg = get_r2_config()
    s3 = get_r2_client()

    try:
        print(f"📥 Downloading from R2: bucket={cfg['bucket']}, key={key}")
        response = s3.get_object(Bucket=cfg["bucket"], Key=key)
        return response["Body"].read()
    except ClientError as e:
        print(f"❌ R2 download error: {e}")
        return None
