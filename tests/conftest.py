"""Shared pytest fixtures.

Each test gets a fresh app bound to its own throwaway SQLite file, so tests are
fully isolated and never touch the real database.db. We use a temp *file* rather
than sqlite:///:memory: because in-memory SQLite hands each connection its own
private database, which trips up as soon as anything crosses a connection.
"""
import os
import tempfile

import pytest

from app import create_app
from models import db, User


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "SECRET_KEY": "test-secret-key",
        # Keep the SECURE flag off so the test client (plain http) keeps the cookie.
        "SESSION_COOKIE_SECURE": False,
    })
    yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


def signup(client, name="Ada Lovelace", email="ada@example.com", password="password123"):
    """Register a user through the real endpoint and return the JSON response.

    The test client keeps the session cookie, so after this call `client` is
    authenticated as the new user.
    """
    return client.post(
        "/signup",
        json={"name": name, "email": email, "password": password},
    )


def login(client, email, password="password123"):
    return client.post("/login", json={"email": email, "password": password})


def logout(client):
    return client.post("/logout", json={})


@pytest.fixture
def make_user(app):
    """Factory that creates a user directly in the DB (bypassing the endpoint).

    Handy when a test needs several users to exist without juggling sessions.
    Returns the user's id.
    """
    def _make(name, email, password="password123"):
        with app.app_context():
            u = User(name=name, email=email)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            return u.id
    return _make
