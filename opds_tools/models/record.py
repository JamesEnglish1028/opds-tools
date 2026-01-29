from opds_tools.models import db
import json

class Record(db.Model):
    __tablename__ = 'record'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Text)  # Store JSON as string

    def set_data(self, obj):
        self.data = json.dumps(obj)

    def get_data(self):
        return json.loads(self.data)
