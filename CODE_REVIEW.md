# LaunchPad — Code Review & Improvement Plan

*Reviewed: 2026-08-30. Scope: full application — `app.py`, `models.py`, all `routes/*.py`, templates, and `static/js`. The `venv/` directory was ignored.*

LaunchPad is in good shape overall: ownership checks on tasks are consistently correct, the help workflow is thoughtfully designed, secret-key handling is already hardened, and most templates escape user content properly. The issues below are the exceptions — and a few of them are genuinely exploitable, so they're worth fixing before this is used by a real team.

## Findings at a glance

| # | Severity | Area | Finding |
|---|----------|------|---------|
| S1 | **High** | Security | Stored XSS in the notifications dropdown (cross-user) |
| S2 | **High** | Security | Stored XSS in global search (cross-user) |
| S3 | Low | Security | Self-XSS in the dashboard greeting |
| S4 | Medium | Security | No CSRF defense on form endpoints (login/signup/logout) |
| S5 | Medium | Security | Session cookies not hardened (no SameSite/Secure) |
| S6 | Low–Med | Security | Debug mode defaults **on** for `python app.py` |
| C1 | Medium | Correctness | `get_current_user()` can be `None` → routes 500 |
| C2 | Medium | Correctness | Claim workflow has a check-then-set race (TOCTOU) |
| C3 | Low–Med | Correctness | Validation gaps & inconsistency (password, email, lengths) |
| C4 | Low–Med | Privacy | Emails leak on *unclaimed* requests, contradicting the design |
| Q1 | Medium | Quality | No automated tests despite README's "tested end-to-end" |
| Q2 | Low | Quality | `escapeHtml` duplicated 4× and missing where it mattered |

---

## Security

### S1 — Stored XSS in the notifications dropdown *(High, cross-user)*

**Where:** `static/js/ui.js` `loadNotifications()` — `` `<div>${n.message}</div>` `` rendered with `innerHTML`.

**Issue:** Notification messages embed user-controlled data. In `routes/help.py`:

```python
log_notification(req.poster_id, f"{user.name} is helping with “{req.title}”", ...)
```

`user.name` is never sanitized (`routes/auth.py` signup, `routes/settings.py` profile update both store it raw), and `req.title` is arbitrary. Because `ui.js` interpolates the message straight into `innerHTML` with no escaping, a display name like `<img src=x onerror=…>` executes script in the **victim's** browser the moment they open the notification bell after that user claims or resolves their request.

**Impact:** Cross-user stored XSS → session/credential theft, actions on behalf of the victim. No special access required — any registered user can attack any other.

**Fix:** Escape `n.message` before insertion (see Q2 — add one shared `escapeHtml` to `ui.js`).

### S2 — Stored XSS in global search *(High, cross-user)*

**Where:** `static/js/ui.js` search handler — `` `<div>${i.title}</div>` `` via `innerHTML`.

**Issue:** `routes/search.py` returns help requests from **all** users (search over the shared feed is intentional), and titles are rendered unescaped. A malicious help-request title runs in any user whose search matches it.

**Fix:** Escape `i.title` with the shared helper.

### S3 — Self-XSS in the dashboard greeting *(Low)*

**Where:** `templates/dashboard.html:88` — `` greeting.innerHTML = `Hey ${me.user.name.split(' ')[0]}! …` ``.

**Issue:** The user's own name is injected via `innerHTML`. A no-space payload (`<svg onload=…>`) executes. Only self-inflicted, so low severity, but it's the same class of bug and cheap to close.

**Fix:** Use `textContent` for the name, or escape it.

### S4 — No CSRF defense on form endpoints *(Medium)*

**Where:** `routes/auth.py` `login`/`signup`/`logout` accept `request.form`; logout is a plain `<form method="POST">` in `templates/app_base.html`.

**Issue:** These endpoints accept classic form submissions, so a cross-site auto-submitting form can log a victim out (annoyance) or **log them into an attacker-controlled account** (login CSRF — the victim's subsequent tasks and help posts land in the attacker's account).

Note: the task/help/settings JSON endpoints are *incidentally* protected today because they require `Content-Type: application/json`, which a cross-site form cannot send. That protection is real but undocumented and fragile.

**Fix (proportional):** Set `SESSION_COOKIE_SAMESITE="Lax"` (see S5) — with Lax, the session cookie isn't attached to cross-site POSTs, which closes the login/logout CSRF vector without touching the UX. Full token-based CSRF (Flask-WTF) is the stronger long-term option and is noted as a follow-up.

### S5 — Session cookies not hardened *(Medium)*

**Where:** `app.py` `create_app()` — no cookie flags configured.

**Issue:** `SESSION_COOKIE_SECURE` defaults to `False` (cookie sent over plain HTTP), `SESSION_COOKIE_SAMESITE` is unset, and there's no session lifetime. `HTTPOnly` defaults on, which is good.

**Fix:** Set `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"`, `SESSION_COOKIE_SECURE=True` in production, and a `PERMANENT_SESSION_LIFETIME`.

### S6 — Debug mode defaults on *(Low–Medium)*

**Where:** `app.py:68` — `debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"`.

**Issue:** Running `python app.py` with no env set enables the Werkzeug interactive debugger, which is a remote-code-execution surface if ever exposed. Production via gunicorn doesn't call `app.run`, and `SECRET_KEY` is already gated on `FLASK_ENV=production`, so this is partly mitigated — but the default should be safe.

**Fix:** Default `FLASK_DEBUG` to `"0"`; document opting in for local dev.

---

## Correctness

### C1 — `get_current_user()` can return `None` → 500 *(Medium)*

**Where:** `routes/auth_utils.py`. `login_required` only checks `"user_id" in session`; `get_current_user()` does `User.query.get(user_id)`, which is `None` if that user was deleted while their session lived on. Routes then do `user.id` immediately (e.g. `routes/tasks.py:18`, everywhere) → `AttributeError` → 500.

**Fix:** Have `login_required` resolve the user once, return 401 (and clear the stale session) if it's gone, and cache it on `flask.g` so routes can't hit `None`.

### C2 — Claim workflow race (TOCTOU) *(Medium)*

**Where:** `routes/help.py` `claim_help()` — reads `req.status`, checks `!= "open"`, then assigns. Not atomic.

**Issue:** The README promises "prevents multiple people from claiming the same request," but with gunicorn running multiple workers (the reason gunicorn is in `requirements.txt`), two simultaneous claims can both pass the check and both commit.

**Fix:** Replace with an atomic conditional `UPDATE … WHERE id=? AND status='open'` and check the affected row count; only the winning request proceeds. Apply the same guard to `resolve`.

### C3 — Validation gaps and inconsistency *(Low–Medium)*

**Where:** `routes/auth.py` signup vs. `routes/settings.py` password change.

**Issue:** Signup enforces **no** password length, but changing the password later requires ≥ 8 characters — so a user can register a 1-character password they could never set via settings. There's also no email-format validation, and `String(120)` limits aren't enforced by SQLite, so names/titles/descriptions are effectively unbounded (DB bloat, UI breakage).

**Fix:** Add an email-format check and a shared password-policy (≥ 8) to signup; cap field lengths server-side.

### C4 — Emails leak on unclaimed requests *(Low–Medium, privacy)*

**Where:** `models.py` `HelpRequest.to_dict()` always includes `poster_email` and `claimer_email`; returned by `routes/help.py` `list_help`, `routes/dashboard.py`, and `routes/search.py`.

**Issue:** The README frames contact info as something you unlock *after claiming* ("once a request is claimed, both people see the other's email"). But `to_dict()` hands out the poster's email for every **open** request to anyone browsing the feed. (Separately, `/api/people` lists every user's email — worth confirming that directory is intended.)

**Fix:** Make `to_dict(viewer_id=…)` include emails only when the request is `claimed`/`resolved` **and** the viewer is the poster or claimer, matching the stated design. Pass the current user at each call site.

---

## Quality

### Q1 — No automated tests *(Medium)*

The README describes extensive manual, multi-user testing, but there is no test suite in the repo. Given the security-sensitive changes above, tests are what prove the fixes hold and guard against regressions.

**Fix:** Add a `pytest` suite (in-memory SQLite) covering the isolation/workflow guarantees the README claims, plus regression tests for each fix here (escaping, None-session 401, atomic double-claim, signup validation, email-exposure rules).

### Q2 — `escapeHtml` duplicated and missing where it counted *(Low)*

`escapeHtml` is copy-pasted into `auth.js`, `tasks.html`, `help.html`, and `dashboard.html` — but **not** `ui.js`, which is exactly why S1/S2 exist. The duplication is the root cause.

**Fix:** Define one `window.escapeHtml` in `ui.js` (loaded on every app page) and have the others reuse it.

---

## Recommended fix order

1. **S1, S2, Q2** — add shared `escapeHtml` to `ui.js`, escape notification/search output (kills both high-severity XSS at the root).
2. **S3** — dashboard greeting.
3. **C1** — auth `None` crash (small, prevents 500s).
4. **C2** — atomic claim.
5. **S4, S5, S6** — session/cookie/debug hardening in `app.py`.
6. **C3** — signup/validation.
7. **C4** — viewer-aware email exposure.
8. **Q1** — pytest suite covering all of the above.

Each change is small and local; none require a redesign. A meaningful Content-Security-Policy is deliberately **not** included here — the app relies on inline `<script>` blocks and inline `onclick=` handlers, so a real CSP needs those refactored first; shipping an `'unsafe-inline'` CSP would give false assurance. That's the recommended next step after this pass.

---

## Resolution — all findings fixed (2026-08-30)

Every item above has been implemented. Summary of what changed:

| # | Status | Change |
|---|--------|--------|
| S1/S2/Q2 | Fixed | Single `window.escapeHtml` added at the top of `static/js/ui.js`; notification messages, search titles, and search types now escaped before `innerHTML`. |
| S3 | Fixed | `templates/dashboard.html` greeting now escapes the name. |
| S4/S5 | Fixed | `app.py` sets `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE="Lax"`, `SESSION_COOKIE_SECURE` (production), and a 14-day `PERMANENT_SESSION_LIFETIME`. SameSite=Lax closes the login/logout CSRF vector. |
| S6 | Fixed | `FLASK_DEBUG` now defaults to `"0"`; opt in explicitly for local dev. |
| C1 | Fixed | `login_required` resolves the user once, returns 401 + clears the stale cookie if the account is gone, and caches on `flask.g`. |
| C2 | Fixed | `claim`/`unclaim`/`resolve` use atomic `UPDATE … WHERE status=…` with a rowcount check; the loser of a race gets a clean 409. |
| C3 | Fixed | Signup validates email format, password length (8–128, matching settings), and name length; task/help title (≤200) and description (≤5000) capped server-side. |
| C4 | Fixed | `HelpRequest.to_dict(viewer_id=…)` exposes emails only when the request is claimed/resolved **and** the viewer is the poster or claimer. All call sites pass the viewer. |
| Q1 | Fixed | Added a `pytest` suite under `tests/` (26 tests) covering XSS round-trip contract, auth/stale-session, atomic double-claim, email-exposure rules, validation, and per-user isolation. |

Note on C4: `/api/people` still returns every user's email by design (it's the team directory). If that directory isn't meant to be public, it should get the same viewer-aware treatment — flagged for your call, not changed.

### Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests run against a throwaway temp SQLite database (`create_app()` now accepts a `test_config`), so they never touch `database.db`. All 26 pass.

