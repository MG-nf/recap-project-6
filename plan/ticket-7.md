# Ticket 7: Containerization & CI

**GitHub Issue:** [#7](https://github.com/MG-nf/recap-project-6/issues/7)
**Project Board Status (at intake):** Ready

## Blueprint

`Dockerfile` using `python:3.12-slim`. `docker-compose` for local orchestration. GitHub Actions `main.yml` for `pytest`.

## Acceptance Criteria

- [ ] `docker build` and `docker run` start server successfully.
- [ ] CI workflow triggers on `git push`; runs full test suite.

## Reinterpretation notice

The blueprint says GitHub Actions should run "`pytest`," but this project has never used pytest — every test across all six prior tickets is a Django `TestCase`/`APITestCase` run via `python manage.py test`, with zero `pytest`/`pytest-django` dependency anywhere in `requirements.txt`. The AC itself only requires "runs full test suite," not literally the `pytest` command. This needs an explicit decision at `/plan`: add `pytest`+`pytest-django` as new dependencies (pytest can run Django `TestCase` classes natively, but `pytest-django` is the idiomatic pairing and needs a settings-module config) vs. keep `python manage.py test` as the actual test runner in CI (zero new dependencies, matches every existing convention in this repo) and treat "pytest" as the blueprint's generic shorthand for "run the tests."

## Current-state notes (from repo inspection)

- No `Dockerfile`, `docker-compose.yml`, `.dockerignore`, or `.github/` directory exists anywhere in the repo yet — this is a from-scratch setup, same greenfield situation as ticket 6's templates.
- **Python version mismatch (informational, not necessarily a blocker):** the active local dev environment runs Python 3.14.6, but the blueprint specifies `python:3.12-slim` as the Docker base image. Since Docker provides an isolated environment, this should be fine as long as every pinned dependency in `requirements.txt` (`Django==6.0.7`, `djangorestframework==3.17.1`, `django-environ==0.14.0`, `openai==2.45.0`, `asgiref==3.11.1`, `sqlparse==0.5.5`, `tzdata==2026.2`) has a compatible wheel/sdist for 3.12 — Django 6.0 supports Python 3.12+, so this is expected to work, but should be verified by actually running `docker build` during `/implement`, not assumed.
- `config/settings.py` already reads `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS`/`OPENAI_API_KEY` via `django-environ` with insecure-but-functional local-dev defaults when no `.env` is present (tickets 1/2/5) — `docker run` with no mounted `.env` should still "start server successfully" per AC1 without any additional Docker-specific config, since `DEBUG` defaults to `True`.
- `CACHES` uses a DB-backed cache table (`django_cache_table`) requiring a one-time `python manage.py createcachetable` per environment (ticket 2) — this needs to happen somewhere in the Docker/CI setup (entrypoint script, `docker-compose` command chain, or CI workflow step) or DRF's auth throttling will hit `OperationalError: no such table` the first time `/api/auth/signup/`or `/login/` is exercised (tests may or may not hit this depending on whether they use the real cache table or an override).
- `.gitignore` already excludes `.env*`, `db.sqlite3`, `__pycache__/` — a new `.dockerignore` should mirror this (plus excluding `.git/`, `plan/`, and anything else not needed inside the image) to keep the build context/image lean and avoid ever baking a local `.env`/`db.sqlite3` into the image.
- No CI/lint/formatter tooling exists yet (per `CLAUDE.md`: "There is no configured linter, formatter, or CI yet") — this ticket is what introduces the first one. Scope should stay to what the AC asks (install deps, run full test suite, triggered on push) rather than also adding linting/formatting/coverage reporting that wasn't requested.
- `manage.py runserver` is the only server-start mechanism used anywhere so far (no gunicorn/uWSGI in `requirements.txt`) — "docker run ... start server successfully" (AC1) is satisfiable with `runserver`, consistent with this project's already-stated "unsuitable for production" framing (`config/settings.py`'s own comments) rather than requiring a production WSGI server, which would be new scope not requested by the ticket.
