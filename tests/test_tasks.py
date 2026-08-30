"""Tasks: CRUD round-trip plus server-side length validation."""
from conftest import signup

from models import MAX_TITLE_LEN, MAX_DESCRIPTION_LEN


def test_create_and_complete_task(client):
    signup(client)
    resp = client.post("/tasks", json={"title": "Write tests", "priority": "high"})
    assert resp.status_code == 201
    task_id = resp.get_json()["task"]["id"]

    # Mark it done.
    resp = client.patch(f"/tasks/{task_id}", json={"status": "done"})
    assert resp.status_code == 200
    body = resp.get_json()["task"]
    assert body["status"] == "done"
    assert body["completed_at"] is not None

    # It shows up in the list.
    listing = client.get("/tasks").get_json()["tasks"]
    assert any(t["id"] == task_id for t in listing)


def test_delete_task(client):
    signup(client)
    task_id = client.post("/tasks", json={"title": "Temp"}).get_json()["task"]["id"]
    assert client.delete(f"/tasks/{task_id}").status_code == 200
    assert client.get("/tasks").get_json()["tasks"] == []


def test_task_requires_title(client):
    signup(client)
    assert client.post("/tasks", json={"title": "   "}).status_code == 400


def test_task_title_length_capped(client):
    signup(client)
    resp = client.post("/tasks", json={"title": "x" * (MAX_TITLE_LEN + 1)})
    assert resp.status_code == 400


def test_task_description_length_capped(client):
    signup(client)
    resp = client.post(
        "/tasks",
        json={"title": "ok", "description": "y" * (MAX_DESCRIPTION_LEN + 1)},
    )
    assert resp.status_code == 400


def test_tasks_require_auth(client):
    # No signup -> no session.
    assert client.get("/tasks").status_code == 401


def test_users_cannot_see_each_others_tasks(app):
    a = app.test_client()
    a.post("/signup", json={"name": "A", "email": "a@example.com", "password": "password123"})
    a.post("/tasks", json={"title": "A's secret task"})

    b = app.test_client()
    b.post("/signup", json={"name": "B", "email": "b@example.com", "password": "password123"})
    assert b.get("/tasks").get_json()["tasks"] == []
