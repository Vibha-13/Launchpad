# LaunchPad

A lightweight internal tool for teams to track their own tasks and ask each other for help — built around one question: *when someone's stuck, how do they actually get unstuck?*

## Why

Individual task trackers are common. What's less common is connecting "I'm stuck" to "here's exactly what you should do about it." LaunchPad tries to close that gap: when a help request gets claimed, both people immediately see the other's contact info and a topic-specific checklist of what to share or ask for — instead of a vague "someone will help you eventually."

## Features

- **Auth** — session-based signup/login/logout
- **Tasks** — create, update status, set priority/due date, delete
- **Dashboard** — today's task progress (count + percentage), recent open help requests
- **Help Feed** — post a request with a topic and urgency; claim/resolve workflow; filter by status and topic
- **Contact & next steps** — once a request is claimed, both the poster and the claimer see the other's email plus a topic-specific checklist (what to share, what to ask for)
- **Profile** — stats (tasks completed, people helped) and an activity log, computed live from the underlying data rather than stored as separate counters

## Tech stack

- **Backend:** Flask, Flask-SQLAlchemy, SQLite
- **Frontend:** server-rendered Jinja templates, vanilla JS (fetch), no frontend framework or build step
- **Auth:** Flask sessions + Werkzeug password hashing

## Architecture notes

- Routes are split into blueprints by feature (`auth`, `tasks`, `help`, `dashboard`, `profile`) rather than one file, so each feature's routes and permission checks live together.
- Profile/dashboard stats (tasks completed, people helped) are computed from the `Task` and `HelpRequest` tables on each request rather than stored as counters — avoids drift if a task's status changes after the fact, at the cost of a query per view.
- `ActivityLog` is a separate append-only table rather than derived from other tables, since it needs to preserve a chronological record even after the referenced task/request is deleted or changes state.

## Running it

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then visit `http://127.0.0.1:5000/login`.

## Future scope

- Multiple claimers / a queue for high-demand requests
- Notifications when a request is claimed or resolved
- Team- or project-level grouping instead of a single flat feed
