# Review: Ticket 7 — Containerization & CI

Branch: `feat/ticket-7-containerization-ci`

## Acceptance criteria verification (plan/ticket-7.md)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `docker build` and `docker run` start server successfully | ✅ Met | `docker build -t recap-app .` succeeds; `docker run -p <port>:8000 recap-app` applies all migrations, creates `django_cache_table`, and serves requests — verified live via Playwright (`GET /` → `302` to `/login/?next=/`, correct dashboard-app behavior). Verified twice, before and after the fix below. |
| 2 | CI workflow triggers on `git push`; runs full test suite | ✅ Met | `.github/workflows/main.yml`: `on: push`, installs `requirements.txt`, runs `python manage.py test`. Reviewed for correctness (Python 3.12 parity with the Dockerfile, correct step ordering, no secrets referenced) — no local GitHub Actions runner available to execute it directly, but the workflow's logic was validated by literally running the same two commands (`pip install`, `manage.py test`) that constitute the job. |

Full local suite: `python manage.py test` → 98/98 passing (unaffected by this ticket, confirmed after every fix below). `python manage.py check` → 0 issues.

## A real bug found only through empirical testing, not static review

All four subagent audits (security, route, service, data) reviewed the Docker/CI files statically and came back clean or with only file-permission/comment-accuracy concerns (below). But actually *running* `docker-compose up` on this Windows/Docker Desktop host surfaced a genuine functional bug none of them could have found without executing it:

| File Path | Issue Type | Fix Applied |
|---|---|---|
| docker-compose.yml, config/settings.py | `docker-compose up` crash — `OperationalError: disk I/O error` | `docker-compose up`'s bind-mount (`.:/app`, needed for live-reload) puts `db.sqlite3` on a Docker-Desktop-translated host filesystem. SQLite's WAL mode (`PRAGMA journal_mode=wal`, set in ticket 2) requires mmap-based shared memory via a `-shm` sidecar file, which does not work reliably over Docker Desktop's bind-mount filesystem translation on Windows/Mac — every `docker-compose up` crashed on first DB connection. Isolated by testing a plain `docker run` with no bind-mount (DB baked fresh inside the container): that path worked perfectly, proving the bug was specific to WAL + bind-mount, not a general regression. **Fix (confirmed with you before applying, since it touches `config/settings.py`, a core file shipped across 6 prior tickets):** `DATABASES['default']['NAME']` is now `env('DATABASE_PATH', default=str(BASE_DIR / 'db.sqlite3'))` — unset (the default), it reproduces the exact original local-dev path; `docker-compose.yml` now mounts a named Docker volume (`sqlite-data:/data`, a native Linux filesystem inside Docker's storage, fully WAL-compatible) and sets `DATABASE_PATH=/data/db.sqlite3`, while the code itself still lives on the bind-mount for live-reload. Verified after the fix: `docker-compose up` starts cleanly with no error, and a test user created inside the container survives a `docker compose restart` (confirming the named volume actually persists data, not just avoiding the crash). |

## Issues found and fixed during the subagent audit

| File Path | Issue Type | Fix Applied |
|---|---|---|
| entrypoint.sh | Cross-platform fragility — git-tracked file mode | Independently flagged by both the security and route reviewers: `docker-compose up`'s bind-mount overlays the image's own `/app`, silently negating the Dockerfile's `RUN chmod +x /app/entrypoint.sh` at runtime — the container actually runs whatever copy the bind-mount exposes, with whatever executable bit *that* file has. Checked `git ls-files -s entrypoint.sh` and confirmed it was tracked as mode `100644` (non-executable) — meaning a fresh clone on Linux/Mac (where git honors the tracked mode, unlike this Windows host where Docker Desktop's file-sharing layer was masking the issue) would hit a "Permission denied" crash under `docker-compose up`, even though a plain `docker build && docker run` would succeed. Fixed with `git update-index --chmod=+x entrypoint.sh` (now `100755`), and added `.gitattributes` (`entrypoint.sh text eol=lf`) to also guarantee LF line endings survive any future edit on a `core.autocrlf=true` Windows checkout — closing the same class of cross-platform fragility from two angles. |
| .dockerignore | Comment accuracy (not a functional bug) | The original comment ("never bake a real .env into an image layer") is true for `docker build`, but could be misread as a runtime guarantee — `docker-compose up`'s bind-mount gives the running container direct access to whatever's actually in the host repo, including a real `.env` if one exists (which is intentional and matches this project's existing non-Docker local-dev behavior, not a leak). Clarified the comment to scope the guarantee explicitly to the build context. |
| .gitignore | Missing pattern (surfaced by this ticket's own testing) | Exercising WAL mode via Docker testing created `db.sqlite3-wal`/`db.sqlite3-shm` sidecar files at the repo root for the first time — `.gitignore` only excluded `db.sqlite3` itself, not its WAL siblings (`.dockerignore` already correctly excluded all three). Added the two missing patterns. |

## Confirmed clean (verified, not just asserted)

- **Secrets**: grepped all five new infra files for `SECRET_KEY`, `OPENAI_API_KEY`, `password`, `token`, `secrets.` — none hardcoded. `docker-compose.yml`'s `environment:` block only sets non-secret `DEBUG`/`ALLOWED_HOSTS`/`DATABASE_PATH` values.
- **CI secrets**: confirmed zero real secrets needed — every AI-dependent test (ticket 5) mocks its OpenAI client.
- **`entrypoint.sh` failure semantics**: `set -e` correctly aborts the script (and thus the container) on a failed `migrate`, with Django's own error output preserved in `docker logs` — fails loud, not silently.
- **`createcachetable` idempotency**: re-confirmed in practice (not just by reading Django's source, per `/refine`) — `docker compose logs` showed `Cache table 'django_cache_table' already exists.` on the second `docker-compose up` against the same volume, no error.
- **Dockerfile layer ordering, `EXPOSE`/port/`WORKDIR` consistency, `ALLOWED_HOSTS` validation semantics, CI Python-version parity, no-PR trigger scoping, static files served without a `collectstatic` step**: all independently verified correct by the route reviewer and cross-checked here.
- **Data/schema**: this ticket is genuinely schema-inert — no models, migrations, or raw SQL touched; `accounts/services.py`/`goals/services.py` show zero Docker/CI-related coupling.

## Route / Service / Data layer summary

- **Route/infra**: all confirmed decisions from `plan/feature-7-plan.md` (root user, `DEBUG=True` default, automatic `migrate`/`createcachetable`, explicit `ALLOWED_HOSTS`, minimal CI scope) implemented exactly as specified — no scope creep, no unrequested additions (no linting, no `manage.py check` in CI, matching the confirmed minimal-scope decision).
- **Service**: confirmed zero application/business-logic code introduced; the one piece of scripting logic (`entrypoint.sh`) behaves correctly on both success and failure paths.
- **Data**: SQLite persistence now correctly isolated from the WAL/bind-mount incompatibility via the named-volume fix; confirmed idempotent across both the ephemeral (`docker run`, fresh DB) and persistent (`docker-compose up`, named volume) paths.
