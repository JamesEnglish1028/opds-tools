from flask import Blueprint, request, render_template, flash
from opds_tools.util.palace_validator import validate_feed_url
import json
from flask import Response

validate_bp = Blueprint("validate", __name__)



@validate_bp.route("/validate-feed", methods=["GET", "POST"])
def validate_feed_view():
    results = {}
    feed_url = ""
    max_pages = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "clear":
            return render_template("validate_feed.html", results={}, feed_url="", max_pages=None)

        feed_url = request.form.get("feed_url")
        max_pages_input = request.form.get("max_pages")

        if max_pages_input:
            try:
                max_pages = int(max_pages_input)
                if max_pages < 1:
                    max_pages = None
            except ValueError:
                max_pages = None

        download_json = request.form.get("download_json")
        if feed_url:
            results = validate_feed_url(feed_url, max_pages=max_pages)
            if download_json:
                return Response(
                    json.dumps(results, indent=2),
                    mimetype="application/json",
                    headers={"Content-Disposition": "attachment;filename=validation.json"}
                )

    return render_template("validate_feed.html", results=results, feed_url=feed_url, max_pages=max_pages)
