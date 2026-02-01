from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response, current_app
import os
import json
import html
import requests
import mimetypes
import tempfile
import base64
from urllib.parse import quote
from datetime import datetime
from io import BytesIO
from werkzeug.utils import secure_filename
from opds_tools.util.onix_to_opds import parse_onix_file, save_opds_feed
from opds_tools.util.onix_validator import validate_onix
from opds_tools.models import db, Publication, Catalog
from opds_tools.util.r2_client import upload_to_r2
from opds_tools.util.readium import (
    base64url_encode_s3_path,
    fetch_readium_manifest,
    check_readium_cli_available
)


onix_bp = Blueprint("onix", __name__, url_prefix="/onix")

UPLOAD_FOLDER = "opds_tools/content"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

UPLOAD_BASE = "content"

@onix_bp.route("/", methods=["GET", "POST"])
def upload_onix():
    opds_json = None
    pretty_json = None
    catalogs = Catalog.query.order_by(Catalog.title).all()
    onix_format = "reference"  # Default format
    validation_errors = []

    if request.method == "POST":
        file = request.files.get("onix_file")
        base_url = request.form.get("base_url") or "http://127.0.0.1:5000/uploads"
        acq_url = request.form.get("acq_url") or "http://127.0.0.1.5000/uploads"
        img_url = request.form.get("img_url") or "http://127.0.0.1:5000/uploads"
        onix_format = request.form.get("onix_format", "reference")

        if not file or file.filename == "":
            flash("No ONIX file selected.", "danger")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        xsd_filename = (
            "ONIX_BookProduct_3.0_short.xsd"
            if onix_format == "short"
            else "ONIX_BookProduct_3.0_reference.xsd"
        )
        xsd_path = os.path.join("opds_tools", "static", "schemas", "onix", xsd_filename)

        is_valid, validation_errors = validate_onix(file_path, xsd_path)
        if not is_valid:
            for err in validation_errors:
                flash(f"ONIX validation warning: {err}", "warning")

        try:
            messages = []
            feed, messages = parse_onix_file(
                file_path,
                base_url=base_url,
                acq_url=acq_url,
                img_url=img_url,
                messages=messages,
            )

            for category, msg in messages:
                flash(msg, category)

            output_path = os.path.join(UPLOAD_FOLDER, "opds_catalog.json")
            save_opds_feed(feed, output_path)
            session["opds_json"] = feed

            if request.form.get("store_in_db"):
                catalog_id = request.form.get("catalog_id")
                catalog_id = int(catalog_id) if catalog_id else None

                opds_publications = feed.get("publications", [])
                added_count = 0

                for pub in opds_publications:
                    metadata = pub.get("metadata", {})
                    links = pub.get("links", [])

                    new_pub = Publication(
                        title=metadata.get("title"),
                        author=", ".join(metadata.get("author", []))
                        if isinstance(metadata.get("author"), list)
                        else metadata.get("author"),
                        isbn=metadata.get("identifier"),
                        language=metadata.get("language"),
                        publisher=metadata.get("publisher"),
                        epub_url=next(
                            (l["href"] for l in links if l.get("type") == "application/epub+zip"),
                            None,
                        ),
                        cover_url=next(
                            (l["href"] for l in links if l.get("rel") == "http://opds-spec.org/image"),
                            None,
                        ),
                        manifest_url=next(
                            (l["href"] for l in links if l.get("rel") == "self"),
                            None,
                        ),
                        opds_json=pub,
                        from_onix=True,
                        catalog_id=catalog_id,
                    )

                    if new_pub.isbn:
                        existing = Publication.query.filter_by(isbn=new_pub.isbn).first()
                        if existing:
                            continue

                    db.session.add(new_pub)
                    added_count += 1

                db.session.commit()

                if catalog_id:
                    catalog = Catalog.query.get(catalog_id)
                    catalog_name = catalog.title if catalog else "Unknown catalog"
                    flash(f"📚 {added_count} publications added to catalog: {catalog_name}", "success")
                else:
                    flash(f"📚 {added_count} publications stored in the database.", "success")

            opds_json = feed
            flash("✅ ONIX file successfully parsed and OPDS catalog saved.", "success")

        except Exception as e:
            flash(f"❌ Failed to process ONIX file: {e}", "danger")

        pretty_json = json.dumps(opds_json, indent=2)
        pretty_json = html.unescape(pretty_json)

    return render_template(
        "onix.html",
        opds_json=opds_json,
        onix_format=onix_format,
        pretty_json=pretty_json,
        catalogs=catalogs,
    )


@onix_bp.route("/download-opds-json")
def download_opds_json():
    data = session.get("opds_json")
    if not data:
        flash("No OPDS data available to download.", "warning")
        return redirect(url_for("onix.upload_onix"))

    return Response(
        json.dumps(data, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=opds_catalog.json"},
    )


@onix_bp.route("/upload-content", methods=["GET", "POST"])
def upload_content():
    if request.method == "POST":
        source_type = request.form.get("source_type")
        filename = ""
        file_stream = None

        if source_type == "local":
            file = request.files.get("file")
            if not file or file.filename == "":
                flash("No local file selected.", "danger")
                return redirect(request.url)
            filename = secure_filename(file.filename)
            file_stream = file.stream

        elif source_type == "ftp":
            ftp_url = request.form.get("ftp_url")
            if not ftp_url:
                flash("No FTP URL provided.", "danger")
                return redirect(request.url)
            try:
                r = requests.get(ftp_url, timeout=10)
                r.raise_for_status()
                filename = os.path.basename(ftp_url)
                file_stream = BytesIO(r.content)
            except Exception as e:
                flash(f"❌ Failed to fetch FTP file: {e}", "danger")
                return redirect(request.url)

        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        r2_key = f"{catalog_id}/{filename}"
        public_url = upload_to_r2(file_stream, r2_key, content_type=content_type)

        if public_url:
            flash(f"✅ Uploaded to R2: {public_url}", "success")
        else:
            flash("❌ Upload failed.", "danger")

    return render_template("upload_file.html")


# NEW UPLOAD ROUTE USING READIUM CLI R2 AND DB


@onix_bp.route("/upload-epub", methods=["GET", "POST"])
def upload_epub():
    catalogs = Catalog.query.order_by(Catalog.title).all()

    if request.method == "POST":
        file = request.files.get("epub_file")
        catalog_id = request.form.get("catalog_id")

        base_url = current_app.config["R2_PUBLIC_URL"].rstrip("/")
        readium_endpoint = current_app.config["READIUM_CLI_ENDPOINT"]
        thorium_reader_base = current_app.config["THORIUM_WEB_CLIENT_URL"]
        bucket = current_app.config["R2_BUCKET"]

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

        # Upload EPUB to R2 under content/{catalog_id}/{filename}
        r2_key = f"content/{catalog_id}/{book_id}/{filename}"
        try:
            with open(epub_path, "rb") as f:
                upload_to_r2(f, r2_key, content_type="application/epub+zip")
        except Exception as e:
            os.unlink(epub_path)
            flash(f"❌ Failed to upload EPUB to R2: {e}", "danger")
            return render_template("upload_epub.html", catalogs=catalogs)

        # Public URL to EPUB
        epub_url = f"{base_url}/{catalog_id}/{book_id}/{filename}"

        # Check if Readium CLI is up
        if not check_readium_cli_available(readium_endpoint):
            os.unlink(epub_path)
            flash(f"⚠️ Readium CLI is not running at {readium_endpoint}", "danger")
            return render_template("upload_epub.html", catalogs=catalogs)

        # Encode s3 path and fetch manifest
        encoded_path = base64url_encode_s3_path(bucket, r2_key)
        print(f"📦 R2 bucket: {bucket}")
        print(f"📂 R2 key: {r2_key}")
        print(f"🔐 Encoded Path: {encoded_path}")
        print(f"🌐 Readium Manifest URL: {readium_endpoint.rstrip('/')}/{encoded_path}/manifest.json")

        manifest = fetch_readium_manifest(encoded_path)

        manifest_url = None
        reader_launch_url = None

        if manifest:
            # Upload manifest to R2 under content/{catalog_id}/{book_id}/manifest.json
            manifest_key = f"content/{catalog_id}/{book_id}/manifest.json"
            relative_manifest_path = manifest_key.removeprefix("content/")
            manifest_url = f"{base_url}/{relative_manifest_path.lstrip('/')}"

            manifest_bytes = BytesIO(json.dumps(manifest, indent=2).encode("utf-8"))
            try:
                upload_to_r2(manifest_bytes, manifest_key, content_type="application/webpub+json")
                flash("✅ Manifest uploaded to R2", "success")
            except Exception as e:
                flash(f"⚠️ Manifest generation succeeded but R2 upload failed: {e}", "warning")

            # Thorium Reader launch URL
            # Use folder path to manifest, not the file
            manifest_folder_url = manifest_url.rsplit('/', 1)[0] + "/"
            flash(f"🌐 Base url: {base_url}", "success")
            flash(f"📂 Manifest path: {manifest_key}", "success")
            flash(f"🌐 Thorium url: {thorium_reader_base}", "success")
            flash(f"🌐 Manifest url: {manifest_url}", "success")
            flash(f"🔐 Encoded Path to EPUB: {encoded_path}", "info")
            # Encode that path
            #encoded_manifest = base64.urlsafe_b64encode(manifest_folder_url.encode("utf-8")).decode("utf-8").rstrip("=")
            reader_launch_url = f"{thorium_reader_base}?book=http%3A%2F%2Flocalhost%3A15080%2F{encoded_path}/manifest.json"
            flash(F"🚀 Reader Launch URL: {reader_launch_url}", "info")

            # Save to database
            metadata = manifest.get("metadata", {})
            publication = Publication(
                title=metadata.get("title", book_id),
                identifier=metadata.get("identifier"),
                manifest_url=manifest_url,
                epub_url=epub_url,
                catalog_id=catalog_id,
                created_at=datetime.utcnow()
            )
            db.session.add(publication)
            db.session.commit()

        else:
            flash("❌ Failed to generate Readium Web Publication Manifest", "danger")

        os.unlink(epub_path)

        print(f"""
            📘 EPUB uploaded: <a href='{epub_url}' target='_blank'>{epub_url}</a><br>
            📄 Manifest: <a href='{manifest_url}' target='_blank'>{manifest_url}</a><br>
            🚀 Open in Thorium: <a href='{reader_launch_url}' target='_blank'>Read Now</a>
        """, "success")

        return render_template(
            "upload_epub.html",
            catalogs=catalogs,
            epub_url=epub_url,
            manifest_url=manifest_url,
            reader_launch_url=reader_launch_url)

    return render_template("upload_epub.html", catalogs=catalogs)
