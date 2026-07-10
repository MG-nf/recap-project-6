# Refinement: Ticket 1 — Project Scaffolding

Survey of the existing codebase against `plan/ticket-1.md`, via the security-reviewer, route-reviewer, service-reviewer, and data-reviewer subagents.

## Security review

| File Path | Issue Type | Brief Description of Inconsistency |
|---|---|---|
| config/settings.py | Hardcoded secret (A02/A05) | `SECRET_KEY` is the plaintext `django-insecure-...` value from `startproject`, committed to source, not read from an env var. |
| config/settings.py | Security misconfiguration (A05) | `DEBUG = True` hardcoded, no environment-based toggle. |
| config/settings.py | Security misconfiguration (A05) | `ALLOWED_HOSTS = []` with no env-based override mechanism. |
| config/settings.py | Missing production hardening (A05) | No `SECURE_SSL_REDIRECT`/`SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`/HSTS overrides (Django defaults only) — informational at this stage. |
| (repo-wide) | Missing dependency pinning (A06) | No `requirements.txt`/`pyproject.toml` — this is acceptance criterion 2 of ticket 1, confirmed still open. |
| .gitignore | Sensitive-file exposure risk | `db.sqlite3` is not gitignored; any seeded data (e.g. superuser password hash) risks being committed. |
| .gitignore | Missing secret-management scaffolding | `.env*` is ignored but nothing in the code reads from environment variables yet, so the ignore rule is currently unused. |

## Route review

Only entry point is the default `admin/` route in `config/urls.py`. No custom apps/views exist yet — nothing to audit for Request/Response pattern or error handling. Not a defect; matches the expected from-scratch state.

## Service layer review

No service-layer code exists anywhere in the repo (no `services.py`/`services/` modules, no custom Django apps). Nothing to audit.

## Data layer review

No `models.py`, `apps.py`, or `migrations/` exist. `DATABASES['default']` in `config/settings.py` is hardcoded to SQLite via `BASE_DIR / 'db.sqlite3'` with no env-based indirection — acceptable for this ticket's scope, flagged for awareness as the project grows. No insecure SQL patterns found (none exist yet).

## Scope decision for this ticket

Ticket 1's three acceptance criteria:
1. **Runnable via `manage.py runserver`** — already satisfied (pre-existing scaffolding).
2. **Virtual environment configured / `requirements.txt` present** — **open**. This is the actionable work for this ticket.
3. **Git repo initialized with `.gitignore`** — already satisfied, but the security review surfaced one gap in it: `db.sqlite3` should be added to `.gitignore` since it's a project-state file, not source.

The `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS` hardening findings are standard `startproject` output, out of scope for this scaffolding ticket, and are recorded here so they aren't lost — they belong in a future settings/config-hardening ticket, not this one.

**Plan for `/plan`:** two acceptance-criterion-sized steps — (1) add `requirements.txt` pinning the installed Django version, (2) add `db.sqlite3` to `.gitignore`.
