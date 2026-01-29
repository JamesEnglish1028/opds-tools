# util/validation.py

import requests
import json
from jsonschema import Draft202012Validator
import jsonref
from copy import deepcopy
import logging

logger = logging.getLogger(__name__)

# OPDS 2.0 Schema URL
SCHEMA_URL = "https://drafts.opds.io/schema/feed.schema.json"

def fetch_json(url):
    """Fetch JSON content from a URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def dereference_schema(schema_url):
    """Dereference all $ref references in the schema."""
    return jsonref.JsonRef.replace_refs(fetch_json(schema_url), base_uri=schema_url)

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

def validate_opds_feed(data):
    """
    Validate a given OPDS 2.0 feed dictionary against the schema.
    Returns (True, []) if valid, or (False, [error_message1, error_message2, ...]) if not.
    """
    try:
        # Fetch, dereference, and sanitize the schema
        logger.info("Fetching and dereferencing OPDS schema...")
        dereferenced_schema = dereference_schema(SCHEMA_URL)
        clean_schema = remove_patterns(deepcopy(dereferenced_schema))

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
