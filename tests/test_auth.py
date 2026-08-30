"""Auth: signup validation, login/logout round-trips, and stale-session handling."""
from conftest import signup, login, logout

from models import db, User


def test_signup_success_sets_session(client):
    resp = signup(client)
    assert resp.status_code == 201
    assert resp.get_json()["user"]["email"] == "ada@example.com"
    # Session is live: a protected endpoint now works.
    assert client.get("/me").status_code == 200


def test_signup_requires_all_fields(client):
    resp = client.post("/signup", json={"name": "A", "email": "a@b.com"})
    assert resp.status_code == 400


def test_signup_rejects_bad_email(client):
    resp = client.post(
        "/signup",
        json={"name": "A", "email": "notanemail", "password": "password123"},
    )
    assert resp.status_code == 400
    assert "email" in resp.get_json()["error"].lower()


def test_signup_rejects_short_password(client):
    resp = client.post(
        "/signup",
        json={"name": "A", "email": "a@b.com", "password": "short"},
    )
    assert resp.status_code == 400
    assert "8" in resp.get_json()["error"]


def test_signup_rejects_overlong_password(client):
    resp = client.post(
        "/signup",
        json={"name": "A", "email": "a@b.com", "password": "x" * 200},
    )
    assert resp.status_code == 400


def test_signup_rejects_duplicate_email(client):
    signup(client, email="dupe@example.com")
    logout(client)
    resp = signup(client, name="Someone Else", email="dupe@example.com")
    assert resp.status_code == 409


def test_login_wrong_password_is_401(client):
    signup(client, email="ada@example.com")
    logout(client)
    resp = login(client, "ada@example.com", password="wrongpassword")
    assert resp.status_code == 401


def test_logout_clears_session(client):
    signup(client)
    logout(client)
    assert client.get("/me").status_code == 401


def test_session_for_deleted_user_is_rejected(client, app):
    """Regression: a session pointing at a since-deleted user must 401, not 500.

    Previously get_current_user() could return None and downstream routes would
    dereference it and crash. Now login_required rejects the stale session.
    """
    signup(client, email="ghost@example.com")
    assert client.get("/tasks").status_code == 200  # authenticated

    # Delete the underlying user out from under the live session.
    with app.app_context():
        user = User.query.filter_by(email="ghost@example.com").first()
        db.session.delete(user)
        db.session.commit()

    # The cookie still exists but points at nobody -> clean 401, no crash.
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert client.get("/me").status_code == 401
