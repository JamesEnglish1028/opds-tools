from flask import Blueprint, render_template, redirect, url_for, request, session, flash, jsonify
import requests
import urllib.parse
import logging
from urllib.parse import urlparse, parse_qs
from opds_tools.util.parser import extract_publications_with_odl
from opds_tools.util.validation import validate_opds_feed
from opds_tools.models import db, ODLFeed


logger = logging.getLogger(__name__)

odl_utilities_bp = Blueprint(
    'odl_utilities', __name__,
    template_folder='templates',
    url_prefix='/odl-utilities'
)

@odl_utilities_bp.route('', methods=['GET', 'POST'])
def odl_utilities():
    """
    Display the ODL Utilities page. On any request with 'feed_url',
    fetch (with auth), validate, extract, parse pagination links, and render.
    """
    # Handle auth: store on POST, reuse from session
    if request.method == 'POST' and request.form.get('feed_url'):
        session['odl_auth'] = {
            'username': request.form.get('username') or None,
            'password': request.form.get('password') or None
        }
        # Redirect to GET with parameters
        params = {
            'feed_url': request.form['feed_url'],
            'skip_validation': request.form.get('skip_validation')
        }
        return redirect(url_for('odl_utilities.odl_utilities', **params))

    # GET flow
    feed_url = request.args.get('feed_url')
    skip_validation = bool(request.args.get('skip_validation'))
    auth_info = session.get('odl_auth', {})
    auth = (auth_info.get('username'), auth_info.get('password')) if auth_info else None

    if not auth or not auth[0]:
        feed_record = ODLFeed.query.filter_by(url=feed_url).first()
        if feed_record and feed_record.username:
            auth = (feed_record.username, feed_record.password)

    publications = []
    navigation_links = {}

    if feed_url:
        logger.info(f"Fetching feed URL={feed_url}")
        try:
            r = requests.get(feed_url, auth=auth, timeout=10)
            r.raise_for_status()
            data = r.json()

            # Validation
            if not skip_validation:
                valid, errors = validate_opds_feed(data)
                if not valid:
                    for err in errors:
                        flash(err, 'danger')
                    logger.warning(f"Validation errors: {len(errors)}")
                else:
                    flash('Validation passed.', 'success')
            else:
                flash('Validation skipped.', 'info')

            # Extraction
            publications = extract_publications_with_odl(data)

            # Pagination links
            links = {link.get('rel'): link.get('href') for link in data.get('links', [])}
            orig_qs = parse_qs(urlparse(feed_url).query)
            token = orig_qs.get('token', [None])[0]

            def ensure_token(url):
                if not url:
                    return url
                p = urlparse(url)
                qs = parse_qs(p.query)
                if token and 'token' not in qs:
                    qs['token'] = token
                new_query = '&'.join(f"{k}={v[0]}" for k, v in qs.items())
                return p._replace(query=new_query).geturl()

            navigation_links = {
                'first': ensure_token(links.get('first')),
                'previous': ensure_token(links.get('prev') or links.get('previous')),
                'next': ensure_token(links.get('next')),
                'last': ensure_token(links.get('last'))
            }

        except requests.HTTPError as e:
            flash(f"Error fetching feed: {e}", 'danger')
            logger.error(e)
        except Exception as e:
            flash(f"Unexpected error: {e}", 'danger')
            logger.error(e)

    # also fetch the saved feeds for the “My List” tab
    odl_feeds = ODLFeed.query.order_by(ODLFeed.name).all()

    return render_template(
        'odl_utilities.html',
        publications=publications,
        navigation_links=navigation_links,
        odl_feeds=odl_feeds
    )


@odl_utilities_bp.route('/clear', methods=['GET'])
def clear_session():
    session.pop('odl_auth', None)
    flash('Cleared credentials.', 'info')
    logger.info("Cleared ODL auth from session.")
    return redirect(url_for('odl_utilities.odl_utilities'))

# ----- ODL Feeds CRUD  -----

@odl_utilities_bp.route('/feeds', methods=['GET'])
def list_odl_feeds():
    """Show all saved ODL feeds."""
    feeds = ODLFeed.query.order_by(ODLFeed.name).all()
    return render_template('odl_feeds/list.html', feeds=feeds)

@odl_utilities_bp.route('/feeds/new', methods=['GET', 'POST'])
def new_odl_feed():
    """Create a new ODL feed entry."""
    if request.method == 'POST':
        f = ODLFeed(
            name=request.form['name'],
            url=request.form['url'],
            username=request.form.get('username'),
            password=request.form.get('password')
        )
        db.session.add(f)
        db.session.commit()
        flash(f"Created ODL feed “{f.name}”", 'success')
        return redirect(url_for('odl_utilities.list_odl_feeds'))  # ✅ fixed

    # GET
    return render_template('odl_feeds/form.html', feed=None)  # ✅ fixed

@odl_utilities_bp.route('/feeds/<int:id>/edit', methods=['GET', 'POST'])
def edit_odl_feed(id):
    """Edit an existing ODL feed."""
    feed = ODLFeed.query.get_or_404(id)
    if request.method == 'POST':
        feed.name     = request.form['name']
        feed.url      = request.form['url']
        feed.username = request.form.get('username')
        feed.password = request.form.get('password')
        db.session.commit()
        flash(f"Updated ODL feed “{feed.name}”", 'success')
        return redirect(url_for('odl_utilities.list_odl_feeds'))  # ✅ fixed

    return render_template('odl_feeds/form.html', feed=feed)  # ✅ fixed

@odl_utilities_bp.route('/feeds/<int:id>/delete', methods=['POST'])
def delete_odl_feed(id):
    """Delete an ODL feed."""
    feed = ODLFeed.query.get_or_404(id)
    db.session.delete(feed)
    db.session.commit()
    flash(f"Deleted ODL feed “{feed.name}”", 'info')
    return redirect(url_for('odl_utilities.list_odl_feeds'))  # ✅ good




@odl_utilities_bp.route('/license-info', methods=['GET'])  
def get_license_info():
    license_url = request.args.get('url')  # Get the URL of the license info document

    if not license_url:
        return jsonify({"error": "URL is required"}), 400

    # Log the raw URL being passed to the backend
    print(f"Raw License URL: {license_url}")  # Log the URL received from the frontend
    
    # Decode the URL to handle any encoded characters like '%3D'
    decoded_url = urllib.parse.unquote(license_url)
    print(f"Decoded License URL: {decoded_url}")  # Log the decoded URL

    # Get cookies from the browser (You can manually add cookies here if needed)
    cookies = {
        'session': request.cookies.get('session')  # Example: Forward the session cookie
        # You can add more cookies here if necessary, e.g., 'user_auth': 'your_cookie_value'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'TE': 'Trailers',
        'Vary': 'Origin',
        'Origin': 'http://127.0.0.1:5000',  # Add this line to mimic the correct origin
        'Referer': 'http://127.0.0.1:5000/odl'  # Set the correct Referer header if needed
    }

    try:
        # Log what we're sending to the external service
        print(f"Making request to: {decoded_url}")

        # Forward the request to the external service with the User-Agent and other headers
        response = requests.get(decoded_url, headers=headers, cookies=cookies, verify=False)  # Temporarily disable SSL verification
        
        print(f"External Service Response Status: {response.status_code}")  # Log the status code
        
        # Check if the external service returns 404 or other status
        if response.status_code == 404:
            print(f"404 Error: The URL was not found on the external server.")
        
        response.raise_for_status()  # Raise an exception if the request was not successful
        
        # Assuming the license info is in JSON format
        license_info = response.json()
        
        # Log the license info for debugging
        print(f"Fetched license info: {license_info}")
        
        return jsonify(license_info)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching license info: {e}")
        return jsonify({"error": str(e)}), 500
