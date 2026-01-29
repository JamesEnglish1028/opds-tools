import json
import textwrap
import re
import requests
from typing import Any, List, Optional
from urllib.parse import urlparse

from pydantic import ValidationError
from opds_tools.util.validation import validate_opds_feed
from opds_tools.util.palace_models import OPDS2Publication, PublicationFeedNoValidation

# Default flexible Accept header that works with most OPDS servers
DEFAULT_ACCEPT_HEADER = "application/opds+json, application/json"
# Fallback header for servers that don't recognize the above
FALLBACK_ACCEPT_HEADER = "application/json"


def is_valid_uri(value: Optional[str]) -> bool:
    """
    Validate if a value is a valid URI (URL or URN).
    
    Supports both traditional URLs and URNs:
    - URLs: https://example.com/book/123
    - URNs: urn:isbn:9791221503265, urn:oclc:123456, uuid:..., doi:...
    
    Per RFC 3986, a URI must have a scheme (letter followed by alphanumerics, +, -, or .)
    followed by a colon.
    
    Args:
        value: The identifier string to validate
        
    Returns:
        True if the value is a valid URI/URN, False otherwise
    """
    if not value or not isinstance(value, str):
        return False
    
    # RFC 3986: scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )
    # A valid URI must start with a scheme followed by a colon
    scheme_match = re.match(r'^[a-zA-Z][a-zA-Z0-9+\-.]*:', value)
    return bool(scheme_match)


def fetch_url_with_fallback(
    url: str, 
    accept_headers: Optional[List[str]] = None,
    timeout: int = 10
) -> requests.Response:
    """
    Fetch a URL with fallback Accept headers for compatibility with various OPDS servers.
    
    Attempts to fetch with the primary Accept header first. If a 406 (Not Acceptable) 
    error occurs, retries with fallback headers in order. If all headers fail or no 
    headers are provided, falls back to no Accept header.
    
    Args:
        url: The URL to fetch
        accept_headers: List of Accept headers to try in order. Defaults to [DEFAULT, FALLBACK]
        timeout: Request timeout in seconds
        
    Returns:
        requests.Response: The successful response
        
    Raises:
        requests.RequestException: If all fetch attempts fail
    """
    if accept_headers is None:
        accept_headers = [DEFAULT_ACCEPT_HEADER, FALLBACK_ACCEPT_HEADER]
    
    last_error = None
    
    # Try each Accept header in order
    for accept_header in accept_headers:
        try:
            response = requests.get(url, headers={"Accept": accept_header}, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            # 406 Not Acceptable - try next header
            if e.response.status_code == 406:
                last_error = e
                continue
            # Other HTTP errors should fail immediately
            raise
        except Exception as e:
            last_error = e
            continue
    
    # Final fallback: try without Accept header
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response
    except Exception as e:
        # If this also fails, raise the last error we encountered
        raise last_error or e


def fetch_all_pages(
    start_url: str, 
    max_pages: Optional[int] = None,
    accept_headers: Optional[List[str]] = None
) -> dict[str, dict[str, Any]]:
    """
    Fetch all paginated OPDS feeds starting from `start_url`.
    
    Args:
        start_url: The starting URL of the OPDS feed
        max_pages: Maximum number of pages to fetch. None means fetch all.
        accept_headers: List of Accept headers to try. Uses smart fallback if None.
        
    Returns:
        Dictionary mapping URLs to feed data or error information
    """
    feeds = {}
    current_url = start_url
    visited_urls = set()
    page_count = 0

    while current_url and current_url not in visited_urls:
        if max_pages is not None and page_count >= max_pages:
            break

        visited_urls.add(current_url)
        page_count += 1

        try:
            response = fetch_url_with_fallback(current_url, accept_headers=accept_headers)
            data = response.json()
            feeds[current_url] = data
        except Exception as e:
            feeds[current_url] = {"error": str(e)}
            break

        # Find next page link
        next_link = next(
            (
                link.get("href")
                for link in data.get("links", [])
                if link.get("rel") == "next" and link.get("href")
            ),
            None,
        )

        if not next_link:
            break

        current_url = requests.compat.urljoin(current_url, next_link)

    return feeds


def validate_feed_url(
    url: str, 
    max_pages: Optional[int] = None,
    accept_headers: Optional[List[str]] = None
) -> dict:
    """
    Fetch and validate a single OPDS feed URL with optional page limit and custom Accept headers.
    
    Args:
        url: The OPDS feed URL to validate
        max_pages: Maximum number of pages to fetch. None means fetch all.
        accept_headers: List of Accept headers to try. Uses smart fallback if None.
        
    Returns:
        Dictionary with feed_errors, publication_errors, and summary statistics
    """
    feeds = fetch_all_pages(url, max_pages=max_pages, accept_headers=accept_headers)
    publication_errors = []
    feed_errors = []
    pub_count = 0

    for page_url, feed in feeds.items():
        if "error" in feed:
            feed_errors.append({
                "url": page_url,
                "error": feed["error"]
            })
            continue

        # Run schema validation but continue even if it fails
        is_valid_schema, schema_errors = validate_opds_feed(feed)
        if not is_valid_schema:
            feed_errors.append({
                "url": page_url,
                "error": "JSON Schema validation failed (continuing)",
                "details": schema_errors
            })

        # Proceed to Pydantic validation regardless
        try:
            publication_feed = PublicationFeedNoValidation.model_validate(feed)
        except ValidationError as e:
            feed_errors.append({
                "url": page_url,
                "error": str(e)
            })
            continue


        for pub in publication_feed.publications:
            pub_count += 1
            try:
                OPDS2Publication.model_validate(pub)
            except ValidationError as e:
                metadata = pub.get("metadata", {})
                links = pub.get("links", [])

                publication_errors.append({
                    "feed_url": page_url,
                    "identifier": metadata.get("identifier"),
                    "title": metadata.get("title"),
                    "author": metadata.get("author"),
                    "self_url": next(
                        (link.get("href") for link in links if link.get("rel") == "self"),
                        None
                    ),
                    "error": str(e),
                    "json": pub
                })
                continue

            # ✅ Check identifier URI validity
            metadata = pub.get("metadata", {})
            identifier = metadata.get("identifier")
            if not is_valid_uri(identifier):
                publication_errors.append({
                    "feed_url": page_url,
                    "identifier": identifier,
                    "title": metadata.get("title"),
                    "author": metadata.get("author"),
                    "self_url": next(
                        (link.get("href") for link in pub.get("links", []) if link.get("rel") == "self"),
                        None
                    ),
                    "error": "Invalid metadata.identifier — not a valid URI",
                    "json": pub
                })

    return {
        "feed_errors": feed_errors,
        "publication_errors": publication_errors,
        "summary": {
            "pages_validated": len(feeds),
            "publication_count": pub_count,
            "error_count": len(publication_errors) + len(feed_errors)
        }
    }
