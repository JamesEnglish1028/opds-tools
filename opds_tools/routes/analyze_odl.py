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

from opds_tools.util.odl_analyzer import analyze_odl_feed

odl_analyze_bp = Blueprint("odl_analyze", __name__)

# Simple in-memory cache for the last analysis result
_last_odl_analysis = {
    'results': None,
    'feed_url': None,
    'max_pages': None,
    'in_progress': False,
    'started_at': None,
}


@odl_analyze_bp.route("/analyze-odl-feed", methods=["GET", "POST"])
def analyze_odl_feed_view():
    """
    Analyze ODL feed for format, media type, and DRM scheme statistics.
    """
    global _last_odl_analysis
    
    results = {}
    feed_url = ""
    max_pages = None
    username = ""
    password = ""

    if request.method == "POST":
        action = request.form.get("action")

        if action == "clear":
            _last_odl_analysis = {'results': None, 'feed_url': None, 'max_pages': None, 'in_progress': False, 'started_at': None}
            return render_template("analyze_odl_feed.html", results={}, feed_url="", max_pages=None, username="", password="")

        feed_url = request.form.get("feed_url")
        username = request.form.get("username") or None
        password = request.form.get("password") or None
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
        if download_json and _last_odl_analysis['results']:
            print(f"📥 Serving JSON download from cached results")
            return Response(
                json.dumps(_last_odl_analysis['results'], indent=2),
                mimetype="application/json",
                headers={"Content-Disposition": "attachment;filename=odl_feed_analysis.json"}
            )
        
        # If not download, they must want analysis - use streaming
        if feed_url:
            # Redirect to streaming endpoint
            params = []
            params.append(f"feed_url={request.form.get('feed_url')}")
            if max_pages_input:
                params.append(f"max_pages={max_pages_input}")
            if username:
                params.append(f"username={username}")
            if password:
                params.append(f"password={password}")
            query_string = "&".join(params)
            return redirect(url_for("odl_analyze.analyze_odl_feed_view_direct", **dict([tuple(p.split('=')) for p in params])))

    else:
        # GET request - show cached results if available
        if _last_odl_analysis['results']:
            print(f"📋 Displaying cached ODL analysis results")
            results = _last_odl_analysis['results']
            feed_url = _last_odl_analysis['feed_url']
            max_pages = _last_odl_analysis['max_pages']
        elif _last_odl_analysis['in_progress']:
            print(f"⏳ ODL analysis still in progress...")
            feed_url = _last_odl_analysis['feed_url'] or ""
            max_pages = _last_odl_analysis['max_pages']
            results = {"in_progress": True, "summary": {}}

    print(f"🎨 Rendering ODL template with results...")
    response = render_template("analyze_odl_feed.html", results=results, feed_url=feed_url, max_pages=max_pages, username=username, password=password)
    print(f"✅ Template rendered successfully, sending response to browser")
    return response


@odl_analyze_bp.route("/analyze-odl-feed/direct", methods=["GET"])
def analyze_odl_feed_view_direct():
    """
    Direct GET view for displaying results from GET request with query parameters.
    """
    global _last_odl_analysis
    
    # Show cached results
    results = {}
    feed_url = ""
    max_pages = None
    username = ""
    password = ""
    
    if _last_odl_analysis['results']:
        results = _last_odl_analysis['results']
        feed_url = _last_odl_analysis['feed_url']
        max_pages = _last_odl_analysis['max_pages']
    
    return render_template("analyze_odl_feed.html", results=results, feed_url=feed_url, max_pages=max_pages, username=username, password=password)


@odl_analyze_bp.route("/analyze-odl-feed/stream", methods=["GET"])
def analyze_odl_feed_stream():
    """
    Stream progress updates for ODL feed analysis using Server-Sent Events.
    """
    feed_url = request.args.get("feed_url", "").strip()
    max_pages_input = request.args.get("max_pages", "").strip()
    username = request.args.get("username", "").strip() or None
    password = request.args.get("password", "").strip() or None
    
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
        global _last_odl_analysis
        
        _last_odl_analysis['in_progress'] = True
        _last_odl_analysis['started_at'] = time.time()
        
        # Create a queue for progress events
        progress_queue = queue.Queue()
        
        def run_analysis():
            """Run analysis in background thread."""
            try:
                def on_progress(event_type, data):
                    progress_queue.put({'type': event_type, **data})
                
                # Prepare auth tuple if provided
                auth = (username, password) if username and password else None
                
                results = analyze_odl_feed(
                    feed_url,
                    auth=auth,
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
                _last_odl_analysis['results'] = results
                _last_odl_analysis['feed_url'] = feed_url
                _last_odl_analysis['max_pages'] = max_pages
                _last_odl_analysis['in_progress'] = False
                _last_odl_analysis['started_at'] = None
                
                # Signal completion
                progress_queue.put({
                    'type': 'complete',
                    'summary': results.get('summary', {}),
                    'total_publications': results.get('summary', {}).get('total_publications', 0),
                    'pages_analyzed': results.get('summary', {}).get('pages_analyzed', 0),
                    'unique_media_types': results.get('summary', {}).get('unique_media_types', 0),
                    'unique_drm_schemes': results.get('summary', {}).get('unique_drm_schemes', 0)
                })
                
            except Exception as e:
                print(f"Error during ODL analysis: {e}")
                import traceback
                traceback.print_exc()
                _last_odl_analysis['in_progress'] = False
                _last_odl_analysis['started_at'] = None
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


@odl_analyze_bp.route("/analyze-odl-feed/pdf", methods=["GET"])
def analyze_odl_feed_pdf():
    """
    Generate a PDF report from the latest ODL analysis results.
    """
    global _last_odl_analysis

    if not _last_odl_analysis.get("results"):
        flash("No analysis results available. Run an analysis first.", "warning")
        return redirect(url_for("odl_analyze.analyze_odl_feed_view"))

    results = _last_odl_analysis["results"]
    feed_url = _last_odl_analysis.get("feed_url")
    max_pages = _last_odl_analysis.get("max_pages")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("ODL Feed Analysis Report", styles["Title"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"<b>Feed:</b> {feed_url or 'N/A'}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Max Pages:</b> {max_pages or 'All'}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    summary = results.get("summary", {})
    media_type_counts = summary.get("media_type_counts", {})
    drm_scheme_counts = summary.get("drm_scheme_counts", {})
    drm_combination_counts = summary.get("drm_combination_counts", {})
    pub_type_counts = summary.get("publication_type_counts", {})
    pub_type_percentages = summary.get("publication_type_percentages", {})
    
    summary_data = [
        ["Total Publications", summary.get("total_publications", 0)],
        ["Pages Analyzed", summary.get("pages_analyzed", 0)],
        ["Pages With Errors", summary.get("pages_with_errors", 0)],
        ["Unique Formats (MIME Types)", summary.get("unique_formats", 0)],
        ["Unique Media Types", summary.get("unique_media_types", 0)],
        ["Unique DRM Schemes", summary.get("unique_drm_schemes", 0)],
        ["Unique DRM Combinations", summary.get("unique_drm_combinations", 0)],
    ]
    
    summary_table = Table(summary_data, hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(Paragraph("Summary", styles["Heading2"]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # Publication Types
    if pub_type_counts:
        elements.append(Paragraph("Publication Types", styles["Heading2"]))
        type_rows = [["Type", "Count", "% of Collection"]]
        for pub_type in sorted(pub_type_counts.keys()):
            count = pub_type_counts[pub_type]
            pct = pub_type_percentages.get(pub_type, 0)
            type_rows.append([pub_type, count, f"{pct}%"])
        type_table = Table(type_rows, hAlign="LEFT")
        type_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(type_table)
        elements.append(Spacer(1, 12))

    # Media Types
    if media_type_counts:
        elements.append(Paragraph("Media Type Distribution", styles["Heading2"]))
        media_rows = [["Media Type", "Count", "% of Collection"]]
        total_pubs = summary.get("total_publications", 0) or 1
        for media_type in sorted(media_type_counts.keys()):
            count = media_type_counts[media_type]
            pct = (count / total_pubs) * 100
            media_rows.append([media_type, count, f"{pct:.1f}%"])
        media_table = Table(media_rows, hAlign="LEFT")
        media_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(media_table)
        elements.append(Spacer(1, 12))

    # DRM Schemes (All Instances)
    if drm_scheme_counts:
        elements.append(Paragraph("DRM Scheme Distribution (All Instances)", styles["Heading2"]))
        elements.append(Paragraph(
            "<i>Note: Publications with multiple DRM types are counted multiple times.</i>",
            styles["Normal"]
        ))
        elements.append(Spacer(1, 6))
        drm_rows = [["DRM Scheme", "Count", "% of Publications"]]
        total_pubs = summary.get("total_publications", 0) or 1
        for drm_scheme in sorted(drm_scheme_counts.keys()):
            count = drm_scheme_counts[drm_scheme]
            pct = (count / total_pubs) * 100
            drm_rows.append([drm_scheme, count, f"{pct:.1f}%"])
        drm_table = Table(drm_rows, hAlign="LEFT")
        drm_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(drm_table)
        elements.append(Spacer(1, 12))

    # DRM Protection Combinations (By Publication)
    if drm_combination_counts:
        elements.append(Paragraph("DRM Protection Combinations (By Publication)", styles["Heading2"]))
        elements.append(Paragraph(
            "<i>Note: Each publication is counted exactly once by its specific DRM configuration.</i>",
            styles["Normal"]
        ))
        elements.append(Spacer(1, 6))
        combo_rows = [["DRM Configuration", "Publications", "% of Collection", "Type"]]
        total_pubs = summary.get("total_publications", 0) or 1
        
        # Sort combinations: No DRM first, then single DRM, then multiple DRM, then Unknown
        def sort_key(item):
            combo = item[0]
            if combo == "No DRM":
                return (0, combo)
            elif combo == "Unknown DRM":
                return (3, combo)
            elif "&" in combo:
                return (2, combo)
            else:
                return (1, combo)
        
        for drm_combo in sorted(drm_combination_counts.items(), key=sort_key):
            combo_name, count = drm_combo
            pct = (count / total_pubs) * 100
            
            # Determine type label
            if "&" in combo_name:
                type_label = "Multiple DRM"
            elif combo_name == "No DRM":
                type_label = "DRM-free"
            elif combo_name == "Unknown DRM":
                type_label = "Unknown"
            else:
                type_label = "Single DRM"
            
            combo_rows.append([combo_name, count, f"{pct:.1f}%", type_label])
        
        combo_table = Table(combo_rows, hAlign="LEFT")
        combo_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            # Highlight multiple DRM rows
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
        ]))
        
        # Add subtle background color for multiple DRM rows
        for idx, (combo_name, count) in enumerate(drm_combination_counts.items(), start=1):
            if "&" in combo_name:
                combo_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, idx), (-1, idx), colors.Color(1, 0.9, 0.9)),
                ]))
        
        elements.append(combo_table)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment;filename=odl_analysis_report.pdf"},
    )
