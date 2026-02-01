"""
Feed Service Module

Handles OPDS feed fetching, validation, and extraction.
This service layer contains business logic separated from route handlers.
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from urllib.parse import quote

import requests
from flask import current_app

from opds_tools.util.extraction import handle_validation_and_extraction
from opds_tools.util.parser import extract_opds_data
from opds_tools.util.open_search import extract_opensearch_template, extract_opensearch_template_from_xml
from opds_tools.util.epub_utils import get_public_url, encode_epub_url, supports_byte_ranges
from opds_tools.util.encoding import encode_path

logger = logging.getLogger(__name__)

# Default response template for error cases
DEFAULT_ERROR_RESPONSE = {
    'error': None,
    'catalog_metadata': {},
    'items': [],
    'navigation_links': {},
    'opensearch_template': None,
    'source': None,
    'skip_validation': '1'
}


class FeedFetchError(Exception):
    """Custom exception for feed fetching errors."""
    pass


def _create_error_response(error_msg: str, source_url: str, skip_validation: str = '1') -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        error_msg: Error message to include
        source_url: Original source URL
        skip_validation: Whether validation was skipped
        
    Returns:
        Dict with error response structure
    """
    response = DEFAULT_ERROR_RESPONSE.copy()
    response['error'] = error_msg
    response['source'] = source_url
    response['skip_validation'] = skip_validation
    return response


def _load_local_file(file_path: str) -> Dict[str, Any]:
    """
    Load and parse a local static JSON file.
    
    Args:
        file_path: Path to the local file
        
    Returns:
        Parsed JSON data
        
    Raises:
        FeedFetchError: If file cannot be loaded or parsed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        raise FeedFetchError(f"Failed to read local static file: {e}")


def _fetch_remote_url(source_url: str, username: Optional[str] = None, 
                      password: Optional[str] = None) -> requests.Response:
    """
    Fetch a remote URL with proper headers and authentication.
    
    Args:
        source_url: URL to fetch
        username: Optional username for auth
        password: Optional password for auth
        
    Returns:
        Response object
        
    Raises:
        FeedFetchError: If fetch fails
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; OPDS-Tools/1.0)",
        "Accept": "application/opds+json, application/json;q=0.9, */*;q=0.8"
    }
    auth = (username, password) if username and password else None

    try:
        response = requests.get(source_url, headers=headers, auth=auth, timeout=10)
        response.raise_for_status()
        return response
    except requests.HTTPError as e:
        if e.response.status_code == 406:
            # Fallback: retry without Accept header
            try:
                response = requests.get(source_url, auth=auth, timeout=10)
                response.raise_for_status()
                return response
            except Exception as fallback_error:
                raise FeedFetchError(f"Failed to fetch URL (fallback attempt): {fallback_error}")
        else:
            raise FeedFetchError(f"Failed to fetch URL: {e}")
    except requests.RequestException as e:
        raise FeedFetchError(f"Failed to fetch URL: {e}")


def _extract_opensearch_info(data: Dict[str, Any]) -> Optional[str]:
    """
    Extract OpenSearch template from feed data.
    
    Args:
        data: OPDS feed data
        
    Returns:
        OpenSearch template URL or None
    """
    opensearch_template = extract_opensearch_template(data)
    logger.info("🔍 Extracted opensearch_template from JSON: %s", opensearch_template)
    
    # If it's a pointer to an XML description, fetch and extract
    if opensearch_template and opensearch_template.endswith('/search/?entrypoint=All'):
        logger.info("📡 Looks like a pointer to OpenSearch XML. Fetching and extracting real template...")
        try:
            xml_response = requests.get(opensearch_template, timeout=10)
            xml_response.raise_for_status()
            xml_template = extract_opensearch_template_from_xml(xml_response.text)
            if xml_template:
                logger.info("📄 Extracted opensearch_template from XML: %s", xml_template)
                return xml_template
            else:
                logger.warning("No usable OpenSearch template found in XML.")
        except Exception as e:
            logger.warning(f"Failed to load OpenSearch XML description: {e}")
    
    return opensearch_template


def _process_publication_items(extracted_data: list, manifest_server: str) -> list:
    """
    Process extracted publication data into items for display.
    
    Args:
        extracted_data: Raw publication data from OPDS feed
        manifest_server: Base URL for Readium manifest server
        
    Returns:
        List of processed publication items
    """
    items = []
    
    for pub in extracted_data:
        metadata = pub.get('metadata', {})
        image = next((l for l in pub.get('images', []) if l.get('rel') == 'cover'), None)
        author = ", ".join(metadata.get('author', [])) if isinstance(metadata.get('author'), list) else metadata.get('author')
        description = metadata.get('description') or metadata.get('subtitle') or ""
        published = metadata.get('published')
        acquisition_links = [l for l in pub.get('links', []) if l.get('rel', '').startswith('http://opds-spec.org/acquisition')]

        manifest_url = None
        for link in acquisition_links:
            if link.get('type') == 'application/epub+zip' and link.get('href', '').startswith('http'):
                epub_url = link['href']
                try:
                    public_url = get_public_url(epub_url)

                    # Skip if server doesn't support byte-range requests
                    if not supports_byte_ranges(public_url):
                        logger.info(f"EPUB server for {public_url} does not support byte-range requests.")
                        continue

                    encoded_path = encode_path(public_url)
                    encoded_server = quote(manifest_server, safe="")

                    manifest_url = f"{encoded_server}%2F{encoded_path}/manifest.json"
                    break
                except Exception as e:
                    logger.warning(f"Could not create manifest URL for {epub_url}: {e}")

        items.append({
            "title": metadata.get('title', 'Untitled'),
            "author": author,
            "description": description,
            "published": published,
            "image": image,
            "acquisition_links": acquisition_links,
            "manifest_url": manifest_url
        })

    return items


def handle_url_fetch(source_url: str, skip_validation: str = '1', 
                    username: Optional[str] = None, 
                    password: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch and parse an OPDS feed from a URL or local file.
    
    This is the main entry point for feed fetching. It handles:
    - Local file loading from /static/ paths
    - Remote URL fetching with authentication
    - JSON and XML parsing
    - OpenSearch template extraction
    - Publication data extraction and processing
    
    Args:
        source_url: URL or local path (/static/...) to fetch
        skip_validation: Whether to skip validation ('0' or '1')
        username: Optional username for authentication
        password: Optional password for authentication
        
    Returns:
        Dict with feed data and metadata, or None on error
        
    Raises:
        No exceptions are raised; errors are logged and error responses returned
    """
    
    try:
        # Handle local static files
        if source_url.startswith('/static/'):
            try:
                local_path = os.path.join(current_app.root_path, source_url.lstrip('/'))
                data = _load_local_file(local_path)
                logger.info("✅ Loaded local static file: %s", source_url)

                context = handle_validation_and_extraction(data, source=source_url, skip_validation=skip_validation)
                context['opensearch_template'] = extract_opensearch_template(data)
                logger.info("✅ Final opensearch_template in context: %s", context.get('opensearch_template'))
                return context

            except FeedFetchError as e:
                logger.error("Failed to load local file: %s", str(e))
                return _create_error_response(str(e), source_url, skip_validation)

        # Handle remote URLs
        logger.info("Fetching remote URL: %s", source_url)
        response = _fetch_remote_url(source_url, username, password)

        # Try to parse as JSON
        try:
            data = response.json()
            logger.info("✔ JSON response successfully parsed.")

            context = handle_validation_and_extraction(data, source=source_url, skip_validation=skip_validation)
            if context is None:
                logger.error("Failed to validate or extract data from the feed.")
                return None
            logger.info("✔ Context after JSON extraction: %s", list(context.keys()))

            # Extract OpenSearch info
            context['opensearch_template'] = _extract_opensearch_info(data)

            # Process publications into displayable items
            manifest_server = current_app.config.get("READIUM_CLI_ENDPOINT", "http://localhost:15080/").rstrip("/")
            extracted_data = extract_opds_data(data)
            logger.debug("🔍 extracted_data sample:\n%s", extracted_data[:1] if extracted_data else "empty")

            context["items"] = _process_publication_items(extracted_data, manifest_server)
            context["thorium_web_url"] = current_app.config.get("THORIUM_WEB_CLIENT_URL", "http://localhost:3000/read")
            
            return context

        except ValueError:
            # JSON parsing failed, try XML fallback
            logger.warning("❌ JSON parsing failed — trying XML fallback...")
            if 'xml' in response.headers.get('Content-Type', ''):
                try:
                    opensearch_template = extract_opensearch_template_from_xml(response.text)
                    logger.info("📄 Extracted opensearch_template from XML fallback: %s", opensearch_template)
                    
                    return {
                        'catalog_metadata': {},
                        'items': [],
                        'navigation_links': {},
                        'opensearch_template': opensearch_template,
                        'source': source_url,
                        'skip_validation': skip_validation
                    }
                except Exception as e:
                    logger.error("Failed to parse XML fallback: %s", str(e))
                    return _create_error_response("Failed to parse XML fallback", source_url, skip_validation)
            else:
                logger.error("❌ Response is not valid JSON or recognizable XML.")
                return _create_error_response(
                    "Response is not valid JSON or recognizable XML OpenSearch document",
                    source_url,
                    skip_validation
                )

    except FeedFetchError as e:
        logger.error("Feed fetch error: %s", str(e))
        return _create_error_response(str(e), source_url, skip_validation)
    except Exception as e:
        logger.exception("Unexpected error during feed fetch: %s", str(e))
        return _create_error_response(f"Unexpected error: {str(e)}", source_url, skip_validation)
