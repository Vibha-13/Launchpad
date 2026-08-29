import os
import secrets
from flask import Flask, redirect, url_for
from models import db

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def create_app():
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

    return app


if __name__ == "__main__":
    app = create_app()
    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug_mode)
