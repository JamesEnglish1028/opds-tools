
from flask import Blueprint, jsonify, abort, request, url_for
from opds_tools.models import db, Catalog, Publication

opds_bp = Blueprint('opds', __name__)

@opds_bp.route("/catalog.json")
def catalog():
    publications = Publication.query.all()
    feed = {
        "metadata": {
            "title": "My OPDS 2.0 Catalog"
        },
        "publications": [p.opds_json for p in publications if p.opds_json]
    }
    return jsonify(feed)

@opds_bp.route("/publications/<int:id>.json")
def publication_detail(id):
    pub = Publication.query.get_or_404(id)
    if not pub.opds_json:
        abort(404, description="No OPDS JSON available for this publication")
    return jsonify(pub.opds_json)

@opds_bp.route("/catalogs/<int:catalog_id>/publications.json")
def catalog_publications(catalog_id):
    catalog = Catalog.query.get_or_404(catalog_id)
    publications = Publication.query.filter_by(catalog_id=catalog.id).all()
    feed = {
        "metadata": {
            "title": f"Publications for {catalog.title}"
        },
        "publications": [p.opds_json for p in publications if p.opds_json]
    }
    return jsonify(feed)

@opds_bp.route("/publications/<int:id>/manifest.json")
def publication_manifest(id):
    pub = Publication.query.get_or_404(id)
    if not pub.opds_json:
        abort(404, description="No metadata available")

    manifest = {
        "metadata": pub.opds_json.get("metadata", {}),
        "readingOrder": pub.opds_json.get("readingOrder", [
            {
                "href": pub.epub_url,
                "type": "application/epub+zip"
            }
        ]),
        "links": [
            {
                "rel": "self",
                "href": url_for("opds.publication_manifest", id=pub.id, _external=True),
                "type": "application/webpub+json"
            },
            {
                "rel": "publication",
                "href": pub.epub_url,
                "type": "application/epub+zip"
            }
        ]
    }
    return jsonify(manifest)
