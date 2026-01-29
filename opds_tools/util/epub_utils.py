import base64
import os
import requests


def get_public_url(epub_url: str) -> str:
    """
    Converts s3://content/... to a public URL, or passes through public URLs.
    """
    if epub_url.startswith("s3://content/"):
        path = epub_url.replace("s3://content/", "")
        domain = os.getenv("R2_PUBLIC_URL", "https://opds-tools.org/content")
        return f"{domain.rstrip('/')}/{path}"
    
    elif epub_url.startswith("http://") or epub_url.startswith("https://"):
        return epub_url
    
    else:
        raise ValueError(f"Unexpected EPUB URL format: {epub_url}")


def encode_epub_url(s3_uri: str) -> str:
    """
    Encodes the public EPUB URL (used by Readium CLI).
    """
    public_url = get_public_url(s3_uri)
    return base64.urlsafe_b64encode(public_url.encode()).decode().rstrip("=")



def supports_byte_ranges(url: str) -> bool:
    """Check if the server supports byte-range requests for streaming EPUB."""
    try:
        response = requests.head(url, timeout=5)
        return response.headers.get("accept-ranges", "").lower() == "bytes"
    except Exception:
        return False