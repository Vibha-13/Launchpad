from flask import Blueprint, jsonify, request, render_template
from models import db, User
from routes.auth_utils import login_required, get_current_user

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings-page", methods=["GET"])
@login_required
def settings_page():
    return render_template("settings.html")


@settings_bp.route("/api/settings/profile", methods=["PATCH"])
@login_required
def update_profile():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name cannot be empty"}), 400
        user.name = name

    db.session.commit()
    return jsonify({"user": user.to_dict()})


@settings_bp.route("/api/settings/password", methods=["PATCH"])
@login_required
def update_password():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    if not user.check_password(current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    user.set_password(new_password)
    db.session.commit()
    return jsonify({"success": True})
