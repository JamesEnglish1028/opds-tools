
from flask import Blueprint, jsonify, abort, request
from opds_tools.models import db, Publication

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
