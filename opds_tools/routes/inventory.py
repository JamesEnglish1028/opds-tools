# opds_tools/routes/inventory.py

from flask import Blueprint, request, render_template, Response, flash, redirect, url_for, stream_with_context
import logging
import json
import queue
import threading

from opds_tools.util.inventory_generator import (
    crawl_feed_for_inventory,
    generate_inventory_csv,
    generate_inventory_excel
)

logger = logging.getLogger(__name__)

inventory_bp = Blueprint("inventory", __name__)

# Simple in-memory cache for the last inventory generation
# In production, you'd use Redis or a database
_last_inventory = {
    'data': None,
    'feed_url': None,
    'stats': None,
    'errors': None,
    'max_pages': None,
    'in_progress': False
}


@inventory_bp.route("/inventory-report", methods=["GET", "POST"])
def inventory_report_view():
    """
    Main view for generating OPDS inventory reports.
    Allows users to input a feed URL and generate CSV/XML reports.
    """
    global _last_inventory
    
    inventory_data = []
    stats = {}
    errors = []
    feed_url = ""
    max_pages = None

    if request.method == "POST":
        action = request.form.get("action")

        # Handle clear action
        if action == "clear":
            _last_inventory = {
                'data': None,
                'feed_url': None,
                'stats': None,
                'errors': None,
                'max_pages': None,
                'in_progress': False
            }
            flash("Results cleared.", "info")
            return redirect(url_for('inventory.inventory_report_view'))

        # Handle generate action
        feed_url = request.form.get("feed_url", "").strip()
        max_pages_input = request.form.get("max_pages", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # Parse max_pages
        if max_pages_input:
            try:
                max_pages = int(max_pages_input)
                if max_pages < 1:
                    max_pages = None
            except ValueError:
                flash("Invalid max pages value. Using unlimited.", "warning")
                max_pages = None

        if not feed_url:
            flash("Please provide a feed URL.", "danger")
            return render_template(
                "inventory_report.html",
                inventory_data=[],
                stats={},
                errors=[],
                feed_url="",
                max_pages=None
            )

        # Validate URL
        if not (feed_url.startswith('http://') or feed_url.startswith('https://')):
            flash("Please provide a valid HTTP or HTTPS URL.", "danger")
            return render_template(
                "inventory_report.html",
                inventory_data=[],
                stats={},
                errors=[],
                feed_url=feed_url,
                max_pages=max_pages
            )

        try:
            logger.info(f"Starting inventory generation for: {feed_url}")
            logger.info(f"Max pages: {max_pages or 'unlimited'}")
            
            _last_inventory['in_progress'] = True
            
            # Crawl the feed
            auth = None
            if username and password:
                auth = (username, password)
            
            result = crawl_feed_for_inventory(
                feed_url,
                max_pages=max_pages,
                username=username,
                password=password
            )
            
            inventory_data = result['inventory']
            stats = result['stats']
            errors = result['errors']
            
            # Cache results
            _last_inventory['data'] = inventory_data
            _last_inventory['feed_url'] = feed_url
            _last_inventory['stats'] = stats
            _last_inventory['errors'] = errors
            _last_inventory['max_pages'] = max_pages
            _last_inventory['in_progress'] = False
            
            logger.info(f"Inventory generation complete: {len(inventory_data)} publications found")
            
            if errors:
                flash(f"Completed with {len(errors)} errors. See details below.", "warning")
            else:
                flash(f"Successfully generated inventory for {len(inventory_data)} publications!", "success")
            
        except Exception as e:
            logger.exception("Error during inventory generation")
            flash(f"Error generating inventory: {str(e)}", "danger")
            _last_inventory['in_progress'] = False
            inventory_data = []
            stats = {}
            errors = [str(e)]

    else:
        # GET request - show cached results if available
        if _last_inventory['data']:
            inventory_data = _last_inventory['data']
            stats = _last_inventory['stats']
            errors = _last_inventory['errors']
            feed_url = _last_inventory['feed_url']
            max_pages = _last_inventory['max_pages']

    return render_template(
        "inventory_report.html",
        inventory_data=inventory_data,
        stats=stats,
        errors=errors,
        feed_url=feed_url,
        max_pages=max_pages
    )


@inventory_bp.route("/inventory-report/download-csv", methods=["GET"])
def download_csv():
    """
    Download inventory report as CSV file.
    """
    global _last_inventory
    
    if not _last_inventory.get('data'):
        flash("No inventory data available. Please generate a report first.", "warning")
        return redirect(url_for('inventory.inventory_report_view'))
    
    try:
        csv_content = generate_inventory_csv(_last_inventory['data'])
        
        # Generate filename
        feed_url = _last_inventory.get('feed_url', 'feed')
        # Extract domain or use generic name
        try:
            from urllib.parse import urlparse
            domain = urlparse(feed_url).netloc.replace('.', '_')
            filename = f"opds_inventory_{domain}.csv"
        except:
            filename = "opds_inventory.csv"
        
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    
    except Exception as e:
        logger.exception("Error generating CSV")
        flash(f"Error generating CSV: {str(e)}", "danger")
        return redirect(url_for('inventory.inventory_report_view'))


@inventory_bp.route("/inventory-report/download-xml", methods=["GET"])
def download_xml():
    """
    Download inventory report as Excel (.xlsx) file.
    """
    global _last_inventory
    
    if not _last_inventory.get('data'):
        flash("No inventory data available. Please generate a report first.", "warning")
        return redirect(url_for('inventory.inventory_report_view'))
    
    try:
        excel_content = generate_inventory_excel(_last_inventory['data'])
        
        # Generate filename
        feed_url = _last_inventory.get('feed_url', 'feed')
        # Extract domain or use generic name
        try:
            from urllib.parse import urlparse
            domain = urlparse(feed_url).netloc.replace('.', '_')
            filename = f"opds_inventory_{domain}.xlsx"
        except:
            filename = "opds_inventory.xlsx"
        
        return Response(
            excel_content,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    
    except Exception as e:
        logger.exception("Error generating Excel")
        flash(f"Error generating Excel report: {str(e)}", "danger")
        return redirect(url_for('inventory.inventory_report_view'))


@inventory_bp.route("/inventory-report/stream", methods=["GET"])
def inventory_report_stream():
    """
    Stream progress updates for inventory generation using Server-Sent Events.
    """
    feed_url = request.args.get("feed_url", "").strip()
    max_pages_input = request.args.get("max_pages", "").strip()
    username = request.args.get("username", "").strip()
    password = request.args.get("password", "").strip()
    
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
        global _last_inventory
        
        _last_inventory['in_progress'] = True
        
        # Create a queue for progress events
        progress_queue = queue.Queue()
        
        def run_crawl():
            """Run crawl in background thread."""
            try:
                def on_progress(event_type, data):
                    progress_queue.put({'type': event_type, **data})
                
                result = crawl_feed_for_inventory(
                    feed_url,
                    max_pages=max_pages,
                    username=username,
                    password=password,
                    progress_callback=on_progress
                )
                
                # Cache results
                _last_inventory['data'] = result['inventory']
                _last_inventory['feed_url'] = feed_url
                _last_inventory['stats'] = result['stats']
                _last_inventory['errors'] = result['errors']
                _last_inventory['max_pages'] = max_pages
                _last_inventory['in_progress'] = False
                
                # Signal completion
                progress_queue.put({'type': 'complete', 'stats': result['stats'], 'error_count': len(result['errors'])})
                
            except Exception as e:
                logger.exception("Error during inventory generation")
                _last_inventory['in_progress'] = False
                progress_queue.put({'type': 'error', 'message': str(e)})
        
        # Start background thread
        thread = threading.Thread(target=run_crawl)
        thread.daemon = True
        thread.start()
        
        # Send initial status
        yield f"data: {json.dumps({'type': 'started', 'feed_url': feed_url})}\n\n"
        
        # Stream events from queue
        while True:
            try:
                event = progress_queue.get(timeout=60)  # 60 second timeout
                yield f"data: {json.dumps(event)}\n\n"
                
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
