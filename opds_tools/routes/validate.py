from flask import Blueprint, request, render_template, flash, Response, redirect, url_for
from opds_tools.util.palace_validator import validate_feed_url
import json
import io

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

validate_bp = Blueprint("validate", __name__)

# Simple in-memory cache for last validation results
_last_validation = {
    "results": None,
    "feed_url": None,
    "max_pages": None,
}



@validate_bp.route("/validate-feed", methods=["GET", "POST"])
def validate_feed_view():
    results = {}
    feed_url = ""
    max_pages = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "clear":
            _last_validation["results"] = None
            _last_validation["feed_url"] = None
            _last_validation["max_pages"] = None
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

        if download_json and _last_validation["results"]:
            return Response(
                json.dumps(_last_validation["results"], indent=2),
                mimetype="application/json",
                headers={"Content-Disposition": "attachment;filename=validation.json"}
            )

        if feed_url:
            results = validate_feed_url(feed_url, max_pages=max_pages)

            _last_validation["results"] = results
            _last_validation["feed_url"] = feed_url
            _last_validation["max_pages"] = max_pages

    return render_template("validate_feed.html", results=results, feed_url=feed_url, max_pages=max_pages)


@validate_bp.route("/validate-feed/pdf", methods=["GET"])
def validate_feed_pdf():
    """
    Generate a PDF report from the latest validation results.
    """
    if not _last_validation.get("results"):
        flash("No validation results available. Run a validation first.", "warning")
        return redirect(url_for("validate.validate_feed_view"))

    results = _last_validation["results"]
    feed_url = _last_validation.get("feed_url")
    max_pages = _last_validation.get("max_pages")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("OPDS Feed Validation Report", styles["Title"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"<b>Feed:</b> {feed_url or 'N/A'}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Max Pages:</b> {max_pages or 'All'}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    summary = results.get("summary", {})
    summary_data = [
        ["Pages Validated", summary.get("pages_validated", 0)],
        ["Publications Checked", summary.get("publication_count", 0)],
        ["Total Errors", summary.get("error_count", 0)],
    ]
    summary_table = Table(summary_data, hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(Paragraph("Summary", styles["Heading2"]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    feed_errors = results.get("feed_errors", [])
    if feed_errors:
        elements.append(Paragraph("Feed Page Errors", styles["Heading2"]))
        rows = [["URL", "Error"]]
        for err in feed_errors[:50]:
            rows.append([err.get("url", ""), err.get("error", "")])
        table = Table(rows, hAlign="LEFT", colWidths=[360, 180])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        if len(feed_errors) > 50:
            elements.append(Paragraph("Showing first 50 feed errors.", styles["Italic"]))
        elements.append(Spacer(1, 12))

    pub_errors = results.get("publication_errors", [])
    if pub_errors:
        elements.append(Paragraph("Publication Errors", styles["Heading2"]))
        rows = [["Title", "Identifier", "Error"]]
        for pub in pub_errors[:50]:
            rows.append([
                pub.get("title") or "Untitled",
                pub.get("identifier") or "",
                pub.get("error") or "",
            ])
        table = Table(rows, hAlign="LEFT", colWidths=[220, 140, 180])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        if len(pub_errors) > 50:
            elements.append(Paragraph("Showing first 50 publication errors.", styles["Italic"]))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment;filename=opds_validation_report.pdf"},
    )
