# opds_tools/util/extraction.py
import os
import json
import logging
from flask import flash, current_app
from opds_tools.util.validation import validate_opds_feed
from opds_tools.util.parser import (
    extract_opds_data,
    extract_navigation_links,
    extract_catalog_metadata,
    extract_catalog_links,
    extract_navigation_collections,
    extract_facet_collections,
    extract_groups,
)

logger = logging.getLogger(__name__)

def handle_validation_and_extraction(data, source=None, skip_validation='1'):
    """
    Validate an OPDS feed (unless skipped), then extract and return a context dict
    containing all catalog-level metadata, navigation, groups, and extracted_data.

    :param data: The loaded OPDS JSON
    :param source: Base URL for relative link resolution (if any)
    :param skip_validation: '1' to skip schema validation, otherwise perform it
    :return: dict with keys:
        - catalog_metadata
        - navigation_links
        - catalog_links
        - navigation_collections
        - facet_collections
        - groups
        - extracted_data
        - current_url
    or None if validation fails critically
    """
    # 1) Schema validation
    if skip_validation != '1':
        logger.info("Validating OPDS feed...")
        is_valid, errors = validate_opds_feed(data)
        if is_valid:
            flash("✅ OPDS feed successfully validated.", "success")
        else:
            flash("⚠️ Feed failed schema validation; attempting extraction anyway.", "warning")
            for msg in errors:
                flash(f"• {msg}", "warning")

    # 2) Inject base URL for relative link resolution
    if source:
        data["_base_url"] = source

    try:
        # 3) Extraction
        extracted_data = extract_opds_data(data)
        navigation_links = extract_navigation_links(data)
        catalog_metadata = extract_catalog_metadata(data)
        catalog_links = extract_catalog_links(data)
        navigation_collections = extract_navigation_collections(data)
        facet_collections = extract_facet_collections(data)
        groups = extract_groups(data)

        flash("✅ Data extraction complete.", "success")
        logger.info("Extraction produced keys: %s", list(globals().keys()))

        return {
            "catalog_metadata": catalog_metadata,
            "navigation_links": navigation_links,
            "catalog_links": catalog_links,
            "navigation_collections": navigation_collections,
            "facet_collections": facet_collections,
            "groups": groups,
            "extracted_data": extracted_data,
            "current_url": source,
        }
    except Exception as e:
        flash(f"❌ Failed to extract data: {e}", "danger")
        logger.exception("Error during extraction")
        return None
