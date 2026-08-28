from flask import Blueprint, jsonify, render_template
from models import User, Task, HelpRequest
from routes.auth_utils import login_required

people_bp = Blueprint("people", __name__)


@people_bp.route("/people-page", methods=["GET"])
@login_required
def people_page():
    return render_template("people.html")


@people_bp.route("/api/people", methods=["GET"])
@login_required
def list_people():
    users = User.query.order_by(User.name).all()
    result = []
    for u in users:
        tasks_completed = Task.query.filter_by(user_id=u.id, status="done").count()
        people_helped = HelpRequest.query.filter_by(claimer_id=u.id, status="resolved").count()
        result.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "tasks_completed": tasks_completed,
            "people_helped": people_helped,
        })
    return jsonify({"people": result})
