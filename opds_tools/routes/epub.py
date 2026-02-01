import os
import re
import base64
from urllib.parse import quote
from flask import Blueprint, request, Response, send_file, render_template, redirect, url_for, flash, current_app
import logging

from opds_tools.models import db, Publication
from opds_tools.util.epub_utils import encode_epub_url, get_public_url

logger = logging.getLogger(__name__)

epub_bp = Blueprint("epub", __name__)


@epub_bp.route("/books/<filename>")
def serve_epub(filename):
    """Serve EPUB file with byte-range support."""
    file_path = os.path.join("uploads", filename)

    if not os.path.exists(file_path):
        return "File not found", 404

    range_header = request.headers.get('Range', None)
    if not range_header:
        return send_file(file_path, mimetype="application/epub+zip")

    size = os.path.getsize(file_path)
    byte1, byte2 = 0, None

    match = re.search(r"bytes=(\d+)-(\d*)", range_header)
    if match:
        byte1 = int(match.group(1))
        if match.group(2):
            byte2 = int(match.group(2))
    length = (byte2 + 1 if byte2 else size) - byte1

    with open(file_path, 'rb') as f:
        f.seek(byte1)
        data = f.read(length)

    response = Response(data,
                        206,
                        mimetype="application/epub+zip",
                        content_type="application/epub+zip",
                        direct_passthrough=True)
    response.headers.add("Content-Range", f"bytes {byte1}-{byte1 + length - 1}/{size}")
    response.headers.add("Accept-Ranges", "bytes")
    response.headers.add("Content-Length", str(length))
    return response


@epub_bp.route("/reader", methods=["GET"])
def reader():
    """Display Thorium reader with a specific EPUB."""
    book_url = request.args.get("book")
    if not book_url:
        return "Missing 'book' parameter", 400

    thorium_url = current_app.config["THORIUM_WEB_CLIENT_URL"]
    return render_template("thorium_reader.html", thorium_url=thorium_url, book_url=book_url)


@epub_bp.route("/selector", methods=["GET", "POST"])
def epub_selector():
    """Select an EPUB from stored publications and open in reader."""
    thorium_url = current_app.config["THORIUM_WEB_CLIENT_URL"]
    manifest_server = current_app.config["READIUM_CLI_ENDPOINT"].rstrip("/")
    publications = Publication.query.filter(Publication.epub_url.isnot(None)).all()

    epub_choices = []
    for pub in publications:
        encoded = encode_epub_url(pub.epub_url)
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


@epub_bp.route("/manage", methods=["GET", "POST"])
def manage_epubs():
    """Manage EPUBs - view and delete stored publications."""
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
        return redirect(url_for("epub.manage_epubs"))

    manifest_server = current_app.config["READIUM_CLI_ENDPOINT"].rstrip("/")
    thorium_url = current_app.config["THORIUM_WEB_CLIENT_URL"]

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
