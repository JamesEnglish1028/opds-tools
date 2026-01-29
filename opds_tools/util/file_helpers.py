# opds_tools/util/file_helpers.py
import json
import logging
from flask import flash
from werkzeug.utils import secure_filename

from opds_tools.util.extraction import handle_validation_and_extraction
from opds_tools.util.open_search import extract_opensearch_template
from opds_tools.util.parser import process_auth_doc

logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {'json'}

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def handle_file_upload(file_storage, *, skip_validation=False, username=None, password=None):
    """
    Load, validate, and extract an OPDS JSON file, returning the same context keys
    as handle_url_fetch for template rendering.
    """
    logger.info("▶️ handle_file_upload called: %s (skip_validation=%s)", file_storage.filename, skip_validation)

    if not file_storage or not file_storage.filename:
        flash("No file provided.", "warning")
        return None

    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename):
        flash("Please upload a valid .json file.", "danger")
        return None

    # Load JSON
    try:
        data = json.load(file_storage.stream)
        logger.info("✔ Loaded JSON from upload")
    except json.JSONDecodeError as e:
        flash(f"Could not parse JSON: {e}", "danger")
        return None

    # 1) validation & extraction of catalog-level data
    context = handle_validation_and_extraction(
        data,
        source=None,
        skip_validation='1' if skip_validation else '0'
    )
    if context is None:
        flash("Failed to validate or extract from file.", "danger")
        return None

    # At this point, context contains:
    # catalog_metadata, navigation_links, catalog_links,
    # navigation_collections, facet_collections, groups,
    # extracted_data (raw publication list), current_url

    # 2) OpenSearch template
    context['opensearch_template'] = extract_opensearch_template(data)

    # 3) Auth document with credentials
    try:
        context['auth_document'] = process_auth_doc(data, username=username, password=password) or {}
    except Exception as e:
        flash(f"Failed to load auth document: {e}", "warning")
        context['auth_document'] = {}

    # 4) Echo form state
    context['skip_validation'] = skip_validation
    context['username']        = username
    context['password']        = password

    flash(f"✅ File processed successfully ({len(context.get('extracted_data', []))} items).", "success")
    logger.info(
        "✅ handle_file_upload returning context with %d items",
        len(context.get('extracted_data', []))
    )
    return context
