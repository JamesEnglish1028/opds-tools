import base64

def encode_path(epub_url: str) -> str:
    # Only extract the key (path within the bucket), not the full public URL
    # e.g., "content/1/BISG_Guide2/BISG_Guide2.epub"
    key = epub_url.split("content/")[-1] if "content/" in epub_url else epub_url

    # R2 key format for Readium is "s3://content/{key}"
    raw = f"s3://content/{key}"
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return encoded
