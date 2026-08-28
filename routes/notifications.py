from flask import Blueprint, jsonify, request
from models import db, Notification
from routes.auth_utils import login_required, get_current_user

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications", methods=["GET"])
@login_required
def list_notifications():
    user = get_current_user()
    notifs = (
        Notification.query.filter_by(user_id=user.id)
        .order_by(Notification.created_at.desc())
        .limit(30)
        .all()
    )
    unread_count = Notification.query.filter_by(user_id=user.id, read=False).count()
    return jsonify({
        "notifications": [n.to_dict() for n in notifs],
        "unread_count": unread_count,
    })


@notifications_bp.route("/notifications/<int:notif_id>/read", methods=["PATCH"])
@login_required
def mark_read(notif_id):
    user = get_current_user()
    notif = Notification.query.filter_by(id=notif_id, user_id=user.id).first()
    if not notif:
        return jsonify({"error": "Notification not found"}), 404
    notif.read = True
    db.session.commit()
    return jsonify({"notification": notif.to_dict()})


@notifications_bp.route("/notifications/read-all", methods=["PATCH"])
@login_required
def mark_all_read():
    user = get_current_user()
    Notification.query.filter_by(user_id=user.id, read=False).update({"read": True})
    db.session.commit()
    return jsonify({"success": True})
