from flask import Blueprint, jsonify, render_template
from models import Task, HelpRequest, ActivityLog
from routes.auth_utils import login_required, get_current_user

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard_page():
    return render_template("dashboard.html")


@dashboard_bp.route("/api/dashboard", methods=["GET"])
@login_required
def dashboard():
    user = get_current_user()

    tasks = Task.query.filter_by(user_id=user.id).order_by(Task.created_at.desc()).all()
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "done")
    progress = round((done / total) * 100) if total else 0

    recent_help = (
        HelpRequest.query.filter_by(status="open")
        .order_by(HelpRequest.created_at.desc())
        .limit(3)
        .all()
    )

    people_helped = HelpRequest.query.filter_by(
        claimer_id=user.id, status="resolved"
    ).count()

    activity = (
        ActivityLog.query.filter_by(user_id=user.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(10)
        .all()
    )

    return jsonify({
        "progress": progress,
        "tasks": [t.to_dict() for t in tasks],
        "recent_help": [h.to_dict() for h in recent_help],
        "stats": {
            "tasks_completed": done,
            "people_helped": people_helped,
        },
        "activity": [a.to_dict() for a in activity],
    })
