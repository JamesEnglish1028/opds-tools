import base64
import requests

def base64url_encode_s3_path(bucket: str, key: str) -> str:
    path = f"s3://{bucket}/{key}"
    encoded = base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")
    return encoded

def fetch_readium_manifest(encoded_path: str, cli_host: str = "http://localhost:15080") -> dict | None:
    url = f"{cli_host}/{encoded_path}/manifest.json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"[Readium CLI] Error fetching manifest: {e}")
        return None


def check_readium_cli_available(cli_host: str = "http://localhost:15080") -> bool:
    """Check if the Readium CLI server is responding."""
    try:
        r = requests.get(cli_host, timeout=3)
        return r.status_code < 500  # even 404 or 403 means it's up
    except requests.RequestException:
        return False
