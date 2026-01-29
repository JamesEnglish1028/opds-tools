import os
import logging
from flask import Flask
from flask_migrate import Migrate
from dotenv import load_dotenv
load_dotenv()

from .models import db, register_models
from .routes.main import main as main_blueprint
from .routes.records import records_bp
from .routes.registry import registry_bp, registry_api
from .routes.open_search import open_search_bp
from .routes.odl_utilities import odl_utilities_bp
from .routes.onix import onix_bp
from .config import Config
from .routes.opds import opds_bp
from .routes.publications import publications_bp
from .routes.epub import epub_bp
from .routes.uploads import uploads_bp
from .routes.opds_crawler import crawler_bp
from .routes.odl_crawler import odl_crawler_bp
from .routes.validate import validate_bp
from .routes.analyze import analyze_bp



def configure_app_logging():
    logger = logging.getLogger("opds_tools")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)


def create_app():
    configure_app_logging()

    app = Flask(__name__, instance_relative_config=True)

    # Ensure instance folder exists before using it
    os.makedirs(app.instance_path, exist_ok=True)

    # Load config from object
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)

    # Register models
    with app.app_context():
        register_models()
        # db.create_all()  ❌ Not needed if using migrations

    # Register Blueprints
    app.register_blueprint(main_blueprint)
    app.register_blueprint(records_bp, url_prefix="/records")
    app.register_blueprint(registry_bp, url_prefix="/registry")
    app.register_blueprint(registry_api, url_prefix="/api/registry")
    app.register_blueprint(open_search_bp, url_prefix="/opds-search")
    app.register_blueprint(odl_utilities_bp, url_prefix="/odl")
    app.register_blueprint(onix_bp, url_prefix="/onix")
    app.register_blueprint(opds_bp)
    app.register_blueprint(publications_bp, url_prefix="/pubs")
    app.register_blueprint(epub_bp)
    app.register_blueprint(uploads_bp, url_prefix="/uploads")
    app.register_blueprint(crawler_bp)
    app.register_blueprint(odl_crawler_bp)
    app.register_blueprint(validate_bp)
    app.register_blueprint(analyze_bp)

    return app
