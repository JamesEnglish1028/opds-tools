from opds_tools.models import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB

class Publication(db.Model):
    __tablename__ = 'publications'

    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(255), unique=True, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=True)
    language = db.Column(db.String(64), nullable=True)
    publisher = db.Column(db.String(255), nullable=True)
    epub_url = db.Column(db.String(1024), nullable=True)
    cover_url = db.Column(db.String(1024), nullable=True)
    manifest_url = db.Column(db.String(1024), nullable=True)
    opds_json = db.Column(JSONB, nullable=True)
    from_onix = db.Column(db.Boolean, default=False)
    from_epub = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    catalog_id = db.Column(db.Integer, db.ForeignKey('catalogs.id', ondelete='SET NULL'), nullable=True)
    catalog = db.relationship('Catalog', backref=db.backref('publications', lazy=True))

    # New field to track last modification timestamp from feed
    modified = db.Column(db.DateTime, nullable=True)
    identifier = db.Column(db.String(128), nullable=True)  # New OPDS/global ID


    def __repr__(self):
        return f"<Publication {self.title}>"