
from opds_tools import create_app
from .models import db
from flask.cli import with_appcontext
from flask_cors import CORS
import click
import logging

logger = logging.getLogger(__name__)


app = create_app()
CORS(app)

@click.command("init-db")
@with_appcontext
def init_db_command():
    db.create_all()
    click.echo("✅ Database initialized successfully.")

def register_commands(app):
    app.cli.add_command(init_db_command)

register_commands(app)