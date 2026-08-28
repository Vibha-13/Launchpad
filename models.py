from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ---------- Allowed values (kept as plain strings, validated in routes) ----------
TASK_STATUSES = ["not_started", "in_progress", "done"]
TASK_PRIORITIES = ["low", "medium", "high"]

HELP_TOPICS = ["development", "database", "git", "deployment", "documentation", "other"]
HELP_URGENCIES = ["low", "medium", "high"]
HELP_STATUSES = ["open", "claimed", "resolved"]

ACTIVITY_EVENTS = [
    "task_created", "task_completed",
    "help_posted", "help_claimed", "help_resolved",
]
REFERENCE_TYPES = ["task", "help_request"]


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship("Task", backref="user", lazy=True, cascade="all, delete-orphan")
    posted_help = db.relationship(
        "HelpRequest", backref="poster", lazy=True,
        foreign_keys="HelpRequest.poster_id", cascade="all, delete-orphan",
    )
    claimed_help = db.relationship(
        "HelpRequest", backref="claimer", lazy=True,
        foreign_keys="HelpRequest.claimer_id",
    )
    activity = db.relationship("ActivityLog", backref="user", lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship("Notification", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email}


class Task(db.Model):
    __tablename__ = "task"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="not_started")  # see TASK_STATUSES
    priority = db.Column(db.String(20), nullable=True)  # see TASK_PRIORITIES
    due_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class HelpRequest(db.Model):
    __tablename__ = "help_request"

    id = db.Column(db.Integer, primary_key=True)
    poster_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    claimer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    topic = db.Column(db.String(30), nullable=False)  # see HELP_TOPICS
    urgency = db.Column(db.String(20), nullable=False, default="medium")  # see HELP_URGENCIES
    status = db.Column(db.String(20), nullable=False, default="open")  # see HELP_STATUSES
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    claimed_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "poster_id": self.poster_id,
            "poster_name": self.poster.name if self.poster else None,
            "claimer_id": self.claimer_id,
            "claimer_name": self.claimer.name if self.claimer else None,
            "claimer_email": self.claimer.email if self.claimer else None,
            "poster_email": self.poster.email if self.poster else None,
            "title": self.title,
            "description": self.description,
            "topic": self.topic,
            "urgency": self.urgency,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class ActivityLog(db.Model):
    __tablename__ = "activity_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    event_type = db.Column(db.String(30), nullable=False)  # see ACTIVITY_EVENTS
    reference_type = db.Column(db.String(20), nullable=False)  # see REFERENCE_TYPES
    reference_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "reference_type": self.reference_type,
            "reference_id": self.reference_id,
            "created_at": self.created_at.isoformat(),
        }


class Notification(db.Model):
    __tablename__ = "notification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=True)
    read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "message": self.message,
            "link": self.link,
            "read": self.read,
            "created_at": self.created_at.isoformat(),
        }


def log_activity(user_id, event_type, reference_type, reference_id):
    """Helper to record an activity event — call this from routes after task/help actions."""
    entry = ActivityLog(
        user_id=user_id,
        event_type=event_type,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.session.add(entry)
    return entry


def log_notification(user_id, message, link=None):
    """Helper to create a notification for a user — call this from routes after events others should know about."""
    entry = Notification(user_id=user_id, message=message, link=link)
    db.session.add(entry)
    return entry
