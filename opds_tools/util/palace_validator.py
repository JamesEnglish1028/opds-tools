import json
import textwrap
import re
import requests
import time
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
    timeout: int = 10,
    max_retries: int = 3,
    retry_delay: float = 2.0
) -> requests.Response:
    """
    Fetch a URL with fallback Accept headers and retry logic for reliability.
    
    Attempts to fetch with the primary Accept header first. If a 406 (Not Acceptable) 
    error occurs, retries with fallback headers in order. For other HTTP errors (404, 
    500, 502, 503, etc.), retries up to max_retries times with exponential backoff.
    
    Args:
        url: The URL to fetch
        accept_headers: List of Accept headers to try in order. Defaults to [DEFAULT, FALLBACK]
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts for transient errors
        retry_delay: Initial delay between retries in seconds (doubles each retry)
        
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
        # Retry loop for transient errors
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers={"Accept": accept_header}, timeout=timeout)
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                
                # 406 Not Acceptable - try next header (no retry)
                if status_code == 406:
                    print(f"⚠️  HTTP {status_code} (Not Acceptable) for {url} with Accept: {accept_header}")
                    print(f"   Trying next Accept header...")
                    last_error = e
                    break  # Break retry loop, try next header
                
                # Transient errors that should be retried
                if status_code in [404, 500, 502, 503, 504]:
                    print(f"⚠️  HTTP {status_code} error fetching {url}")
                    if attempt < max_retries - 1:
                        delay = retry_delay * (2 ** attempt)  # Exponential backoff
                        print(f"   Retrying in {delay:.1f}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        last_error = e
                        continue  # Retry with same header
                    else:
                        print(f"   Max retries ({max_retries}) reached for {url}")
                        last_error = e
                        break
                
                # Other HTTP errors should fail immediately
                print(f"❌ HTTP {status_code} error fetching {url}: {str(e)}")
                raise
            except requests.exceptions.RequestException as e:
                # Network errors, timeouts, etc.
                print(f"⚠️  Network error fetching {url}: {str(e)}")
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    print(f"   Retrying in {delay:.1f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    last_error = e
                    continue
                else:
                    print(f"   Max retries ({max_retries}) reached for {url}")
                    last_error = e
                    break
            except Exception as e:
                last_error = e
                print(f"❌ Unexpected error fetching {url}: {str(e)}")
                break
    
    # Final fallback: try without Accept header
    print(f"🔄 Trying {url} without Accept header as final fallback...")
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            print(f"✅ Success fetching {url} (no Accept header)")
            return response
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            print(f"⚠️  HTTP {status_code} error fetching {url} (no Accept header)")
            if status_code in [404, 500, 502, 503, 504] and attempt < max_retries - 1:
                delay = retry_delay * (2 ** attempt)
                print(f"   Retrying in {delay:.1f}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            else:
                last_error = e
                break
        except Exception as e:
            last_error = e
            break
    
    # If everything failed, raise the last error we encountered
    print(f"❌ All retry attempts failed for {url}")
    raise last_error or Exception(f"Failed to fetch {url} after all retries")


def fetch_all_pages(
    start_url: str,
    max_pages: Optional[int] = None,
    accept_headers: Optional[List[str]] = None,
    progress_callback=None
) -> dict[str, dict[str, Any]]:
    """
    Fetch all paginated OPDS feeds starting from `start_url`.
    
    Args:
        start_url: The starting URL of the OPDS feed
        max_pages: Maximum number of pages to fetch. None means fetch all.
        accept_headers: List of Accept headers to try. Uses smart fallback if None.
        progress_callback: Optional callback function to report progress.
        
    Returns:
        Dictionary mapping URLs to feed data or error information
    """
    feeds = {}
    current_url = start_url
    visited_urls = set()
    page_count = 0
    
    print(f"\n{'='*60}")
    print(f"📄 Starting OPDS feed pagination from: {start_url}")
    if max_pages:
        print(f"   Max pages limit: {max_pages}")
    print(f"{'='*60}\n")

    while current_url and current_url not in visited_urls:
        if max_pages is not None and page_count >= max_pages:
            print(f"⛔ Reached max pages limit ({max_pages}). Stopping pagination.")
            break

        visited_urls.add(current_url)
        page_count += 1
        
        print(f"📖 Fetching page {page_count}: {current_url}")

        try:
            response = fetch_url_with_fallback(current_url, accept_headers=accept_headers)
            data = response.json()
            feeds[current_url] = data
            
            # Log publications count
            pub_count = len(data.get("publications", []))
            print(f"✅ Page {page_count} fetched successfully: {pub_count} publications found")
            
            if progress_callback:
                progress_callback('page_fetched', {
                    'current_page': page_count,
                    'url': current_url,
                    'publications': pub_count,
                    'max_pages': max_pages
                })
            
        except Exception as e:
            print(f"❌ Error fetching page {page_count}: {str(e)}")
            feeds[current_url] = {"error": str(e)}
            
            if progress_callback:
                progress_callback('page_fetch_error', {
                    'current_page': page_count,
                    'url': current_url,
                    'error': str(e),
                    'max_pages': max_pages
                })
            break

        # Find next page link
        links = data.get("links", [])
        print(f"🔍 Looking for 'next' link in {len(links)} links...")
        
        next_link = next(
            (
                link.get("href")
                for link in links
                if link.get("rel") == "next" and link.get("href")
            ),
            None,
        )

        if not next_link:
            print(f"🏁 No 'next' link found. Pagination complete.")
            break
        
        print(f"➡️  Found next page link: {next_link}")
        current_url = requests.compat.urljoin(current_url, next_link)
        print(f"🔗 Resolved next URL: {current_url}\n")

    print(f"\n{'='*60}")
    print(f"✅ Pagination complete: Fetched {page_count} page(s)")
    print(f"{'='*60}\n")
    
    return feeds


def validate_feed_url(
    url: str, 
    max_pages: Optional[int] = None,
    accept_headers: Optional[List[str]] = None,
    progress_callback = None
) -> dict:
    """
    Fetch and validate a single OPDS feed URL with optional page limit and custom Accept headers.
    
    Args:
        url: The OPDS feed URL to validate
        max_pages: Maximum number of pages to fetch. None means fetch all.
        accept_headers: List of Accept headers to try. Uses smart fallback if None.
        progress_callback: Optional callback function(event_type, data) for progress updates
        
    Returns:
        Dictionary with feed_errors, publication_errors, and summary statistics
    """
    if progress_callback:
        progress_callback('started', {'url': url, 'max_pages': max_pages})
    
    feeds = fetch_all_pages(url, max_pages=max_pages, accept_headers=accept_headers, progress_callback=progress_callback)
    
    if progress_callback:
        progress_callback('pages_fetched', {'total_pages': len(feeds)})
    
    publication_errors = []
    feed_errors = []
    publication_warnings = []
    feed_warnings = []
    pub_count = 0

    page_num = 0
    for page_url, feed in feeds.items():
        page_num += 1
        
        if "error" in feed:
            feed_errors.append({
                "page_number": page_num,
                "url": page_url,
                "error": feed["error"]
            })
            if progress_callback:
                progress_callback('page_validation_error', {
                    'page_number': page_num,
                    'url': page_url,
                    'error': feed["error"]
                })
            continue

        # Run schema validation but continue even if it fails
        if progress_callback:
            progress_callback('validation_stage', {
                'page_number': page_num,
                'stage': 'JSON Schema Validation',
                'url': page_url
            })
        
        is_valid_schema, schema_errors = validate_opds_feed(feed)
        if not is_valid_schema:
            feed_warnings.append({
                "page_number": page_num,
                "url": page_url,
                "warning": "JSON Schema validation failed (continuing)",
                "severity": "warning",
                "details": schema_errors
            })
            if progress_callback:
                progress_callback('validation_warning', {
                    'page_number': page_num,
                    'stage': 'JSON Schema Validation',
                    'url': page_url,
                    'warning': f"Schema validation failed with {len(schema_errors) if isinstance(schema_errors, list) else 1} error(s)"
                })
        else:
            if progress_callback:
                progress_callback('validation_success', {
                    'page_number': page_num,
                    'stage': 'JSON Schema Validation',
                    'url': page_url
                })

        # Proceed to Pydantic validation regardless
        if progress_callback:
            progress_callback('validation_stage', {
                'page_number': page_num,
                'stage': 'Pydantic Feed Structure Validation',
                'url': page_url
            })
        
        try:
            publication_feed = PublicationFeedNoValidation.model_validate(feed)
            if progress_callback:
                progress_callback('validation_success', {
                    'page_number': page_num,
                    'stage': 'Pydantic Feed Structure Validation',
                    'url': page_url
                })
        except ValidationError as e:
            feed_errors.append({
                "page_number": page_num,
                "url": page_url,
                "error": str(e)
            })
            if progress_callback:
                progress_callback('validation_error', {
                    'page_number': page_num,
                    'stage': 'Pydantic Feed Structure Validation',
                    'url': page_url,
                    'error': str(e)
                })
            continue

        # Notify processing this page
        if progress_callback:
            progress_callback('page_validating', {
                'page_number': page_num,
                'url': page_url,
                'publications': len(publication_feed.publications),
                'validation_stage': 'publications'
            })

        pub_validation_errors = 0
        for pub in publication_feed.publications:
            pub_count += 1
            pub_metadata = pub.get("metadata", {})
            pub_title = pub_metadata.get("title", "Untitled")
            
            # Pydantic publication validation
            try:
                OPDS2Publication.model_validate(pub)
            except ValidationError as e:
                pub_validation_errors += 1
                links = pub.get("links", [])

                publication_errors.append({
                    "page_number": page_num,
                    "feed_url": page_url,
                    "identifier": pub_metadata.get("identifier"),
                    "title": pub_metadata.get("title"),
                    "author": pub_metadata.get("author"),
                    "self_url": next(
                        (link.get("href") for link in links if link.get("rel") == "self"),
                        None
                    ),
                    "error": str(e),
                    "json": pub
                })
                if progress_callback:
                    progress_callback('validation_error', {
                        'page_number': page_num,
                        'stage': 'Pydantic Publication Validation',
                        'publication': pub_title,
                        'error': str(e)
                    })
                continue

            # ✅ Check identifier URI validity
            identifier = pub_metadata.get("identifier")
            if not identifier:
                # Missing identifier is a warning
                publication_warnings.append({
                    "page_number": page_num,
                    "feed_url": page_url,
                    "identifier": identifier,
                    "title": pub_metadata.get("title"),
                    "author": pub_metadata.get("author"),
                    "warning": "Missing metadata.identifier",
                    "severity": "warning"
                })
                if progress_callback:
                    progress_callback('validation_warning', {
                        'page_number': page_num,
                        'stage': 'URI Validation',
                        'publication': pub_title,
                        'warning': 'Missing metadata.identifier'
                    })
            elif not is_valid_uri(identifier):
                pub_validation_errors += 1
                publication_errors.append({
                    "page_number": page_num,
                    "feed_url": page_url,
                    "identifier": identifier,
                    "title": pub_metadata.get("title"),
                    "author": pub_metadata.get("author"),
                    "self_url": next(
                        (link.get("href") for link in pub.get("links", []) if link.get("rel") == "self"),
                        None
                    ),
                    "error": "Invalid metadata.identifier — not a valid URI",
                    "json": pub
                })
                if progress_callback:
                    progress_callback('validation_error', {
                        'page_number': page_num,
                        'stage': 'URI Validation',
                        'publication': pub_title,
                        'identifier': identifier,
                        'error': 'Invalid metadata.identifier — not a valid URI'
                    })
            
            # Check for missing optional but recommended fields
            if not pub_metadata.get("author"):
                publication_warnings.append({
                    "page_number": page_num,
                    "feed_url": page_url,
                    "identifier": identifier,
                    "title": pub_metadata.get("title"),
                    "warning": "Missing recommended field: metadata.author",
                    "severity": "info"
                })
            
            if not pub.get("images") and not pub_metadata.get("coverImage"):
                publication_warnings.append({
                    "page_number": page_num,
                    "feed_url": page_url,
                    "identifier": identifier,
                    "title": pub_metadata.get("title"),
                    "warning": "Missing cover image (images[] or metadata.coverImage)",
                    "severity": "info"
                })
        
        # Summary for this page
        if progress_callback:
            if pub_validation_errors == 0:
                progress_callback('validation_success', {
                    'page_number': page_num,
                    'stage': 'Publication Validation Complete',
                    'url': page_url,
                    'publications_checked': len(publication_feed.publications)
                })
            else:
                progress_callback('validation_error', {
                    'page_number': page_num,
                    'stage': 'Publication Validation Complete',
                    'url': page_url,
                    'errors_found': pub_validation_errors,
                    'publications_checked': len(publication_feed.publications)
                })

    result = {
        "feed_errors": feed_errors,
        "publication_errors": publication_errors,
        "feed_warnings": feed_warnings,
        "publication_warnings": publication_warnings,
        "summary": {
            "pages_validated": len(feeds),
            "publication_count": pub_count,
            "error_count": len(publication_errors) + len(feed_errors),
            "warning_count": len(publication_warnings) + len(feed_warnings)
        }
    }
    
    if progress_callback:
        progress_callback('complete', {
            'summary': result['summary'],
            'total_errors': result['summary']['error_count'],
            'total_warnings': result['summary']['warning_count']
        })
    
    return result

