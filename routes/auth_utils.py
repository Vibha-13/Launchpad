from functools import wraps
from flask import session, jsonify, g
from models import User, db


def get_current_user():
    """Return the logged-in User, or None.

    The result is cached on flask.g for the duration of the request so routes
    can call this freely without issuing a DB query each time.
    """
    if "current_user" in g:
        return g.current_user
    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    g.current_user = user
    return user


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            # Either there's no session, or the session points at a user that
            # no longer exists (e.g. the account was deleted while the session
            # lived on). Clear the stale cookie and force re-authentication so
            # downstream routes never operate on a None user.
            session.pop("user_id", None)
            return jsonify({"error": "Login required"}), 401
        return view_func(*args, **kwargs)
    return wrapped
