"""Security posture: response headers, cookie flags, and the XSS server contract."""
from conftest import signup


def test_security_headers_present(client):
    resp = client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "same-origin"


def test_session_cookie_is_hardened(client):
    resp = signup(client)
    set_cookie = " ".join(resp.headers.getlist("Set-Cookie"))
    assert "HttpOnly" in set_cookie          # JS can't read it -> XSS can't steal it
    assert "SameSite=Lax" in set_cookie       # not sent on cross-site POSTs -> CSRF mitigation


def test_api_returns_user_input_verbatim(client):
    """The API stores/returns user text unchanged; rendering-layer escaping is the
    defense against XSS.

    The stored-XSS fix lives at the rendering layer: ui.js escapes values before
    building innerHTML, and Jinja autoescapes template output. The API itself
    deliberately round-trips the raw string, so this test locks in that contract
    (and would catch anyone "fixing" XSS by mangling stored data instead).
    """
    signup(client)
    payload = '<img src=x onerror="alert(1)">'
    resp = client.post("/help", json={"title": payload, "topic": "other"})
    assert resp.status_code == 201
    assert resp.get_json()["help_request"]["title"] == payload
