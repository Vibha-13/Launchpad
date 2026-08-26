from datetime import datetime, date
from flask import Blueprint, request, jsonify, render_template
from models import db, Task, TASK_STATUSES, TASK_PRIORITIES, log_activity
from routes.auth_utils import login_required, get_current_user

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("/tasks-page", methods=["GET"])
@login_required
def tasks_page():
    return render_template("tasks.html")


@tasks_bp.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    user = get_current_user()
    tasks = (
        Task.query.filter_by(user_id=user.id)
        .order_by(Task.created_at.desc())
        .all()
    )
    return jsonify({"tasks": [t.to_dict() for t in tasks]})


@tasks_bp.route("/tasks", methods=["POST"])
@login_required
def create_task():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400

    priority = data.get("priority")
    if priority and priority not in TASK_PRIORITIES:
        return jsonify({"error": f"priority must be one of {TASK_PRIORITIES}"}), 400

    due_date = None
    if data.get("due_date"):
        try:
            due_date = date.fromisoformat(data["due_date"])
        except ValueError:
            return jsonify({"error": "due_date must be in YYYY-MM-DD format"}), 400

    task = Task(
        user_id=user.id,
        title=title,
        description=data.get("description"),
        priority=priority,
        due_date=due_date,
        status="not_started",
    )
    db.session.add(task)
    db.session.flush()  # get task.id before commit

    log_activity(user.id, "task_created", "task", task.id)
    db.session.commit()

    return jsonify({"task": task.to_dict()}), 201


@tasks_bp.route("/tasks/<int:task_id>", methods=["PATCH"])
@login_required
def update_task(task_id):
    user = get_current_user()
    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            return jsonify({"error": "Title cannot be empty"}), 400
        task.title = title

    if "description" in data:
        task.description = data["description"]

    if "priority" in data:
        priority = data["priority"]
        if priority and priority not in TASK_PRIORITIES:
            return jsonify({"error": f"priority must be one of {TASK_PRIORITIES}"}), 400
        task.priority = priority

    if "due_date" in data:
        if data["due_date"]:
            try:
                task.due_date = date.fromisoformat(data["due_date"])
            except ValueError:
                return jsonify({"error": "due_date must be in YYYY-MM-DD format"}), 400
        else:
            task.due_date = None

    if "status" in data:
        status = data["status"]
        if status not in TASK_STATUSES:
            return jsonify({"error": f"status must be one of {TASK_STATUSES}"}), 400

        was_done = task.status == "done"
        task.status = status

        if status == "done" and not was_done:
            task.completed_at = datetime.utcnow()
            log_activity(user.id, "task_completed", "task", task.id)
        elif status != "done":
            task.completed_at = None

    db.session.commit()
    return jsonify({"task": task.to_dict()})


@tasks_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    user = get_current_user()
    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify({"error": "Task not found"}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({"success": True})
