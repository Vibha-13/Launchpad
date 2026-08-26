from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from models import db, User
from routes.auth_utils import get_current_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    data = request.form or request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with that email already exists"}), 409

    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    session["user_id"] = user.id

    if request.is_json:
        return jsonify({"user": user.to_dict()}), 201
    return redirect(url_for("dashboard.dashboard_page"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    data = request.form or request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        if request.is_json:
            return jsonify({"error": "Invalid email or password"}), 401
        return render_template("login.html", error="Invalid email or password"), 401

    session["user_id"] = user.id

    if request.is_json:
        return jsonify({"user": user.to_dict()})
    return redirect(url_for("dashboard.dashboard_page"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    if request.is_json:
        return jsonify({"success": True})
    return redirect(url_for("auth.login"))


@auth_bp.route("/me")
def me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"user": user.to_dict()})
