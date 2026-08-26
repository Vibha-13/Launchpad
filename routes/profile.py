from flask import Blueprint, jsonify, render_template
from models import Task, HelpRequest, ActivityLog
from routes.auth_utils import login_required, get_current_user

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile-page", methods=["GET"])
@login_required
def profile_page():
    return render_template("profile.html")


@profile_bp.route("/api/profile", methods=["GET"])
@login_required
def profile_data():
    user = get_current_user()

    tasks_completed = Task.query.filter_by(user_id=user.id, status="done").count()
    people_helped = HelpRequest.query.filter_by(
        claimer_id=user.id, status="resolved"
    ).count()

    activity = (
        ActivityLog.query.filter_by(user_id=user.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(50)
        .all()
    )

    return jsonify({
        "user": user.to_dict(),
        "stats": {
            "tasks_completed": tasks_completed,
            "people_helped": people_helped,
        },
        "activity": [a.to_dict() for a in activity],
    })
