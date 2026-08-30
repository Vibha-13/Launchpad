from datetime import date, timedelta
from flask import Blueprint, jsonify, render_template
from models import Task, HelpRequest, ActivityLog
from routes.auth_utils import login_required, get_current_user

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard_page():
    return render_template("dashboard.html")


def compute_streak(user_id):
    """Count consecutive days (ending today or yesterday) with any activity for this user."""
    rows = ActivityLog.query.filter_by(user_id=user_id).all()
    active_dates = {r.created_at.date() for r in rows}

    day = date.today()
    if day not in active_dates:
        day -= timedelta(days=1)

    streak = 0
    while day in active_dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


@dashboard_bp.route("/api/dashboard", methods=["GET"])
@login_required
def dashboard():
    user = get_current_user()

    tasks = Task.query.filter_by(user_id=user.id).order_by(Task.created_at.desc()).all()
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "done")
    progress = round((done / total) * 100) if total else 0

    recent_help = (
        HelpRequest.query.filter(HelpRequest.status == "open", HelpRequest.poster_id != user.id)
        .order_by(HelpRequest.created_at.desc())
        .limit(5)
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
        "recent_help": [h.to_dict(viewer_id=user.id) for h in recent_help],
        "stats": {
            "tasks_completed": done,
            "people_helped": people_helped,
            "streak": compute_streak(user.id),
        },
        "activity": [a.to_dict() for a in activity],
    })
