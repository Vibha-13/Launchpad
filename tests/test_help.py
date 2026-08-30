"""Help requests: full lifecycle, atomic claiming, and email-exposure rules."""


def client_for(app, name, email):
    """A fresh test client already logged in as a newly-created user."""
    c = app.test_client()
    c.post("/signup", json={"name": name, "email": email, "password": "password123"})
    return c


def post_help(client, title="Need help with Postgres", topic="database"):
    resp = client.post("/help", json={"title": title, "topic": topic})
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["help_request"]["id"]


def find_help(client, help_id, query="/help?all=1"):
    """Fetch the help feed as this client and return the one item, or None."""
    resp = client.get(query)
    assert resp.status_code == 200
    for item in resp.get_json()["help_requests"]:
        if item["id"] == help_id:
            return item
    return None


def test_full_lifecycle(app):
    poster = client_for(app, "Poster", "poster@example.com")
    helper = client_for(app, "Helper", "helper@example.com")

    help_id = post_help(poster)

    # Claim by a different user.
    assert helper.patch(f"/help/{help_id}/claim").status_code == 200
    item = find_help(helper, help_id)
    assert item["status"] == "claimed"
    assert item["claimer_name"] == "Helper"

    # Only the poster may resolve.
    assert helper.patch(f"/help/{help_id}/resolve").status_code == 403
    assert poster.patch(f"/help/{help_id}/resolve").status_code == 200
    assert find_help(poster, help_id)["status"] == "resolved"


def test_cannot_claim_own_request(app):
    poster = client_for(app, "Poster", "poster@example.com")
    help_id = post_help(poster)
    resp = poster.patch(f"/help/{help_id}/claim")
    assert resp.status_code == 400


def test_double_claim_is_rejected(app):
    """The second claimer loses the race and gets a clean 409.

    This exercises the atomic conditional UPDATE (WHERE status='open'): once the
    first claim flips the row, the second UPDATE matches zero rows and is
    rejected rather than silently overwriting the first claimer.
    """
    poster = client_for(app, "Poster", "poster@example.com")
    first = client_for(app, "First", "first@example.com")
    second = client_for(app, "Second", "second@example.com")

    help_id = post_help(poster)

    assert first.patch(f"/help/{help_id}/claim").status_code == 200
    resp = second.patch(f"/help/{help_id}/claim")
    assert resp.status_code == 409

    # The winner sticks.
    assert find_help(poster, help_id)["claimer_name"] == "First"


def test_unclaim_returns_request_to_open(app):
    poster = client_for(app, "Poster", "poster@example.com")
    helper = client_for(app, "Helper", "helper@example.com")

    help_id = post_help(poster)
    helper.patch(f"/help/{help_id}/claim")
    assert helper.patch(f"/help/{help_id}/unclaim").status_code == 200
    assert find_help(poster, help_id)["status"] == "open"


# --- Email-exposure rules (contact details unlock only after a claim, and only
#     for the two people involved) -------------------------------------------

def test_open_request_never_exposes_email(app):
    poster = client_for(app, "Poster", "poster@example.com")
    onlooker = client_for(app, "Onlooker", "onlooker@example.com")

    help_id = post_help(poster)
    item = find_help(onlooker, help_id)
    assert "poster_email" not in item
    assert "claimer_email" not in item


def test_claimed_request_exposes_email_to_involved_parties(app):
    poster = client_for(app, "Poster", "poster@example.com")
    helper = client_for(app, "Helper", "helper@example.com")

    help_id = post_help(poster)
    helper.patch(f"/help/{help_id}/claim")

    # Claimer sees both emails...
    as_helper = find_help(helper, help_id)
    assert as_helper["poster_email"] == "poster@example.com"
    assert as_helper["claimer_email"] == "helper@example.com"

    # ...and so does the poster.
    as_poster = find_help(poster, help_id)
    assert as_poster["poster_email"] == "poster@example.com"
    assert as_poster["claimer_email"] == "helper@example.com"


def test_claimed_request_hides_email_from_bystanders(app):
    poster = client_for(app, "Poster", "poster@example.com")
    helper = client_for(app, "Helper", "helper@example.com")
    bystander = client_for(app, "Nosy", "nosy@example.com")

    help_id = post_help(poster)
    helper.patch(f"/help/{help_id}/claim")

    item = find_help(bystander, help_id)
    assert item["status"] == "claimed"
    assert "poster_email" not in item
    assert "claimer_email" not in item
