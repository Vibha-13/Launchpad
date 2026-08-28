from datetime import datetime
from flask import Blueprint, request, jsonify, render_template
from models import db, HelpRequest, HELP_TOPICS, HELP_URGENCIES, HELP_STATUSES, log_activity, log_notification
from routes.auth_utils import login_required, get_current_user

help_bp = Blueprint("help", __name__)


@help_bp.route("/help-page", methods=["GET"])
@login_required
def help_page():
    return render_template("help.html")


@help_bp.route("/help", methods=["GET"])
@login_required
def list_help():
    query = HelpRequest.query

    status = request.args.get("status")
    if status:
        if status not in HELP_STATUSES:
            return jsonify({"error": f"status must be one of {HELP_STATUSES}"}), 400
        query = query.filter_by(status=status)

    topic = request.args.get("topic")
    if topic:
        if topic not in HELP_TOPICS:
            return jsonify({"error": f"topic must be one of {HELP_TOPICS}"}), 400
        query = query.filter_by(topic=topic)

    requests_ = query.order_by(HelpRequest.created_at.desc()).all()
    return jsonify({"help_requests": [h.to_dict() for h in requests_]})


@help_bp.route("/help", methods=["POST"])
@login_required
def create_help():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400

    topic = data.get("topic")
    if topic not in HELP_TOPICS:
        return jsonify({"error": f"topic must be one of {HELP_TOPICS}"}), 400

    urgency = data.get("urgency", "medium")
    if urgency not in HELP_URGENCIES:
        return jsonify({"error": f"urgency must be one of {HELP_URGENCIES}"}), 400

    req = HelpRequest(
        poster_id=user.id,
        title=title,
        description=data.get("description"),
        topic=topic,
        urgency=urgency,
        status="open",
    )
    db.session.add(req)
    db.session.flush()

    log_activity(user.id, "help_posted", "help_request", req.id)
    db.session.commit()

    return jsonify({"help_request": req.to_dict()}), 201


@help_bp.route("/help/<int:help_id>/claim", methods=["PATCH"])
@login_required
def claim_help(help_id):
    user = get_current_user()
    req = HelpRequest.query.get(help_id)
    if not req:
        return jsonify({"error": "Help request not found"}), 404

    if req.poster_id == user.id:
        return jsonify({"error": "You can't claim your own help request"}), 400

    if req.status != "open":
        return jsonify({"error": f"Request is already {req.status}"}), 409

    req.claimer_id = user.id
    req.status = "claimed"
    req.claimed_at = datetime.utcnow()

    log_activity(user.id, "help_claimed", "help_request", req.id)
    log_notification(req.poster_id, f"{user.name} is helping with \u201c{req.title}\u201d", link="/help-page")
    db.session.commit()

    return jsonify({"help_request": req.to_dict()})


@help_bp.route("/help/<int:help_id>/unclaim", methods=["PATCH"])
@login_required
def unclaim_help(help_id):
    user = get_current_user()
    req = HelpRequest.query.get(help_id)
    if not req:
        return jsonify({"error": "Help request not found"}), 404

    if req.claimer_id != user.id:
        return jsonify({"error": "Only the claimer can unclaim this request"}), 403

    if req.status != "claimed":
        return jsonify({"error": "Only claimed requests can be unclaimed"}), 409

    req.claimer_id = None
    req.status = "open"
    req.claimed_at = None
    db.session.commit()

    return jsonify({"help_request": req.to_dict()})


@help_bp.route("/help/<int:help_id>/resolve", methods=["PATCH"])
@login_required
def resolve_help(help_id):
    user = get_current_user()
    req = HelpRequest.query.get(help_id)
    if not req:
        return jsonify({"error": "Help request not found"}), 404

    if req.poster_id != user.id:
        return jsonify({"error": "Only the poster can resolve this request"}), 403

    if req.status != "claimed":
        return jsonify({"error": "Only claimed requests can be resolved"}), 409

    req.status = "resolved"
    req.resolved_at = datetime.utcnow()

    log_activity(user.id, "help_resolved", "help_request", req.id)
    if req.claimer_id:
        log_notification(req.claimer_id, f"{user.name} marked \u201c{req.title}\u201d as resolved", link="/help-page")
    db.session.commit()

    return jsonify({"help_request": req.to_dict()})


@help_bp.route("/help/<int:help_id>", methods=["DELETE"])
@login_required
def delete_help(help_id):
    user = get_current_user()
    req = HelpRequest.query.get(help_id)
    if not req:
        return jsonify({"error": "Help request not found"}), 404

    if req.poster_id != user.id:
        return jsonify({"error": "Only the poster can delete this request"}), 403

    db.session.delete(req)
    db.session.commit()

    return jsonify({"success": True})
