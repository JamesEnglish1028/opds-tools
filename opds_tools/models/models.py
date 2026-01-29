
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Catalog(db.Model):
    __tablename__ = 'catalogs'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(1024), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class Publication(db.Model):
    __tablename__ = 'publications'
    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(32), unique=True, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=True)
    language = db.Column(db.String(8), nullable=True)
    publisher = db.Column(db.String(255), nullable=True)
    epub_url = db.Column(db.String(1024), nullable=True)
    cover_url = db.Column(db.String(1024), nullable=True)
    manifest_url = db.Column(db.String(1024), nullable=True)
    opds_json = db.Column(db.JSON, nullable=True)
    from_onix = db.Column(db.Boolean, default=False)
    from_epub = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
