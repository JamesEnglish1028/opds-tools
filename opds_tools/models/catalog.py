from . import db

class Catalog(db.Model):
    __tablename__ = 'catalogs'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(500), nullable=False, unique=True)

    def to_dict(self):
        return {
            "title": self.title,
            "description": self.description,
            "url": self.url,
        }

    @classmethod
    def from_opds_entry(cls, entry):
        title = entry.get("metadata", {}).get("title", "Untitled")
        description = entry.get("metadata", {}).get("description")
        href = next(
            (link.get("href") for link in entry.get("links", [])
             if link.get("rel") == "http://opds-spec.org/catalog"),
            None
        )
        return cls(title=title, description=description, url=href)
