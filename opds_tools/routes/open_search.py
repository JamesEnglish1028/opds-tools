from flask import Blueprint, render_template, request, redirect, url_for, flash
import requests
from lxml import etree
from io import BytesIO
from urllib.parse import quote_plus
from opds_tools.util.open_search import extract_opensearch_template_from_xml
import logging

from opds_tools.util.parser import (
    extract_opds_data,
    extract_catalog_metadata,
    extract_navigation_links,
)
from opds_tools.routes.main import handle_url_fetch  # handles fetching and parsing OPDS JSON

# Blueprint registration
open_search_bp = Blueprint('open_search', __name__)

# -------------------------------------------------------------------
# 🧩 Utility: Extract OpenSearch URL from Atom-based catalog
# -------------------------------------------------------------------
def extract_opensearch_url(xml_content):
    """
    Parses an OPDS 1.0 Atom-based XML catalog and finds the OpenSearch
    description link (with type 'application/opensearchdescription+xml').

    Returns the href if found, else None.
    """
    try:
        tree = etree.parse(BytesIO(xml_content))
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'os': 'http://a9.com/-/spec/opensearch/1.1/',
        }
        for link in tree.xpath('//atom:link', namespaces=ns):
            if link.get('rel') == 'search' and link.get('type') == 'application/opensearchdescription+xml':
                return link.get('href')
    except Exception as e:
        print(f"⚠️ Failed to extract OpenSearch URL: {e}")
    return None


# -------------------------------------------------------------------
# 📤 Route: Handle POST submission of search form
# -------------------------------------------------------------------
@open_search_bp.route('/opds-search', methods=['POST'])
def opds_search_post():
    """
    Receives the search form with:
      - `template_url` (e.g., https://example.org/search?q={searchTerms})
      - `search_terms` (user input)

    Replaces `{searchTerms}` in the template with the actual search query
    and redirects to the search results route.
    """
    template_url = request.form.get('template_url')
    search_terms = request.form.get('search_terms')

    
    if not template_url or not search_terms:
        flash("Missing search template or terms.", "danger")
        return redirect(url_for('main.index'))

    # Encode the search terms and substitute into template
    search_url = template_url.replace("{searchTerms}", quote_plus(search_terms))

    # Redirect to the search results route with the constructed URL
    print(f"🔎 Search URL being redirected to: {search_url}")
    return redirect(url_for('open_search.search', source_url=search_url, skip_validation='1'))
   

# -------------------------------------------------------------------
# 🔍 Route: GET handler to display search results
# -------------------------------------------------------------------
@open_search_bp.route('/search', methods=['GET'])
def search():
    """
    Accepts a query param `source_url` pointing to the OPDS+JSON search results.
    Optionally skips schema validation.

    Uses handle_url_fetch to parse the results and render the template.
    """
    source_url = request.args.get('source_url')
    skip_validation = request.args.get('skip_validation', '1')

    if not source_url:
        flash("No search result URL provided.", "danger")
        return redirect(url_for('main.index'))

    # Reuse existing logic to fetch and extract OPDS JSON
    context = handle_url_fetch(source_url, skip_validation=skip_validation)
    if not context:
        flash("Could not load search results.", "danger")
        return redirect(url_for('main.index'))
    
      # 🔧 Ensure template can access publications
    context['items'] = context.get('extracted_data', [])

    return render_template("search_results_json.html", **context)


# -------------------------------------------------------------------
# 🌐 Route: Retrieve OpenSearch template URL from a catalog (XML-based)
# -------------------------------------------------------------------
@open_search_bp.route('/opds-opensearch-template', methods=['GET'])
def get_opensearch_template():
    """
    Accepts a `catalog` query param pointing to an OPDS 1.0 Atom feed.
    Parses the feed to extract an OpenSearch template (if present).
    
    Example use:
    - Client passes: ?catalog=https://example.org/catalog.xml
    - Response: { "template_url": "https://example.org/search?q={searchTerms}" }

    Returns 404 if no template found, or 500 on error.
    """
    catalog_url = request.args.get('catalog')
    if not catalog_url:
        return {"error": "Missing catalog URL"}, 400

    try:
        headers = {"Accept": "application/atom+xml"}
        response = requests.get(catalog_url, headers=headers, timeout=10)
        response.raise_for_status()
        opensearch_url = extract_opensearch_url(response.content)

        if opensearch_url:
            return {"template_url": opensearch_url}
        else:
            return {"error": "No OpenSearch template found in catalog."}, 404

    except Exception as e:
        return {"error": str(e)}, 500
