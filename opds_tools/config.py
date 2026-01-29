import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "secret-key")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")

    READIUM_CLI_ENDPOINT = os.getenv("READIUM_CLI_ENDPOINT", "http://localhost:15080/")
    THORIUM_WEB_CLIENT_URL = os.getenv("THORIUM_WEB_CLIENT_URL", "http://localhost:3000/read")
    R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "https://opds-tools.org/content")

    R2_ENDPOINT = os.getenv("R2_ENDPOINT")
    R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
    R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
    R2_BUCKET = os.getenv("R2_BUCKET", "content")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(basedir, 'instance', 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

