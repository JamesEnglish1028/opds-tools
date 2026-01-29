import os
import json
import requests
from flask import Blueprint, current_app, request, render_template, redirect, url_for, flash, jsonify
from opds_tools.models import db
from opds_tools.models.catalog import Catalog
import logging
logger = logging.getLogger(__name__)

registry_bp = Blueprint('registry', __name__, template_folder='../templates')

@registry_bp.route('/fetch-registry')
def fetch_registry():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Missing URL parameter'}), 400

    try:
        response = requests.get(
            url,
            headers={"Accept": "application/opds+json", "User-Agent": "OPDS-Tools/1.0"},
            timeout=10
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        raw_text = response.text

        print("🔎 Content-Type:", content_type)
        print("🔎 First 200 chars of response:\n", raw_text[:200])

        if "json" not in content_type.lower():
            return jsonify({'error': 'Registry did not return JSON content.'}), 400

        data = json.loads(raw_text)

        if 'catalogs' not in data and 'navigation' not in data:
            return jsonify({'error': 'URL does not contain a valid OPDS registry'}), 400

        return jsonify(data)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        logger.error(f"Registry fetch error for {url}: {str(e)}")
        return jsonify({'error': f'Failed to fetch registry: {str(e)}'}), 500


# REGISTRY DB ##

from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify

@registry_bp.route('/catalogs', methods=['GET', 'POST'])
def manage_catalogs():
    if request.method == 'POST':
        # Add new catalog from form
        title = request.form.get('title')
        description = request.form.get('description')
        url = request.form.get('url')

        if not title or not url:
            flash("Title and URL are required.", "danger")
        else:
            catalog = Catalog(title=title, description=description, url=url)
            db.session.add(catalog)
            db.session.commit()
            flash("Catalog added successfully.", "success")
        return redirect(url_for('registry.manage_catalogs'))

    # GET: list catalogs
    catalogs = Catalog.query.all()
    return render_template('catalogs.html', catalogs=catalogs)


## REGISTRY API ##

registry_api = Blueprint('registry_api', __name__)

## Get Catalog from Registry

@registry_api.route('/api/catalogs', methods=['GET'])
def get_catalogs():
    catalogs = Catalog.query.all()
    return jsonify([{
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "url": c.url
    } for c in catalogs])

## Add Catalog to Registry

@registry_api.route('/api/catalogs', methods=['POST'])
def add_catalog():
    data = request.get_json()
    if not data.get('title') or not data.get('url'):
        return jsonify({"error": "Missing title or URL"}), 400

    catalog = Catalog(
        title=data['title'],
        description=data.get('description', ''),
        url=data['url']
    )
    db.session.add(catalog)
    db.session.commit()
    return jsonify({"message": "Catalog added"}), 201

## Delete Catalog From Registry

@registry_api.route('/api/catalogs/<int:id>', methods=['DELETE'])
def delete_catalog(id):
    catalog = Catalog.query.get(id)
    if not catalog:
        return jsonify({"error": "Catalog not found"}), 404
    db.session.delete(catalog)
    db.session.commit()
    return jsonify({"message": "Catalog deleted"})
