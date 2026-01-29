from flask import Blueprint, request, jsonify
from opds_tools.models import db, Record
import logging

logger = logging.getLogger(__name__)

records_bp = Blueprint('records', __name__)

@records_bp.route('/records', methods=['POST'])
def add_record():
    logger.info("POST records.")
    json_data = request.get_json()
    if not json_data:
        return jsonify({'error': 'Invalid JSON'}), 400

    record = Record()
    record.set_data(json_data)
    db.session.add(record)
    db.session.commit()

    return jsonify({'id': record.id}), 201

@records_bp.route('/records/<int:id>', methods=['GET'])
def get_record(id):
    logger.info("GET record with id %s", id)
    record = Record.query.get(id)
    if not record:
        return jsonify({'error': 'Record not found'}), 404
    return jsonify(record.get_data())

@records_bp.route('/records', methods=['GET'])
def list_records():
    logger.info("GET list of records.")
    return jsonify([
        {"id": r.id, "data": r.get_data()}
        for r in Record.query.all()
    ])
