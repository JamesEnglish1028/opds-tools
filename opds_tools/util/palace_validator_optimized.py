"""
Optimized OPDS validation for handling hundreds of pages efficiently.

Key optimizations:
- Parallel page fetching with connection pooling
- Single-pass Pydantic validation (skip redundant JSON Schema)
- Batch processing of publications
- Streaming error reporting via callbacks
- Memory-efficient processing
"""

import json
import re
from typing import Any, List, Optional, Callable, Dict, Tuple
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pydantic import ValidationError

from opds_tools.util.palace_models import OPDS2Publication, PublicationFeedNoValidation

# Default flexible Accept header that works with most OPDS servers
DEFAULT_ACCEPT_HEADER = "application/opds+json, application/json"
FALLBACK_ACCEPT_HEADER = "application/json"

# Connection pooling configuration
MAX_WORKERS = 5  # Parallel page fetches
BATCH_SIZE = 50  # Publications per batch
REQUEST_TIMEOUT = 15
RETRY_STRATEGY = Retry(
    total=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"],
    backoff_factor=1
)


class OptimizedSession:
    """Thread-safe session with connection pooling and retries."""
    
    def __init__(self):
        self.session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=RETRY_STRATEGY,
            pool_connections=MAX_WORKERS,
            pool_maxsize=MAX_WORKERS
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def get_with_fallback(self, url: str) -> requests.Response:
        """Fetch URL with Accept header fallback."""
        for accept_header in [DEFAULT_ACCEPT_HEADER, FALLBACK_ACCEPT_HEADER]:
            try:
                response = self.session.get(
                    url, 
                    headers={"Accept": accept_header},
                    timeout=REQUEST_TIMEOUT
                )
                if response.status_code != 406:  # Not Acceptable
                    response.raise_for_status()
                    return response
            except requests.exceptions.RequestException:
                continue
        
        # Final attempt without Accept header
        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response
    
    def close(self):
        self.session.close()


def is_valid_uri(value: Optional[str]) -> bool:
    """Validate if a value is a valid URI (URL or URN)."""
    if not value or not isinstance(value, str):
        return False
    scheme_match = re.match(r'^[a-zA-Z][a-zA-Z0-9+\-.]*:', value)
    return bool(scheme_match)


class PublicationValidator:
    """Handles validation of individual publications."""
    
    @staticmethod
    def validate_publication(pub: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate a single publication.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Pydantic validation
            OPDS2Publication.model_validate(pub)
            
            # Check identifier URI validity
            metadata = pub.get("metadata", {})
            identifier = metadata.get("identifier")
            if identifier and not is_valid_uri(identifier):
                return False, "Invalid metadata.identifier — not a valid URI"
            
            return True, None
        except ValidationError as e:
            return False, str(e)
    
    @staticmethod
    def extract_publication_info(pub: dict) -> Dict[str, Any]:
        """Extract metadata from publication for error reporting."""
        metadata = pub.get("metadata", {})
        links = pub.get("links", [])
        return {
            "identifier": metadata.get("identifier"),
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "self_url": next(
                (link.get("href") for link in links if link.get("rel") == "self"),
                None
            )
        }


def fetch_page_batch(
    urls: List[str],
    session: OptimizedSession
) -> Dict[str, Tuple[bool, Any]]:
    """Fetch multiple pages in parallel using thread pool."""
    results = {}
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(session.get_with_fallback, url): url for url in urls}
        
        for future in as_completed(futures):
            url = futures[future]
            try:
                response = future.result()
                results[url] = (True, response.json())
            except Exception as e:
                results[url] = (False, str(e))
    
    return results


def validate_publications_batch(
    publications: List[dict],
    page_url: str,
    on_error: Optional[Callable] = None
) -> Tuple[int, int]:
    """
    Validate a batch of publications with callback for each error.
    
    Returns:
        Tuple of (valid_count, error_count)
    """
    valid_count = 0
    error_count = 0
    validator = PublicationValidator()
    
    for pub in publications:
        is_valid, error_msg = validator.validate_publication(pub)
        
        if is_valid:
            valid_count += 1
        else:
            error_count += 1
            if on_error:
                on_error({
                    "feed_url": page_url,
                    "error": error_msg,
                    **validator.extract_publication_info(pub)
                })
    
    return valid_count, error_count


# Removed unused async function - validate_feed_url_optimized handles all pagination synchronously


def validate_feed_url_optimized(
    url: str,
    max_pages: Optional[int] = None,
    on_publication_error: Optional[Callable] = None,
    on_feed_error: Optional[Callable] = None
) -> dict:
    """
    Fetch and validate OPDS feed with optimizations for scale.
    
    Args:
        url: Starting OPDS feed URL
        max_pages: Maximum pages to fetch
        on_publication_error: Callback for each publication error
        on_feed_error: Callback for each feed error
        
    Returns:
        Dictionary with feed_errors, publication_errors, and summary statistics
    """
    feed_errors = []
    publication_errors = []
    pages_validated = 0
    publications_valid = 0
    publications_error = 0
    
    session = OptimizedSession()
    validator = PublicationValidator()
    
    try:
        to_fetch = [url]
        visited = set()
        page_count = 0
        
        while to_fetch and (max_pages is None or page_count < max_pages):
            # Prepare batch of URLs to fetch
            batch_urls = []
            for fetch_url in to_fetch:
                if fetch_url not in visited:
                    batch_urls.append(fetch_url)
                    visited.add(fetch_url)
                    page_count += 1
                    if max_pages and page_count >= max_pages:
                        break
            
            if not batch_urls:
                break
            
            # Fetch batch in parallel using ThreadPoolExecutor
            results = fetch_page_batch(batch_urls, session)
            
            # Process results and collect next URLs
            to_fetch = []
            for page_url, (success, data) in results.items():
                pages_validated += 1
                
                if not success:
                    feed_error = {"url": page_url, "error": data}
                    feed_errors.append(feed_error)
                    if on_feed_error:
                        on_feed_error(feed_error)
                    continue
                
                # Process publications in batches
                publications = data.get("publications", [])
                for i in range(0, len(publications), BATCH_SIZE):
                    batch = publications[i:i + BATCH_SIZE]
                    for pub in batch:
                        is_valid, error_msg = validator.validate_publication(pub)
                        
                        if is_valid:
                            publications_valid += 1
                        else:
                            publications_error += 1
                            pub_error = {
                                "feed_url": page_url,
                                "error": error_msg,
                                **validator.extract_publication_info(pub)
                            }
                            publication_errors.append(pub_error)
                            if on_publication_error:
                                on_publication_error(pub_error)
                
                # Find next page links
                for link in data.get("links", []):
                    if link.get("rel") == "next":
                        next_url = urljoin(page_url, link.get("href", ""))
                        if next_url not in visited:
                            to_fetch.append(next_url)
    
    finally:
        session.close()
    
    # Return in the format expected by the template
    return {
        "feed_errors": feed_errors,
        "publication_errors": publication_errors,
        "summary": {
            "pages_validated": pages_validated,
            "publication_count": publications_valid + publications_error,
            "error_count": len(feed_errors) + len(publication_errors)
        }
    }


def validate_feed_url_streaming(
    url: str,
    max_pages: Optional[int] = None,
) -> None:
    """
    DEPRECATED: Streaming validation is not supported in synchronous context.
    Use validate_feed_url_optimized() with callbacks instead.
    """
    raise NotImplementedError(
        "Streaming validation is deprecated. Use validate_feed_url_optimized() "
        "with on_publication_error and on_feed_error callbacks instead."
    )
