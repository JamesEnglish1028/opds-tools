from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all model classes
from .record import Record
from .catalog import Catalog
from .odl_feed import ODLFeed
from .publication import Publication
from .ODLpublications import ODLPublication

def register_models():
    # Make sure all models are referenced here
    _ = (Record, Catalog, ODLFeed, Publication, ODLPublication)
