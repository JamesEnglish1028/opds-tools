from models.record import Record
from models.catalog import Catalog
from models import db

sample_record = Record()
sample_record.set_data({"title": "Sample Title", "author": "Jane Doe"})
db.session.add(sample_record)

sample_catalog = Catalog(name="Test Catalog", url="http://example.com/opds")
db.session.add(sample_catalog)

db.session.commit()