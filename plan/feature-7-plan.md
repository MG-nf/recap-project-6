# Feature Plan: Ticket 7 — Containerization & CI

Based on `plan/ticket-7.md` and `plan/refinement-7.md`. One step per acceptance criterion. This ticket has no unit-testable application code — "tests" here mean empirically verifying the infra actually does what the AC requires (`docker build`/`docker run` succeeding, the CI workflow correctly running the existing test suite), not new Python test cases.

## Decisions (confirmed with user)

- **Test runner**: keep `python manage.py test` in CI — zero new dependencies, matches every existing test file unchanged. The blueprint's "pytest" is treated as generic shorthand for "run the tests."
- **`DEBUG`**: defaults to `True` in `docker-compose.yml` (matches this project's existing no-`.env` local-dev default) — `docker-compose up` works with zero required configuration.
- **`migrate`/`createcachetable`**: run automatically on every container start via an entrypoint script (`createcachetable` is confirmed idempotent — safe to re-run unconditionally), so `docker run`/`docker-compose up` "just works" with no manual follow-up step.
- **Container user**: root — simplest, avoids bind-mount permission friction, consistent with this project's already-stated "unsuitable for production" framing.
- **`ALLOWED_HOSTS`**: set explicitly in `docker-compose.yml` (`localhost,127.0.0.1`, matching `.env.example`'s existing values) rather than relying on Django's implicit `DEBUG`+empty-list allowance.
- **CI scope**: minimal — install dependencies and run `python manage.py test` only, matching the AC literally. No `manage.py check`/linting/coverage added (not requested).
- **Resolved during `/refine`, not a decision**: the cache-table/CI risk both the route and data reviewers flagged is a non-issue — Django's `create_test_db()` unconditionally runs `createcachetable` against the ephemeral test database on every `manage.py test` invocation (`django/db/backends/base/creation.py:114`), confirmed by reading Django's source and running `ThrottleTest` directly. No special CI handling needed for this.

New files: `Dockerfile`, `.dockerignore`, `entrypoint.sh`, `docker-compose.yml`, `.github/workflows/main.yml`. No existing files need changes — this ticket is additive infra config only.

## Step 1 — AC1: "`docker build` and `docker run` start server successfully"

- **Verification (no unit test possible — this is infra, verified empirically):** run `docker build -t recap-app .` and confirm it completes without error; run `docker run -p 8000:8000 recap-app` (or `docker-compose up`) and confirm the container starts, runs `migrate`+`createcachetable` via the entrypoint without error, and the Django dev server binds successfully; `curl http://localhost:8000/` (or a browser hit) returns a response (404 is fine — root has no route — the point is the server answers, matching how ticket 1 originally verified "project runnable").
- **Implementation:**
  - `Dockerfile`: `FROM python:3.12-slim`, `WORKDIR /app`, copy `requirements.txt` and `pip install` (before copying the rest of the source, so dependency installation is Docker-layer-cached across rebuilds), copy the full source, copy+chmod `entrypoint.sh`, `EXPOSE 8000`, `ENTRYPOINT ["/entrypoint.sh"]`, `CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]`.
  - `entrypoint.sh`: `#!/bin/sh` script running `python manage.py migrate --noinput` then `python manage.py createcachetable` then `exec "$@"` (hands off to the Dockerfile's `CMD`).
  - `.dockerignore`: mirrors `.gitignore` (`.env*` except `.env.example`, `db.sqlite3`/`-wal`/`-shm`, `__pycache__/`, `*.pyc`) plus repo-specific non-runtime files (`.git/`, `plan/`, `.claude/`, `.playwright-mcp/`, `backlog.md`, `claude-edits.log`, `WORKFLOW_STATE.md`) — keeps the build context lean and guarantees no local secret/DB file is ever baked into an image layer.
  - `docker-compose.yml`: single `web` service, `build: .`, bind-mount the repo root (`.:/app`) for live-reload (this also makes `db.sqlite3` persist naturally, since it lives at the repo root), `ports: ["8000:8000"]`, `environment: [DEBUG=True, ALLOWED_HOSTS=localhost,127.0.0.1]`.

## Step 2 — AC2: "CI workflow triggers on `git push`; runs full test suite"

- **Verification (no unit test possible — validated by inspection + a local dry-run of the equivalent commands):** confirm `.github/workflows/main.yml` is valid YAML with `on: push` (no `pull_request`, matching this project's no-PR workflow constraint) and a job that installs `requirements.txt` then runs `python manage.py test`; locally reproduce the same two commands in a clean shell to confirm they'd succeed in a fresh CI runner with no `.env` (already verified in `/refine`: every AI-dependent test mocks its client, so zero secrets are needed).
- **Implementation:** `.github/workflows/main.yml` — `on: push`; one job (`ubuntu-latest`) that checks out the repo (`actions/checkout@v4`), sets up Python 3.12 (`actions/setup-python@v5`, matching the Dockerfile's base image for parity), installs `pip install -r requirements.txt`, then runs `python manage.py test`.
