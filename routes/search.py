from sqlalchemy import or_
from flask import Blueprint, jsonify, request
from models import Task, HelpRequest
from routes.auth_utils import login_required, get_current_user

search_bp = Blueprint("search", __name__)


@search_bp.route("/api/search", methods=["GET"])
@login_required
def search():
    user = get_current_user()
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"tasks": [], "help_requests": []})

    like = f"%{q}%"
    tasks = (
        Task.query.filter(
            Task.user_id == user.id,
            or_(Task.title.ilike(like), Task.description.ilike(like)),
        )
        .limit(10)
        .all()
    )
    help_requests = (
        HelpRequest.query.filter(
            or_(HelpRequest.title.ilike(like), HelpRequest.description.ilike(like))
        )
        .limit(10)
        .all()
    )

    return jsonify({
        "tasks": [t.to_dict() for t in tasks],
        "help_requests": [h.to_dict(viewer_id=user.id) for h in help_requests],
    })
