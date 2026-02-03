# opds_tools/routes/odl_inventory.py

from flask import Blueprint, request, render_template, Response, flash, redirect, url_for, stream_with_context
import logging
import json
import queue
import threading

from opds_tools.util.odl_inventory_generator import (
    crawl_odl_feed_for_inventory,
    generate_odl_inventory_csv,
    generate_odl_inventory_excel
)

logger = logging.getLogger(__name__)

odl_inventory_bp = Blueprint("odl_inventory", __name__)

_last_odl_inventory = {
    'data': None,
    'feed_url': None,
    'stats': None,
    'errors': None,
    'max_pages': None,
    'in_progress': False
}


@odl_inventory_bp.route("/odl-inventory-report", methods=["GET", "POST"])
def odl_inventory_report_view():
    """
    Main view for generating ODL inventory reports.
    """
    global _last_odl_inventory

    inventory_data = []
    stats = {}
    errors = []
    feed_url = ""
    max_pages = None
    username = ""
    password = ""

    if request.method == "POST":
        action = request.form.get("action")

        if action == "clear":
            _last_odl_inventory = {
                'data': None,
                'feed_url': None,
                'stats': None,
                'errors': None,
                'max_pages': None,
                'in_progress': False
            }
            flash("Results cleared.", "info")
            return redirect(url_for('odl_inventory.odl_inventory_report_view'))

        feed_url = request.form.get("feed_url", "").strip()
        max_pages_input = request.form.get("max_pages", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

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
                "odl_inventory_report.html",
                inventory_data=[],
                stats={},
                errors=[],
                feed_url="",
                max_pages=None
            )

        if not (feed_url.startswith('http://') or feed_url.startswith('https://')):
            flash("Please provide a valid HTTP or HTTPS URL.", "danger")
            return render_template(
                "odl_inventory_report.html",
                inventory_data=[],
                stats={},
                errors=[],
                feed_url=feed_url,
                max_pages=max_pages
            )

        try:
            logger.info("Starting ODL inventory generation for: %s", feed_url)
            logger.info("Max pages: %s", max_pages or 'unlimited')

            _last_odl_inventory['in_progress'] = True

            result = crawl_odl_feed_for_inventory(
                feed_url,
                max_pages=max_pages,
                username=username,
                password=password
            )

            inventory_data = result['inventory']
            stats = result['stats']
            errors = result['errors']

            _last_odl_inventory['data'] = inventory_data
            _last_odl_inventory['feed_url'] = feed_url
            _last_odl_inventory['stats'] = stats
            _last_odl_inventory['errors'] = errors
            _last_odl_inventory['max_pages'] = max_pages
            _last_odl_inventory['in_progress'] = False

            logger.info("ODL inventory generation complete: %s publications found", len(inventory_data))

            if errors:
                flash(f"Completed with {len(errors)} errors. See details below.", "warning")
            else:
                flash(f"Successfully generated ODL inventory for {len(inventory_data)} publications!", "success")

        except Exception as e:
            logger.exception("Error during ODL inventory generation")
            flash(f"Error generating ODL inventory: {str(e)}", "danger")
            _last_odl_inventory['in_progress'] = False
            inventory_data = []
            stats = {}
            errors = [str(e)]

    else:
        if _last_odl_inventory['data']:
            inventory_data = _last_odl_inventory['data']
            stats = _last_odl_inventory['stats']
            errors = _last_odl_inventory['errors']
            feed_url = _last_odl_inventory['feed_url']
            max_pages = _last_odl_inventory['max_pages']
            # username and password kept as empty strings for security (don't re-display credentials)

    return render_template(
        "odl_inventory_report.html",
        inventory_data=inventory_data,
        stats=stats,
        errors=errors,
        feed_url=feed_url,
        max_pages=max_pages,
        username=username,
        password=password
    )


@odl_inventory_bp.route("/odl-inventory-report/download-csv", methods=["GET"])
def download_csv():
    global _last_odl_inventory

    if not _last_odl_inventory.get('data'):
        flash("No inventory data available. Please generate a report first.", "warning")
        return redirect(url_for('odl_inventory.odl_inventory_report_view'))

    try:
        csv_content = generate_odl_inventory_csv(_last_odl_inventory['data'])

        feed_url = _last_odl_inventory.get('feed_url', 'feed')
        try:
            from urllib.parse import urlparse
            domain = urlparse(feed_url).netloc.replace('.', '_')
            filename = f"odl_inventory_{domain}.csv"
        except:
            filename = "odl_inventory.csv"

        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    except Exception as e:
        logger.exception("Error generating ODL CSV")
        flash(f"Error generating CSV: {str(e)}", "danger")
        return redirect(url_for('odl_inventory.odl_inventory_report_view'))


@odl_inventory_bp.route("/odl-inventory-report/download-xml", methods=["GET"])
def download_xml():
    global _last_odl_inventory

    if not _last_odl_inventory.get('data'):
        flash("No inventory data available. Please generate a report first.", "warning")
        return redirect(url_for('odl_inventory.odl_inventory_report_view'))

    try:
        excel_content = generate_odl_inventory_excel(_last_odl_inventory['data'])

        feed_url = _last_odl_inventory.get('feed_url', 'feed')
        try:
            from urllib.parse import urlparse
            domain = urlparse(feed_url).netloc.replace('.', '_')
            filename = f"odl_inventory_{domain}.xlsx"
        except:
            filename = "odl_inventory.xlsx"

        return Response(
            excel_content,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    except Exception as e:
        logger.exception("Error generating ODL Excel")
        flash(f"Error generating Excel report: {str(e)}", "danger")
        return redirect(url_for('odl_inventory.odl_inventory_report_view'))


@odl_inventory_bp.route("/odl-inventory-report/stream", methods=["GET"])
def odl_inventory_report_stream():
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
        global _last_odl_inventory

        _last_odl_inventory['in_progress'] = True
        progress_queue = queue.Queue()
        completion_event = threading.Event()

        def run_crawl():
            try:
                def on_progress(event_type, data):
                    progress_queue.put({'type': event_type, **data})

                result = crawl_odl_feed_for_inventory(
                    feed_url,
                    max_pages=max_pages,
                    username=username,
                    password=password,
                    progress_callback=on_progress
                )

                # Store results in global cache - ensure this completes before signaling
                _last_odl_inventory['data'] = result['inventory']
                _last_odl_inventory['feed_url'] = feed_url
                _last_odl_inventory['stats'] = result['stats']
                _last_odl_inventory['errors'] = result['errors']
                _last_odl_inventory['max_pages'] = max_pages
                _last_odl_inventory['in_progress'] = False

                # Signal completion after all data is stored
                progress_queue.put({'type': 'complete', 'stats': result['stats'], 'error_count': len(result['errors'])})
                completion_event.set()

            except Exception as e:
                logger.exception("Error during ODL inventory generation")
                _last_odl_inventory['in_progress'] = False
                progress_queue.put({'type': 'error', 'message': str(e)})
                completion_event.set()

        thread = threading.Thread(target=run_crawl)
        thread.daemon = True
        thread.start()

        yield f"data: {json.dumps({'type': 'started', 'feed_url': feed_url})}\n\n"

        while True:
            try:
                event = progress_queue.get(timeout=60)
                yield f"data: {json.dumps(event)}\n\n"

                if event['type'] in ['complete', 'error']:
                    # Wait for thread completion flag to ensure data is persisted
                    completion_event.wait(timeout=5)
                    break

            except queue.Empty:
                yield ": keepalive\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )
