# routes/uploads.py
from flask import Blueprint, request, jsonify
from opds_tools.util.r2_client import upload_to_r2
from werkzeug.utils import secure_filename
import logging

logger = logging.getLogger(__name__)

uploads_bp = Blueprint("uploads", __name__)

@uploads_bp.route("/upload", methods=["POST"])
def upload_epub_file():
    if "epub_file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["epub_file"]
    filename = secure_filename(file.filename)
    key = f"epubs/{filename}"

    epub_url = upload_to_r2(file, key, content_type="application/epub+zip")
    if not epub_url:
        return jsonify({"error": "Upload failed"}), 500

    return jsonify({
        "message": "Upload successful",
        "epub_url": epub_url,
        "key": key
    })
