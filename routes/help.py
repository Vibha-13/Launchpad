from flask import Blueprint, request, jsonify, render_template
from models import db, HelpRequest, HELP_TOPICS, HELP_URGENCIES, HELP_STATUSES, MAX_TITLE_LEN, MAX_DESCRIPTION_LEN, log_activity, log_notification, utcnow
from routes.auth_utils import login_required, get_current_user

help_bp = Blueprint("help", __name__)

MAX_OPEN_REQUESTS_PER_USER = 5
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


@help_bp.route("/help-page", methods=["GET"])
@login_required
def help_page():
    return render_template("help.html")


@help_bp.route("/help", methods=["GET"])
@login_required
def list_help():
    user = get_current_user()
    query = HelpRequest.query

    status = request.args.get("status")
    if status:
        if status not in HELP_STATUSES:
            return jsonify({"error": f"status must be one of {HELP_STATUSES}"}), 400
        query = query.filter_by(status=status)
    elif request.args.get("all") != "1":
        # No status chosen and the client didn't explicitly ask for everything —
        # default to open requests so the feed doesn't fill up with old
        # claimed/resolved items as usage grows.
        query = query.filter_by(status="open")

    topic = request.args.get("topic")
    if topic:
        if topic not in HELP_TOPICS:
            return jsonify({"error": f"topic must be one of {HELP_TOPICS}"}), 400
        query = query.filter_by(topic=topic)

    try:
        limit = min(int(request.args.get("limit", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return jsonify({"error": "limit and offset must be integers"}), 400

    total = query.count()
    requests_ = (
        query.order_by(HelpRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return jsonify({
        "help_requests": [h.to_dict(viewer_id=user.id) for h in requests_],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(requests_) < total,
    })


@help_bp.route("/help", methods=["POST"])
@login_required
def create_help():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400
    if len(title) > MAX_TITLE_LEN:
        return jsonify({"error": f"Title must be {MAX_TITLE_LEN} characters or fewer"}), 400

    description = data.get("description")
    if description and len(description) > MAX_DESCRIPTION_LEN:
        return jsonify({"error": f"Description must be {MAX_DESCRIPTION_LEN} characters or fewer"}), 400

    topic = data.get("topic")
    if topic not in HELP_TOPICS:
        return jsonify({"error": f"topic must be one of {HELP_TOPICS}"}), 400

    urgency = data.get("urgency", "medium")
    if urgency not in HELP_URGENCIES:
        return jsonify({"error": f"urgency must be one of {HELP_URGENCIES}"}), 400

    open_count = HelpRequest.query.filter_by(poster_id=user.id, status="open").count()
    if open_count >= MAX_OPEN_REQUESTS_PER_USER:
        return jsonify({
            "error": f"You already have {MAX_OPEN_REQUESTS_PER_USER} open help requests. "
                     "Resolve or delete one before posting another."
        }), 429

    req = HelpRequest(
        poster_id=user.id,
        title=title,
        description=description,
        topic=topic,
        urgency=urgency,
        status="open",
    )
    db.session.add(req)
    db.session.flush()

    log_activity(user.id, "help_posted", "help_request", req.id)
    db.session.commit()

    return jsonify({"help_request": req.to_dict(viewer_id=user.id)}), 201


@help_bp.route("/help/<int:help_id>", methods=["PATCH"])
@login_required
def update_help(help_id):
    user = get_current_user()
    req = db.session.get(HelpRequest, help_id)
    if not req:
        return jsonify({"error": "Help request not found"}), 404

    if req.poster_id != user.id:
        return jsonify({"error": "Only the poster can edit this request"}), 403

    if req.status != "open":
        return jsonify({"error": "Only open requests can be edited — once someone's claimed it, delete and repost instead"}), 409

    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            return jsonify({"error": "Title cannot be empty"}), 400
        if len(title) > MAX_TITLE_LEN:
            return jsonify({"error": f"Title must be {MAX_TITLE_LEN} characters or fewer"}), 400
        req.title = title

    if "description" in data:
        description = data["description"]
        if description and len(description) > MAX_DESCRIPTION_LEN:
            return jsonify({"error": f"Description must be {MAX_DESCRIPTION_LEN} characters or fewer"}), 400
        req.description = description

    if "topic" in data:
        topic = data["topic"]
        if topic not in HELP_TOPICS:
            return jsonify({"error": f"topic must be one of {HELP_TOPICS}"}), 400
        req.topic = topic

    if "urgency" in data:
        urgency = data["urgency"]
        if urgency not in HELP_URGENCIES:
            return jsonify({"error": f"urgency must be one of {HELP_URGENCIES}"}), 400
        req.urgency = urgency

    db.session.commit()
    return jsonify({"help_request": req.to_dict(viewer_id=user.id)})


@help_bp.route("/help/<int:help_id>/claim", methods=["PATCH"])
@login_required
def claim_help(help_id):
    user = get_current_user()
    req = db.session.get(HelpRequest, help_id)
    if not req:
        return jsonify({"error": "Help request not found"}), 404

    if req.poster_id == user.id:
        return jsonify({"error": "You can't claim your own help request"}), 400

    if req.status != "open":
        return jsonify({"error": f"Request is already {req.status}"}), 409

    # Atomic claim. The WHERE status='open' guard means that if two people
    # claim simultaneously (multiple gunicorn workers), only one UPDATE matches
    # a row; the loser updates zero rows and is rejected below. This is what
    # actually enforces the "one claimer" guarantee \u2014 the check above is just a
    # friendly fast path for the common already-claimed case.
    poster_id, title = req.poster_id, req.title
    claimed = (
        HelpRequest.query
        .filter_by(id=help_id, status="open")
        .update(
            {"claimer_id": user.id, "status": "claimed", "claimed_at": utcnow()},
            synchronize_session=False,
        )
    )
    if not claimed:
        db.session.rollback()
        return jsonify({"error": "Someone else just claimed this request"}), 409

    log_activity(user.id, "help_claimed", "help_request", help_id)
    log_notification(poster_id, f"{user.name} is helping with \u201c{title}\u201d", link="/help-page")
    db.session.commit()

    req = db.session.get(HelpRequest, help_id)
    return jsonify({"help_request": req.to_dict(viewer_id=user.id)})


@help_bp.route("/help/<int:help_id>/unclaim", methods=["PATCH"])
@login_required
def unclaim_help(help_id):
    user = get_current_user()
    req = db.session.get(HelpRequest, help_id)
    if not req:
        return jsonify({"error": "Help request not found"}), 404

    is_claimer = req.claimer_id == user.id
    is_poster = req.poster_id == user.id
    if not is_claimer and not is_poster:
        return jsonify({"error": "Only the claimer or poster can unclaim this request"}), 403

    if req.status != "claimed":
        return jsonify({"error": "Only claimed requests can be unclaimed"}), 409

    released_by_poster = is_poster and not is_claimer
    unclaimed = (
        HelpRequest.query
        .filter_by(id=help_id, status="claimed")
        .update(
            {"claimer_id": None, "status": "open", "claimed_at": None},
            synchronize_session=False,
        )
    )
    if not unclaimed:
        db.session.rollback()
        return jsonify({"error": "Request is no longer claimed"}), 409

    db.session.commit()

    req = db.session.get(HelpRequest, help_id)
    if released_by_poster:
        return jsonify({"help_request": req.to_dict(viewer_id=user.id), "released_by_poster": True})
    return jsonify({"help_request": req.to_dict(viewer_id=user.id)})


@help_bp.route("/help/<int:help_id>/resolve", methods=["PATCH"])
@login_required
def resolve_help(help_id):
    user = get_current_user()
    req = db.session.get(HelpRequest, help_id)
    if not req:
        return jsonify({"error": "Help request not found"}), 404

    if req.poster_id != user.id:
        return jsonify({"error": "Only the poster can resolve this request"}), 403

    if req.status != "claimed":
        return jsonify({"error": "Only claimed requests can be resolved"}), 409

    claimer_id, title = req.claimer_id, req.title
    resolved = (
        HelpRequest.query
        .filter_by(id=help_id, status="claimed")
        .update(
            {"status": "resolved", "resolved_at": utcnow()},
            synchronize_session=False,
        )
    )
    if not resolved:
        db.session.rollback()
        return jsonify({"error": "Request is no longer claimed"}), 409

    log_activity(user.id, "help_resolved", "help_request", help_id)
    if claimer_id:
        log_notification(claimer_id, f"{user.name} marked \u201c{title}\u201d as resolved", link="/help-page")
    db.session.commit()

    req = db.session.get(HelpRequest, help_id)
    return jsonify({"help_request": req.to_dict(viewer_id=user.id)})


@help_bp.route("/help/<int:help_id>", methods=["DELETE"])
@login_required
def delete_help(help_id):
    user = get_current_user()
    req = db.session.get(HelpRequest, help_id)
    if not req:
        return jsonify({"error": "Help request not found"}), 404

    if req.poster_id != user.id:
        return jsonify({"error": "Only the poster can delete this request"}), 403

    db.session.delete(req)
    db.session.commit()

    return jsonify({"success": True})
