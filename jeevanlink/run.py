"""JeevanLink Flask application.

Run from the project root:

    python main.py

A single server hosts both the frontend and the API:

    http://127.0.0.1:5000/            -> index.html
    http://127.0.0.1:5000/donate      -> donar.html
    http://127.0.0.1:5000/request     -> request.html
    http://127.0.0.1:5000/api/...     -> REST API

Because everything is served from one origin, the relative URLs used
by the frontend ("/api/donors") resolve correctly and no CORS
configuration is needed in the browser.
"""

from pathlib import Path

from flask import Flask
from flask import jsonify
from flask import send_from_directory

from flask_cors import CORS

from .api import api_blueprint
from . import alerts
from .database import backend_name
from .database import describe_database
from .database import IS_POSTGRES
from .donors import donors_blueprint
from .init_db import initialise_database


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"


def _allowed_origins():
    """Origins allowed to call /api/*.

    Everything is served from one origin in normal use, so this only
    matters if the frontend is opened separately (Live Server) or from
    another device during development.
    """
    import os

    configured = os.getenv("ALLOWED_ORIGINS", "").strip()
    if configured:
        return [o.strip() for o in configured.split(",") if o.strip()]

    return "*"


def create_app(auto_init_db: bool = True) -> Flask:
    app = Flask(
        __name__,
        static_folder=str(FRONTEND_DIR),
        static_url_path="/static"
    )

    # Allows the frontend to be served separately (for example by the
    # VS Code Live Server extension on port 5500) without the API
    # rejecting the request.
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": _allowed_origins()
            }
        }
    )

    app.register_blueprint(donors_blueprint)
    app.register_blueprint(api_blueprint)

    # Create the tables on first run. On Postgres the statements all use
    # IF NOT EXISTS, so this is safe to attempt on every boot.
    if auto_init_db:
        try:
            if IS_POSTGRES:
                initialise_database()
            elif not Path(describe_database()).exists():
                initialise_database()
        except Exception as error:
            print(f"[startup] could not initialise database: {error}")

    # ---------- FRONTEND PAGES ----------

    @app.route("/")
    def home():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/donate")
    @app.route("/donor")
    def donate_page():
        return send_from_directory(FRONTEND_DIR, "donar.html")

    @app.route("/request")
    @app.route("/need-blood")
    def request_page():
        return send_from_directory(FRONTEND_DIR, "request.html")

    @app.route("/respond/<token>")
    def respond_page(token):
        # Target of the link sent to donors by WhatsApp or SMS.
        return send_from_directory(FRONTEND_DIR, "respond.html")

    # Serve CSS, JS and images by their bare filename, because the HTML
    # files reference them that way (for example <link href="index.css">).
    @app.route("/<path:filename>")
    def frontend_asset(filename):
        target = FRONTEND_DIR / filename

        if target.is_file():
            return send_from_directory(FRONTEND_DIR, filename)

        return jsonify({
            "success": False,
            "message": "Not found"
        }), 404

    # ---------- HEALTH CHECK ----------

    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "success": True,
            "message": "JeevanLink backend is running",
            "database": describe_database(),
            "backend": backend_name(),
            "alertChannels": alerts.active_channels(),
        }), 200

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
