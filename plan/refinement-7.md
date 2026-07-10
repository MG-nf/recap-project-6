# Refinement: Ticket 7 — Containerization & CI

Survey of the existing codebase against `plan/ticket-7.md`, via the security-reviewer, route-reviewer, service-reviewer, and data-reviewer subagents, adapted to infra/Docker/CI concerns since this ticket has no traditional route/service/data-layer work. All four confirm this is a from-scratch, greenfield setup (no `Dockerfile`/`docker-compose.yml`/`.github/` exist yet).

## Resolved during refinement (not left open for `/plan`)

**The cache-table/CI risk is a non-issue — verified empirically, not just by reasoning.** Both the route and data reviewers independently flagged a theoretical risk: since `django_cache_table` (backing `CACHES`'s `DatabaseCache`) is created by the `createcachetable` management command outside Django's migration framework, and `manage.py test` uses an ephemeral in-memory SQLite test database, they reasoned `accounts/tests.py::ThrottleTest` (which exercises the real DB-backed cache) might fail in a genuinely fresh CI environment with `OperationalError: no such table`. This contradicted this project's own observed history (the full suite, including `ThrottleTest`, has passed in every one of dozens of local `manage.py test` runs across six prior tickets). Dispatched a dedicated verification pass that read Django's actual installed source and ran the test directly:

- **`django/db/backends/base/creation.py`, line 114** (inside `BaseDatabaseCreation.create_test_db()`): unconditionally calls `call_command("createcachetable", database=self.connection.alias)` immediately after running migrations, every time a test database is created — regardless of which cache backend is configured or whether `createcachetable` was ever run against the real database.
- Confirmed empirically: `python manage.py test accounts.tests.ThrottleTest -v 2` passes cleanly (3/3), consistent with every prior full-suite run.

**Conclusion: `python manage.py test` needs zero special cache-table provisioning in CI.** This closes what would otherwise have been the single riskiest unknown in this ticket.

## Security review

| File Path | Issue Type | Brief Description |
|---|---|---|
| Dockerfile (new) | Secrets handling | Must never `COPY`/`ARG`/`ENV` a real `.env` or secret into image layers — `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS`/`OPENAI_API_KEY` supplied only at `docker run`/`docker-compose up` time. |
| .dockerignore (new) | Build-context leakage | Must exclude `.env*` (except `.env.example`, mirroring `.gitignore`), plus `.git/`, `__pycache__/`, `db.sqlite3`, `plan/`, `.playwright-mcp/`, `backlog.md`, `claude-edits.log`. |
| config/settings.py | DEBUG/SECRET_KEY interaction — design decision needed | `DEBUG` defaults to `True` with no `.env`, so `docker run` with no mounted `.env` starts successfully per AC1. If `/plan` instead wants `DEBUG=False` in Docker/compose (more production-like), that trips the existing fail-fast `ImproperlyConfigured` check unless a real `SECRET_KEY` is also supplied — must be an explicit choice, not stumbled into. |
| docker-compose.yml (new) | Secrets handling | Use `env_file: .env` rather than inlining real values under `environment:`. |
| .github/workflows/main.yml (new) | CI secrets | Confirmed: every AI-related test mocks `get_client`/uses `FakeOpenAIClient` — zero real secrets needed for `manage.py test` to pass in CI. |
| .github/workflows/main.yml (new) | Trigger scope | AC only requires `on: push`; this project's no-PR workflow constraint means `pull_request` would be dead weight — push-only is correct. |
| docker-compose.yml (new) | Port binding | Binding `0.0.0.0` inside the container is required/expected container networking (for the mapped port to be reachable), not an "unsafe bind" regression. |

## Route/infra review

| File Path | Issue Type | Brief Description |
|---|---|---|
| config/settings.py (`ALLOWED_HOSTS`) | Docker host validation | Confirmed Django behavior: `DEBUG=True` + empty `ALLOWED_HOSTS` validates the `Host` header against `['.localhost', '127.0.0.1', '[::1]']` automatically (not a blanket bypass) — `docker run -p 8000:8000` + `curl localhost:8000` satisfies this with zero extra config. Won't cover a compose service-name hostname if that's ever needed for inter-container health checks. |
| Dockerfile/entrypoint (new) | `migrate`/`createcachetable` automation | `createcachetable` is confirmed idempotent (skips with a message if the table exists) — safe to run unconditionally on every container start, changing ticket 2's "one-time manual step" framing to "automatic." `/plan` should decide entrypoint-automatic vs. documented manual `docker-compose exec` step. |
| docker-compose.yml (new) | Volumes/persistence | Bind-mounting the repo root for live-reload naturally includes `db.sqlite3` (it lives at `BASE_DIR`) — no separate named volume needed. |
| Dockerfile (new) | Container user | `python:3.12-slim` runs as root by default; blueprint implies no `USER` directive. Decision needed: non-root user (avoids UID/permission friction against the bind-mounted, host-owned `db.sqlite3`) vs. accepting root for this single-developer, dev-only setup. |
| .github/workflows/main.yml (new) | Python version parity | Target `actions/setup-python` at 3.12 to match the Dockerfile's base image, rather than an arbitrary version. |
| CLAUDE.md | Documentation drift risk | If `migrate`/`createcachetable` become automatic in the container, `CLAUDE.md`'s "Common commands" section (currently documents `createcachetable` as manual) needs a corresponding update. |

## Service layer review

Confirmed CI-tooling questions (pytest vs. `manage.py test`) fall outside this reviewer's mandate (correctly declined to guess) — resolved directly with you instead, below. One useful confirmation: neither `goals/services.py` nor `accounts/services.py` branches on `settings.DEBUG` anywhere — service-layer behavior is identical regardless of the Docker/CI `DEBUG` setting, so that interaction is purely a `config/settings.py`-level concern (see security review above), not a service-layer one.

## Data layer review

| File Path | Issue Type | Brief Description |
|---|---|---|
| config/settings.py (`DATABASES.OPTIONS.init_command`) | WAL sidecar files | `PRAGMA journal_mode=wal` creates `db.sqlite3-wal`/`db.sqlite3-shm` companion files. The bind-mount must cover the containing directory, not just the single `db.sqlite3` file, or these companions live only in the ephemeral container layer. |
| django/db/backends/sqlite3/creation.py | Test-DB isolation — confirmed | Test DB defaults to `:memory:` (no `TEST` key configured) — fully ephemeral, separate from `db.sqlite3`; CI needs no persistence/seeding of the real database file. |
| .dockerignore/Dockerfile (new) | Data-loss framing (informational) | If `db.sqlite3` were baked into the image at build time instead of bind/volume-mounted, every `docker build`/container recreation would silently revert to that snapshot — low-severity given this is explicitly dev-only infra, but a deliberate trade-off to note, not a silent surprise. `db.sqlite3` (and `-wal`/`-shm`) must be in `.dockerignore` regardless. |
| — | Schema/migrations | None needed — purely infra/deployment config, no model changes. |

## Scope decisions for `/plan`

1. **Cache table**: resolved above — no special CI handling needed; `createcachetable` automation for the Docker/compose *runtime* environment (not CI) is still an open call (entrypoint-automatic vs. manual step).
2. **`ALLOWED_HOSTS`**: rely on Django's implicit `DEBUG`+empty-list localhost allowance, or set it explicitly in compose — needs confirming with you.
3. **`DEBUG` in Docker/compose**: keep the default `True` (AC1 "just works," matches this project's dev-only framing) vs. `False` (requires also supplying a real `SECRET_KEY`) — needs confirming with you.
4. **Test runner**: `pytest`+`pytest-django` (new dependency) vs. keep `python manage.py test` (zero new dependencies, matches all six prior tickets) — needs confirming with you.
5. **`migrate`/`createcachetable` automation** in the Docker/compose runtime: entrypoint-automatic vs. documented manual step — needs confirming with you.
6. **Container user**: root (simplest, matches dev-only framing) vs. non-root (avoids bind-mount permission friction) — needs confirming with you.
7. **CI scope**: keep to exactly what the AC asks (install deps + run full test suite) rather than also adding `manage.py check`/linting/coverage that wasn't requested — recommend minimal scope, confirming with you.
