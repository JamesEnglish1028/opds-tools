# models/odl_publication.py
from datetime import datetime
from opds_tools.models import db
from opds_tools.models.odl_feed import ODLFeed  # Optional: helps with relationship clarity
from sqlalchemy.dialects.postgresql import JSONB

class ODLPublication(db.Model):
    __tablename__ = "odl_publications"

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(JSONB, nullable=False)  # raw publication JSON
    feed_id = db.Column(db.Integer, db.ForeignKey("odl_feeds.id"), nullable=False)
    crawled_at = db.Column(db.DateTime, default=datetime.utcnow)

    feed = db.relationship("ODLFeed", backref=db.backref("publications", lazy=True))
