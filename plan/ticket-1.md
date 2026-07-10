# Ticket 1: Project Scaffolding

**GitHub Issue:** [#1](https://github.com/MG-nf/recap-project-6/issues/1)
**Project Board Status (at intake):** Ready

## Blueprint

Initialize using `django-admin startproject`. Maintain a clean directory structure separating `settings` and `apps`.

## Acceptance Criteria

- [ ] Project initialized and runnable via `python manage.py runserver`.
- [ ] Virtual environment configured (or `requirements.txt` present).
- [ ] Git repository initialized with `.gitignore`.

## Current-state notes (from repo inspection)

- `django-admin startproject` has already been run: `manage.py` and the `config/` package (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`) exist, and `python manage.py runserver` is runnable — criterion 1 is already satisfied.
- Git repo is already initialized and `.gitignore` already exists (currently ignores `.env*`, `backlog.md`) — criterion 3 is already satisfied.
- No `requirements.txt` / `pyproject.toml` exists yet, and no virtual environment is recorded in the repo — criterion 2 is **not yet satisfied**. This is the remaining, actionable scope of this ticket.
