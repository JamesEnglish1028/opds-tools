from flask import Blueprint, request, render_template, Response, redirect, url_for, flash, stream_with_context
import json
import time
import io
import queue
import threading

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from opds_tools.util.feed_analyzer import analyze_feed_url

analyze_bp = Blueprint("analyze", __name__)

# Simple in-memory cache for the last analysis result
# In production, you'd use Redis or a database
_last_analysis = {
    'results': None,
    'feed_url': None,
    'max_pages': None,
    'in_progress': False,
    'started_at': None,
}


@analyze_bp.route("/analyze-feed", methods=["GET", "POST"])
def analyze_feed_view():
    """
    Analyze OPDS feed for format and DRM statistics.
    """
    global _last_analysis
    
    results = {}
    feed_url = ""
    max_pages = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "clear":
            _last_analysis = {'results': None, 'feed_url': None, 'max_pages': None, 'in_progress': False, 'started_at': None}
            return render_template("analyze_feed.html", results={}, feed_url="", max_pages=None)

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
        
        # Handle JSON download from cached results
        if download_json and _last_analysis['results']:
            print(f"📥 Serving JSON download from cached results")
            return Response(
                json.dumps(_last_analysis['results'], indent=2),
                mimetype="application/json",
                headers={"Content-Disposition": "attachment;filename=feed_analysis.json"}
            )
        
        if feed_url:
            # Run analysis
            try:
                print(f"\n🔬 Starting analysis for: {feed_url}")
                print(f"   Max pages: {max_pages or 'unlimited'}")
                print(f"   ⏱️  This may take several minutes for large feeds...")

                _last_analysis['in_progress'] = True
                _last_analysis['started_at'] = time.time()
                _last_analysis['feed_url'] = feed_url
                _last_analysis['max_pages'] = max_pages
                _last_analysis['results'] = None
                
                results = analyze_feed_url(feed_url, max_pages=max_pages)
                
                print(f"\n✅ Analysis complete!")
                print(f"   Total publications: {results.get('summary', {}).get('total_publications', 0)}")
                print(f"   Pages analyzed: {results.get('summary', {}).get('pages_analyzed', 0)}")
                print(f"   Format combinations found: {len(results.get('format_combo_stats', []))}")
                
                # Limit page_stats for template rendering to avoid massive HTML
                # Only show first 20 and last 5 pages in detail
                page_stats_count = len(results.get('page_stats', []))
                if page_stats_count > 25:
                    print(f"   ⚠️  Limiting page details display: {page_stats_count} pages total, showing first 20 + last 5")
                    page_stats = results.get('page_stats', [])
                    results['page_stats_display'] = page_stats[:20] + page_stats[-5:]
                    results['page_stats_truncated'] = True
                    results['page_stats_total'] = page_stats_count
                else:
                    results['page_stats_display'] = results.get('page_stats', [])
                    results['page_stats_truncated'] = False
                
                # Cache the results
                _last_analysis['results'] = results
                _last_analysis['feed_url'] = feed_url
                _last_analysis['max_pages'] = max_pages
                _last_analysis['in_progress'] = False
                _last_analysis['started_at'] = None
                
            except Exception as e:
                print(f"\n❌ Error during analysis: {str(e)}")
                import traceback
                traceback.print_exc()
                results = {
                    "error": str(e),
                    "summary": {
                        "total_publications": 0,
                        "pages_analyzed": 0,
                        "pages_with_errors": 0
                    }
                }
                results['page_stats_display'] = []
                results['page_stats_truncated'] = False
                _last_analysis['in_progress'] = False
                _last_analysis['started_at'] = None

    else:
        # GET request - show cached results if available
        if _last_analysis['results']:
            print(f"📋 Displaying cached analysis results")
            results = _last_analysis['results']
            feed_url = _last_analysis['feed_url']
            max_pages = _last_analysis['max_pages']
        elif _last_analysis['in_progress']:
            print(f"⏳ Analysis still in progress...")
            feed_url = _last_analysis['feed_url'] or ""
            max_pages = _last_analysis['max_pages']
            results = {"in_progress": True, "summary": {}}

    print(f"🎨 Rendering template with results...")
    response = render_template("analyze_feed.html", results=results, feed_url=feed_url, max_pages=max_pages)
    print(f"✅ Template rendered successfully, sending response to browser")
    return response


@analyze_bp.route("/analyze-feed/pdf", methods=["GET"])
def analyze_feed_pdf():
    """
    Generate a PDF report from the latest analysis results.
    """
    global _last_analysis

    if not _last_analysis.get("results"):
        flash("No analysis results available. Run an analysis first.", "warning")
        return redirect(url_for("analyze.analyze_feed_view"))

    results = _last_analysis["results"]
    feed_url = _last_analysis.get("feed_url")
    max_pages = _last_analysis.get("max_pages")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("OPDS Feed Analysis Report", styles["Title"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"<b>Feed:</b> {feed_url or 'N/A'}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Max Pages:</b> {max_pages or 'All'}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    summary = results.get("summary", {})
    summary_data = [
        ["Total Publications", summary.get("total_publications", 0)],
        ["Pages Analyzed", summary.get("pages_analyzed", 0)],
        ["Pages With Errors", summary.get("pages_with_errors", 0)],
        ["Unique Formats", summary.get("unique_formats", 0)],
        ["Unique Format Combinations", summary.get("unique_format_combinations", 0)],
        ["Unique DRM Types", summary.get("unique_drm_types", 0)],
    ]
    summary_table = Table(summary_data, hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(Paragraph("Summary", styles["Heading2"]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Format Availability (Combinations)", styles["Heading2"]))
    combo_rows = [["Combination", "Count", "% of Collection"]]
    for item in results.get("format_combo_stats", []):
        combo_rows.append([item.get("combination"), item.get("count"), f"{item.get('percentage', 0)}%"])
    combo_table = Table(combo_rows, hAlign="LEFT")
    combo_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(combo_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Format Distribution", styles["Heading2"]))
    format_rows = [["Format", "Count", "% of Collection"]]
    total_pubs = summary.get("total_publications", 0) or 1
    for fmt, count in results.get("format_counts", {}).items():
        pct = (count / total_pubs) * 100
        format_rows.append([fmt, count, f"{pct:.1f}%"])
    format_table = Table(format_rows, hAlign="LEFT")
    format_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(format_table)
    elements.append(Spacer(1, 12))

    drm_counts = results.get("drm_counts", {})
    if drm_counts:
        elements.append(Paragraph("DRM Distribution (EPUB Only)", styles["Heading2"]))
        drm_rows = [["DRM Type", "Count", "% of EPUBs", "% of Collection"]]
        epub_total = results.get("format_counts", {}).get("EPUB", 0) or 1
        for drm, count in drm_counts.items():
            if drm == "N/A":
                continue
            pct_epub = (count / epub_total) * 100
            pct_all = (count / total_pubs) * 100
            drm_rows.append([drm, count, f"{pct_epub:.1f}%", f"{pct_all:.1f}%"])
        drm_table = Table(drm_rows, hAlign="LEFT")
        drm_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(drm_table)
        elements.append(Spacer(1, 12))

    elements.append(Paragraph("Format + DRM Distribution", styles["Heading2"]))
    combined_rows = [["Format", "DRM", "Count", "% of Collection"]]
    for item in results.get("combined_stats", []):
        combined_rows.append([
            item.get("format"),
            item.get("drm"),
            item.get("count"),
            f"{item.get('percentage', 0)}%",
        ])
    combined_table = Table(combined_rows, hAlign="LEFT")
    combined_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(combined_table)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment;filename=opds_analysis_report.pdf"},
    )


@analyze_bp.route("/analyze-feed/stream", methods=["GET"])
def analyze_feed_stream():
    """
    Stream progress updates for feed analysis using Server-Sent Events.
    """
    feed_url = request.args.get("feed_url", "").strip()
    max_pages_input = request.args.get("max_pages", "").strip()
    
    max_pages = None
    if max_pages_input:
        try:
            max_pages = int(max_pages_input)
            if max_pages < 1:
                max_pages = None
        except ValueError:
            max_pages = None
    
    def generate():
        """Generator for Server-Sent Events."""
        global _last_analysis
        
        _last_analysis['in_progress'] = True
        _last_analysis['started_at'] = time.time()
        
        # Create a queue for progress events
        progress_queue = queue.Queue()
        
        def run_analysis():
            """Run analysis in background thread."""
            try:
                def on_progress(event_type, data):
                    progress_queue.put({'type': event_type, **data})
                
                results = analyze_feed_url(
                    feed_url,
                    max_pages=max_pages,
                    progress_callback=on_progress
                )
                
                # Limit page_stats for template rendering
                page_stats_count = len(results.get('page_stats', []))
                if page_stats_count > 25:
                    page_stats = results.get('page_stats', [])
                    results['page_stats_display'] = page_stats[:20] + page_stats[-5:]
                    results['page_stats_truncated'] = True
                    results['page_stats_total'] = page_stats_count
                else:
                    results['page_stats_display'] = results.get('page_stats', [])
                    results['page_stats_truncated'] = False
                
                # Cache results
                _last_analysis['results'] = results
                _last_analysis['feed_url'] = feed_url
                _last_analysis['max_pages'] = max_pages
                _last_analysis['in_progress'] = False
                _last_analysis['started_at'] = None
                
                # Signal completion
                progress_queue.put({
                    'type': 'complete',
                    'summary': results.get('summary', {}),
                    'total_publications': results.get('summary', {}).get('total_publications', 0),
                    'pages_analyzed': results.get('summary', {}).get('pages_analyzed', 0)
                })
                
            except Exception as e:
                print(f"Error during analysis: {e}")
                import traceback
                traceback.print_exc()
                _last_analysis['in_progress'] = False
                _last_analysis['started_at'] = None
                progress_queue.put({'type': 'error', 'message': str(e)})
        
        # Start background thread
        thread = threading.Thread(target=run_analysis)
        thread.daemon = True
        thread.start()
        
        # Stream events from queue
        while True:
            try:
                event = progress_queue.get(timeout=60)  # 60 second timeout
                event_json = json.dumps(event)
                yield f"data: {event_json}\n\n"
                
                # Stop if complete or error
                if event['type'] in ['complete', 'error']:
                    break
                    
            except queue.Empty:
                # Send keepalive
                yield f": keepalive\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )
