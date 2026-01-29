import os
import re
from flask import Blueprint, request, Response, send_file
import logging

logger = logging.getLogger(__name__)

epub_bp = Blueprint("epub", __name__)

@epub_bp.route("/books/<filename>")
def serve_epub(filename):
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
