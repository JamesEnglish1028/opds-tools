# opds_tools/models/odl_feed.py

from datetime import datetime
from . import db

class ODLFeed(db.Model):
    __tablename__ = "odl_feeds"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    url = db.Column(db.String(512), nullable=False)
    username = db.Column(db.String(128))
    password = db.Column(db.String(128))   # consider encrypting in production
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ODLFeed {self.name} ({self.url})>"
