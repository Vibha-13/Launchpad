import os
import secrets
from datetime import timedelta
from flask import Flask, redirect, url_for
from models import db

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def create_app(test_config=None):
    app = Flask(__name__)

    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'database.db')}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        if os.environ.get("FLASK_ENV") == "production":
            raise RuntimeError(
                "SECRET_KEY environment variable must be set in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Local/dev fallback only — random per run, never a hardcoded default.
        secret_key = secrets.token_hex(32)
    app.config["SECRET_KEY"] = secret_key

    # --- Session cookie hardening ---
    # HTTPONLY: JS can't read the session cookie, so an XSS payload can't exfiltrate it.
    # SAMESITE=Lax: the cookie isn't sent on cross-site POSTs, which blunts CSRF on the
    #   JSON API (the browser also won't attach it to a form auto-submitted from another origin).
    # SECURE (production only): cookie is only ever sent over HTTPS. Left off in dev so
    #   local http://localhost testing still works.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=14)

    # Test overrides (e.g. a throwaway database, a fixed SECRET_KEY) are applied
    # last so they win over the defaults above, before the DB is initialised.
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    from routes.auth import auth_bp
    from routes.tasks import tasks_bp
    from routes.help import help_bp
    from routes.dashboard import dashboard_bp
    from routes.profile import profile_bp
    from routes.notifications import notifications_bp
    from routes.people import people_bp
    from routes.settings import settings_bp
    from routes.search import search_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(help_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(people_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(search_bp)

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.after_request
    def set_security_headers(resp):
        # Defense-in-depth headers, safe for this app (no external framing,
        # no need to sniff content types, and we don't want the full URL
        # leaking to third parties via the Referer header).
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    return app


if __name__ == "__main__":
    app = create_app()
    # Debug defaults OFF. Werkzeug's debugger exposes an interactive console
    # (arbitrary code execution) on unhandled exceptions, so it must never be
    # on by accident — opt in explicitly with FLASK_DEBUG=1 for local work.
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode)
