# util/validation.py

import requests
import json
from jsonschema import Draft202012Validator
import jsonref
from copy import deepcopy
import logging
import threading

logger = logging.getLogger(__name__)

# OPDS 2.0 Schema URL
SCHEMA_URL = "https://drafts.opds.io/schema/feed.schema.json"

# Schema cache to avoid repeated network requests and processing
_schema_cache = None
_schema_cache_lock = threading.Lock()

def fetch_json(url):
    """Fetch JSON content from a URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def dereference_schema(schema_url):
    """Dereference all $ref references in the schema."""
    return jsonref.JsonRef.replace_refs(fetch_json(schema_url), base_uri=schema_url)

def get_cached_schema(force_refresh=False):
    """
    Get the processed OPDS schema, using cache if available.
    
    Args:
        force_refresh: If True, bypass cache and fetch fresh schema
        
    Returns:
        Dereferenced and cleaned OPDS schema ready for validation
    """
    global _schema_cache
    
    with _schema_cache_lock:
        if _schema_cache is None or force_refresh:
            logger.info("Fetching and dereferencing OPDS schema...")
            dereferenced_schema = dereference_schema(SCHEMA_URL)
            _schema_cache = remove_patterns(deepcopy(dereferenced_schema))
            logger.info("OPDS schema cached successfully.")
        else:
            logger.debug("Using cached OPDS schema.")
    
    return _schema_cache

def remove_patterns(obj, visited=None):
    """
    Recursively remove 'pattern' keys from a JSON schema object.
    This helps avoid ECMAScript regex validation errors.
    """
    if visited is None:
        visited = set()

    obj_id = id(obj)
    if obj_id in visited:
        return obj
    visited.add(obj_id)

    if isinstance(obj, dict):
        return {
            key: remove_patterns(value, visited)
            for key, value in obj.items()
            if key != "pattern"
        }
    elif isinstance(obj, list):
        return [remove_patterns(item, visited) for item in obj]
    else:
        return obj

def validate_opds_feed(data, force_refresh=False):
    """
    Validate a given OPDS 2.0 feed dictionary against the schema.
    
    Uses a cached schema to avoid repeated network requests and processing.
    The schema is fetched and processed only once per application lifecycle.
    
    Args:
        data: The OPDS feed data to validate
        force_refresh: If True, bypass cache and fetch fresh schema
        
    Returns:
        Tuple of (is_valid, error_messages):
            - (True, []) if valid
            - (False, [error_message1, error_message2, ...]) if invalid
    """
    try:
        # Get cached schema (or fetch if not cached)
        clean_schema = get_cached_schema(force_refresh=force_refresh)

        # Create validator
        logger.info("Validating OPDS data against schema...")
        validator = Draft202012Validator(clean_schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))

        if errors:
            error_messages = []
            for err in errors:
                path = " → ".join(map(str, err.path))
                error_messages.append(f"{path}: {err.message}")
                logger.warning(f"Validation failed: {path}: {err.message}")
            return False, error_messages
        else:
            logger.info("Validation successful.")
            return True, []

    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False, [f"Validation error: {str(e)}"]


def clear_schema_cache():
    """
    Clear the cached OPDS schema.
    Useful for forcing a fresh schema fetch on the next validation.
    """
    global _schema_cache
    with _schema_cache_lock:
        _schema_cache = None
        logger.info("Schema cache cleared.")
