from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify,current_app
import json
import requests
import os
import base64

from opds_tools.util.extraction import handle_validation_and_extraction
from opds_tools.util.file_helpers import handle_file_upload
from opds_tools.util.validation import validate_opds_feed
from opds_tools.util.parser import extract_opds_data, extract_navigation_links, extract_catalog_metadata, extract_catalog_links, extract_navigation_collections, extract_facet_collections, extract_groups, process_auth_doc
from opds_tools.util.csv_exporter import generate_csv
from opds_tools.util.epub_utils import encode_epub_url, get_public_url
from urllib.parse import quote, urljoin
from opds_tools.util.open_search import extract_opensearch_template  # your improved function
from opds_tools.models.catalog import Catalog
from opds_tools.models.publication import Publication
from opds_tools.models import db
import logging
from opds_tools.util.encoding import encode_path
from opds_tools.util.epub_utils import supports_byte_ranges 

logger = logging.getLogger(__name__)
main = Blueprint('main', __name__)

# -------------------------
# Helpers
# -------------------------



### Fetch the OPDS URL

def handle_url_fetch(source_url, skip_validation='1', username=None, password=None):
    # Check for local static file path
    if source_url.startswith('/static/'):
        try:
            local_path = os.path.join(current_app.root_path, source_url.lstrip('/'))
            with open(local_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            context = handle_validation_and_extraction(data, source=source_url, skip_validation=skip_validation)
            context['opensearch_template'] = extract_opensearch_template(data)
            logger.info("✅ Final opensearch_template in context: %s", context.get('opensearch_template'))
            return context

        except Exception as e:
            flash(f"Failed to read local static file: {e}", "danger")
            return {
                'error': f"Failed to read local static file: {e}",
                'catalog_metadata': {},
                'items': [],
                'navigation_links': {},
                'opensearch_template': None,
                'source': source_url,
                'skip_validation': skip_validation
            }

    # Remote fetch (URL)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; OPDS-Tools/1.0)",
        "Accept": "application/opds+json, application/json;q=0.9, */*;q=0.8"
    }
    auth = (username, password) if username and password else None

    try:
        response = requests.get(source_url, headers=headers, auth=auth, timeout=10)
        response.raise_for_status()
    except requests.HTTPError as e:
        if e.response.status_code == 406:
            try:
                response = requests.get(source_url, auth=auth, timeout=10)
                response.raise_for_status()
            except Exception as fallback_error:
                flash(f"Failed to fetch URL (fallback attempt): {fallback_error}", "danger")
                return {
                    'error': f"Failed to fetch URL (fallback attempt): {fallback_error}",
                    'catalog_metadata': {},
                    'items': [],
                    'navigation_links': {},
                    'opensearch_template': None,
                    'source': source_url,
                    'skip_validation': skip_validation
                }
        else:
            flash(f"Failed to fetch URL: {e}", "danger")
            return {
                'error': f"Failed to fetch URL: {e}",
                'catalog_metadata': {},
                'items': [],
                'navigation_links': {},
                'opensearch_template': None,
                'source': source_url,
                'skip_validation': skip_validation
            }
    except requests.RequestException as e:
        flash(f"Failed to fetch URL: {e}", "danger")
        return {
            'error': f"Failed to fetch URL: {e}",
            'catalog_metadata': {},
            'items': [],
            'navigation_links': {},
            'opensearch_template': None,
            'source': source_url,
            'skip_validation': skip_validation
        }

    # Try to parse JSON first
    try:
        data = response.json()
        logger.info("✔ JSON response successfully parsed.")

        context = handle_validation_and_extraction(data, source=source_url, skip_validation=skip_validation)
        if context is None:
            flash("Failed to validate or extract data from the feed.", "danger")
            return None
        logger.info("✔ Context after JSON extraction: %s", list(context.keys()))

        opensearch_template = extract_opensearch_template(data)
        logger.info("🔍 Extracted opensearch_template from JSON: %s", opensearch_template)
        context['opensearch_template'] = opensearch_template

        if opensearch_template and opensearch_template.endswith('/search/?entrypoint=All'):
            logger.info("📡 Looks like a pointer to OpenSearch XML. Fetching and extracting real template...")
            from ..util.open_search import extract_opensearch_template_from_xml
            try:
                xml_response = requests.get(opensearch_template, timeout=10)
                xml_response.raise_for_status()
                xml_template = extract_opensearch_template_from_xml(xml_response.text)
                if xml_template:
                    logger.info("📄 Extracted opensearch_template from XML: %s", xml_template)
                    context['opensearch_template'] = xml_template
                    flash("Fetched OpenSearch template from XML description.", "info")
                else:
                    flash("No usable OpenSearch template found in XML.", "warning")
            except Exception as e:
                flash(f"Failed to load OpenSearch XML description: {e}", "warning")

        elif not opensearch_template and 'xml' in response.headers.get('Content-Type', ''):
            from util.open_search import extract_opensearch_template_from_xml
            logger.warning("⚠ No JSON template found, trying direct XML fallback...")
            xml_template = extract_opensearch_template_from_xml(response.text)
            logger.info("📄 Extracted opensearch_template from XML: %s", xml_template)
            context['opensearch_template'] = xml_template
            logger.info("✅ Final opensearch_template in context: %s", context.get('opensearch_template'))

        extracted_data = extract_opds_data(data)
        logger.debug("🔍 extracted_data sample:\n%s", extracted_data[:1])

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

                        # 🚫 Skip if server doesn't support byte-range requests
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
                "manifest_url": manifest_url  # ✅ now part of each item
            })

        context["items"] = items
        context["thorium_web_url"] = current_app.config["THORIUM_WEB_CLIENT_URL"]
        return context

    except ValueError:
        logger.error("❌ JSON parsing failed — trying XML fallback...")
        if 'xml' in response.headers.get('Content-Type', ''):
            from util.open_search import extract_opensearch_template_from_xml
            logger.info("📄 XML content detected — attempting to extract OpenSearch template...")
            opensearch_template = extract_opensearch_template_from_xml(response.text)
            logger.info("📄 Extracted opensearch_template from XML fallback: %s", opensearch_template)
            flash("Fetched an OpenSearch XML Description Document.", "info")
            logger.info("✅ Final opensearch_template from XML-only fallback: %s", opensearch_template)

            return {
                'catalog_metadata': {},
                'items': [],
                'navigation_links': {},
                'opensearch_template': opensearch_template,
                'source': source_url,
                'skip_validation': skip_validation
            }
        else:
            logger.error("❌ Response is not valid JSON or recognizable XML.")
            flash("Response is not valid JSON or recognizable XML OpenSearch document.", "danger")
            return {
                'error': "Unrecognized response format",
                'catalog_metadata': {},
                'items': [],
                'navigation_links': {},
                'opensearch_template': None,
                'source': source_url,
                'skip_validation': skip_validation
            }




# -------------------------
# Routes
# -------------------------

# MAIN ROUTE

@main.route('/', methods=['GET', 'POST'])
def index():
    logger.info("Rendering homepage.")
    catalogs = Catalog.query.order_by(Catalog.id.desc()).all()  # fetch persistent catalog list

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'upload_file':
            file = request.files.get('opds_file')
            skip_validation = request.form.get('skip_validation') == '1'
            username = request.form.get('username')
            password = request.form.get('password')

            if not file:
                flash("No file selected.", "warning")
                return render_template('index.html', catalogs=catalogs)

            context = handle_file_upload(
                file,
                skip_validation=skip_validation,
                username=username,
                password=password
            )

        elif form_type == 'add_catalog':
            title = request.form.get('title')
            description = request.form.get('description')
            url = request.form.get('url')

            if not title or not url:
                flash("Title and URL are required.", "danger")
            else:
                catalog = Catalog(title=title, description=description, url=url)
                db.session.add(catalog)
                db.session.commit()
                flash("Catalog added to your list.", "success")

            return redirect(url_for('main.index'))

        elif form_type == 'edit_catalog':
            catalog_id = request.form.get('catalog_id')
            title = request.form.get('title')
            description = request.form.get('description')
            url = request.form.get('url')

            catalog = Catalog.query.get(catalog_id)
            if catalog:
                catalog.title = title
                catalog.description = description
                catalog.url = url
                db.session.commit()
                flash("Catalog updated successfully.", "success")
            else:
                flash("Catalog not found.", "danger")

            return redirect(url_for('main.index'))

        # ✅ New case: Fetch feed URL from main form or registry selection
        elif form_type == 'fetch_url':
            feed_url = request.form.get('feed_url')
            skip_validation = request.form.get('skip_validation') == '1'
            username = request.form.get('username')
            password = request.form.get('password')

            if not feed_url:
                flash("Feed URL is required.", "warning")
                return render_template('index.html', catalogs=catalogs)

            return redirect(url_for(
                'main.index',
                feed_url=feed_url,
                skip_validation=int(skip_validation),
                username=username,
                password=password
            ))

        # Fallback: legacy file/url mixed upload
        feed_url       = request.form.get('feed_url')
        skip_validation= request.form.get('skip_validation') == '1'
        username       = request.form.get('username')
        password       = request.form.get('password')
        file           = request.files.get('opds_file')

        if not feed_url and not file:
            flash("Please provide a URL or upload a file.", "warning")
            return render_template('index.html', catalogs=catalogs)

        if feed_url:
            return redirect(url_for(
                'main.fetch_url',
                source_url=feed_url,
                skip_validation=int(skip_validation),
                username=username,
                password=password
            ))

        if context:
            context["catalogs"] = catalogs
            return render_template('index.html', **context)

        return render_template('index.html', catalogs=catalogs)

    # GET request
    feed_url       = request.args.get('feed_url')
    skip_validation= request.args.get('skip_validation') == '1'
    username       = request.args.get('username')
    password       = request.args.get('password')

    if feed_url:
        context = handle_url_fetch(
            source_url=feed_url,
            skip_validation=skip_validation,
            username=username,
            password=password
        )
        if context:
            context["catalogs"] = catalogs
            return render_template('index.html', **context)

    return render_template(
        'index.html',
        catalogs=catalogs,
        catalog_metadata=None,
        publications=None,
        navigation=None,
        auth_document=None
    )




# FETCH ROUTE

@main.route('/fetch')
def fetch_url():
    source_url = request.args.get('source_url')
    skip_validation = request.args.get('skip_validation') == '1'
    username = request.args.get('username')
    password = request.args.get('password')

    if not source_url:
        flash("No URL provided for fetching.", "warning")
        return redirect(url_for('main.index'))

    context = handle_url_fetch(
        source_url,
        skip_validation=skip_validation,
        username=username,
        password=password
    )

    if context:
        return render_template('index.html', **context)

    return redirect(url_for(
        'main.index',
        feed_url=source_url,
        skip_validation=int(skip_validation)
    ))

# route for deleting saved catalog in My Lits

@main.route('/delete-catalog/<int:catalog_id>', methods=['POST'])
def delete_catalog(catalog_id):
    catalog = Catalog.query.get_or_404(catalog_id)
    db.session.delete(catalog)
    db.session.commit()
    flash("Catalog deleted.", "info")
    return redirect(url_for('main.index'))

# route for displaying saved catalog in My List

@main.route('/api/catalogs')
def api_catalogs():
    catalogs = Catalog.query.order_by(Catalog.id.desc()).all()
    return jsonify([
        {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "url": c.url
        } for c in catalogs
    ])

    
# AUTH DOCUMENT MODAL ROUTE HANDLING

@main.route('/auth_doc_modal')
def auth_doc_modal():
    auth_url = request.args.get('url')
    if not auth_url:
        return "Missing URL", 400

    try:
        resp = requests.get(auth_url, timeout=10)
        resp.raise_for_status()
        auth_doc = resp.json()

        # Extract metadata title
        metadata = auth_doc.get("title") or auth_doc.get("metadata", {}).get("title", "Authentication Document")

        # Group links by rel type
        general_rels = {"start", "help", "alternate", "logo"}
        extension_rels = {
            "http://librarysimplified.org/terms/rel/user-profile",
            "http://librarysimplified.org/rel/designated-agent/copyright"
        }

        general_links = []
        extension_links = []
        other_links = []

        for link in auth_doc.get("links", []):
            rel = link.get("rel", "")
            if rel in general_rels:
                general_links.append(link)
            elif rel in extension_rels:
                extension_links.append(link)
            else:
                other_links.append(link)

        # Parse authentication endpoints
        authentication_endpoints = []
        for method in auth_doc.get("authentication", []):
            authentication_endpoints.append({
                "type": method.get("type", "unknown"),
                "description": method.get("description", "No description provided."),
                "inputs": method.get("inputs", {})
            })

        return render_template(
            "auth_doc_modal.html",
            title=metadata,
            general_links=general_links,
            extension_links=extension_links,
            other_links=other_links,
            authentication_endpoints=authentication_endpoints
        )

    except Exception as e:
        current_app.logger.warning(f"Failed to fetch authentication document: {e}")
        return f"Failed to load document: {e}", 500


# JSON DOCUMENT PREVIEW MODAL ROUTE HANDLING

from flask import Blueprint, request, jsonify
import requests

preview_bp = Blueprint('preview', __name__)

@main.route("/preview-proxy")
def preview_proxy():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing URL parameter"}), 400

    try:
        headers = {"Accept": "application/opds+json"}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type or "application/opds+json" in content_type:
            return jsonify(response.json())
        else:
            # Return raw text (HTML, XML, etc.) as plain text fallback
            return response.text, 200, {"Content-Type": "text/plain"}

    except Exception as e:
        return jsonify({"error": f"Failed to fetch preview: {str(e)}"}), 500


@main.route('/clear')
def clear_session():
    return redirect(url_for('main.index'))


@main.route("/reader")
def reader():
    book_url = request.args.get("book")
    if not book_url:
        return "Missing 'book' parameter", 400

    thorium_url = current_app.config["THORIUM_WEB_CLIENT_URL"]
    return render_template("thorium_reader.html", thorium_url=thorium_url, book_url=book_url)


# select EPUB from stored in R2
@main.route("/epub-selector", methods=["GET", "POST"])
def epub_selector():
    thorium_url = current_app.config["THORIUM_WEB_CLIENT_URL"]
    manifest_server = current_app.config["READIUM_CLI_ENDPOINT"].rstrip("/")
    publications = Publication.query.filter(Publication.epub_url.isnot(None)).all()

    epub_choices = []
    for pub in publications:
        encoded = encode_epub_url(pub.epub_url)
        base_url = f"{manifest_server}/{encoded}"
        book_param = quote(base_url, safe="") + "/manifest.json"

        # 🔒 Escape only the base manifest URL (not /manifest.json)
        base_url = f"{manifest_server}/{encoded}"
        encoded_manifest_url = quote(base_url, safe="") + "/manifest.json"

        epub_choices.append({
            "title": pub.title or pub.epub_url,
            "book_url": encoded_manifest_url
        })

    if request.method == "POST":
        selected_book_url = request.form.get("book_url")
        return redirect(f"{thorium_url}?book={selected_book_url}")

    return render_template("epub_selector.html", epub_choices=epub_choices, thorium_url=thorium_url)


from urllib.parse import quote
import os

import base64
from urllib.parse import quote

@main.route("/manage-epubs", methods=["GET", "POST"])
def manage_epubs():
    if request.method == "POST":
        delete_ids = request.form.getlist("delete_ids")
        if delete_ids:
            for delete_id in delete_ids:
                pub = Publication.query.get(delete_id)
                if pub:
                    db.session.delete(pub)
            db.session.commit()
            flash(f"Deleted {len(delete_ids)} publication(s).", "success")
        else:
            flash("No EPUBs selected.", "warning")
        return redirect(url_for("main.manage_epubs"))

    manifest_server = current_app.config["READIUM_CLI_ENDPOINT"].rstrip("/")  # e.g. http://localhost:15080
    thorium_url = current_app.config["THORIUM_WEB_CLIENT_URL"]  # e.g. http://localhost:3000/read

    publications = Publication.query.filter(Publication.epub_url.isnot(None)).order_by(Publication.id.desc()).all()

    enriched_pubs = []
    for pub in publications:
        public_url = get_public_url(pub.epub_url)

        # Base64 encode the public URL
        encoded = base64.urlsafe_b64encode(public_url.encode()).decode().rstrip("=")

        # Build Readium CLI URL (without manifest yet)
        readium_base = f"{manifest_server}/{encoded}"

        # Percent-encode the full Readium base URL
        encoded_readium_base = quote(readium_base, safe="")

        # Append /manifest.json (unencoded)
        thorium_book_param = f"{encoded_readium_base}/manifest.json"

        # Final Thorium URL
        thorium_link = f"{thorium_url}?book={thorium_book_param}"

        enriched_pubs.append({
            "id": pub.id,
            "title": pub.title or "Untitled",
            "epub_url": pub.epub_url,
            "book_url": thorium_link
        })

    return render_template("manage_epubs.html", publications=enriched_pubs)
