from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
import json
import requests
import os

from opds_tools.util.file_helpers import handle_file_upload
from opds_tools.util.validation import validate_opds_feed
from opds_tools.util.parser import extract_navigation_links, extract_catalog_metadata, extract_catalog_links, extract_navigation_collections, extract_facet_collections, extract_groups, process_auth_doc
from opds_tools.util.csv_exporter import generate_csv
from urllib.parse import quote, urljoin
from opds_tools.models import db, Catalog, Publication
from opds_tools.services.feed_service import handle_url_fetch
import logging

logger = logging.getLogger(__name__)
main = Blueprint('main', __name__)

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
    """Redirect to EPUB reader route."""
    return redirect(url_for("epub.reader", book=request.args.get("book")))


@main.route("/epub-selector", methods=["GET", "POST"])
def epub_selector():
    """Redirect to EPUB selector route."""
    return redirect(url_for("epub.epub_selector"))


@main.route("/manage-epubs", methods=["GET", "POST"])
def manage_epubs():
    """Redirect to EPUB management route."""
    return redirect(url_for("epub.manage_epubs"))