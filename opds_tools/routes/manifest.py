# routes/manifest.py or part of your main app
import os
import logging
from flask import Blueprint, jsonify, request
from opds_tools.util.manifest import epub_to_manifest

logger = logging.getLogger(__name__)

manifest_bp = Blueprint('manifest', __name__)


@onix_bp.route("/upload-epub", methods=["GET", "POST"])
def upload_epub():
    import requests
    import base64
    from flask import current_app
    from opds_tools.models import Catalog  # Confirm import path
    catalogs = Catalog.query.order_by(Catalog.title).all()

    if request.method == "POST":
        file = request.files.get("epub_file")
        catalog_id = request.form.get("catalog_id")
        base_url = request.form.get("base_url", "").rstrip("/")

        readium_endpoint = current_app.config["READIUM_CLI_ENDPOINT"]
        thorium_reader_base = current_app.config["THORIUM_WEB_CLIENT_URL"]

        if not file or file.filename == "":
            flash("No EPUB file provided.", "danger")
            return render_template("upload_epub.html", catalogs=catalogs)

        if not catalog_id:
            flash("No catalog ID specified.", "danger")
            return render_template("upload_epub.html", catalogs=catalogs)

        filename = secure_filename(file.filename)
        book_id = os.path.splitext(filename)[0]
        epub_path = os.path.join(tempfile.gettempdir(), filename)
        file.save(epub_path)

        # Upload EPUB to R2
        r2_key = f"uploads/{catalog_id}/{book_id}.epub"
        with open(epub_path, "rb") as f:
            upload_to_r2(f, r2_key, content_type="application/epub+zip")

        epub_url = f"{base_url}/{r2_key}"

        # Fetch manifest from Readium CLI
        try:
            r = requests.get(readium_endpoint, params={"url": epub_url}, timeout=10)
            r.raise_for_status()
            manifest = r.json()
        except Exception as e:
            flash(f"Failed to fetch manifest from Readium CLI: {e}", "danger")
            os.unlink(epub_path)
            return render_template("upload_epub.html", catalogs=catalogs)

        # Upload manifest to R2
        manifest_key = f"uploads/{catalog_id}/{book_id}/manifest.json"
        manifest_url = f"{base_url}/{manifest_key}"
        manifest_bytes = BytesIO(json.dumps(manifest, indent=2).encode("utf-8"))
        upload_to_r2(manifest_bytes, manifest_key, content_type="application/webpub+json")

        # Thorium reader launch URL
        encoded_manifest = base64.urlsafe_b64encode(manifest_url.encode("utf-8")).decode("utf-8").rstrip("=")
        reader_launch_url = f"{thorium_reader_base}?book={encoded_manifest}"

        os.unlink(epub_path)

        flash(f"""
            📘 EPUB uploaded: <a href='{epub_url}' target='_blank'>{epub_url}</a><br>
            📄 Manifest: <a href='{manifest_url}' target='_blank'>{manifest_url}</a><br>
            🚀 Open in Thorium: <a href='{reader_launch_url}' target='_blank'>Read Now</a>
        """, "success")

        return render_template("upload_epub.html", catalogs=catalogs, epub_url=epub_url, manifest_url=manifest_url, reader_launch_url=reader_launch_url)

    return render_template("upload_epub.html", catalogs=catalogs)

