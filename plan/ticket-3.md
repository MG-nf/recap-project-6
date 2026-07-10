# Ticket 3: Goals & Sessions (CRUD)

**GitHub Issue:** [#3](https://github.com/MG-nf/recap-project-6/issues/3)
**Project Board Status (at intake):** Ready

## Blueprint

Models: `Goal` (title, desc, status, timestamps), `LearningSession` (ForeignKey to `Goal`, date, duration, notes, tags).

## Acceptance Criteria

- [ ] Django Migrations created and applied.
- [ ] CRUD implemented for `Goal` and `LearningSession`.
- [ ] Filtering: Goals list view supports `status` filter (GET parameter).
- [ ] Security: All QuerySets must use `.filter(user=request.user)`.

## Current-state notes (from repo inspection)

- `accounts` app (ticket 2) already provides `django.contrib.auth` + a `Profile` model (`OneToOneField` to `User`) and a working signup/login/logout/profile API under `/api/auth/`, built with Django REST Framework, Route/Service/Data layers separated, and session authentication (`rest_framework.authentication.SessionAuthentication`) as the project-wide default (`config/settings.py`).
- No `Goal` or `LearningSession` models exist yet — this ticket needs a new Django app (e.g. `python manage.py startapp goals`, per `CLAUDE.md`'s architecture guidance), registered in `INSTALLED_APPS` and wired into `config/urls.py` via `include()`, following the same `/api/<app>/` prefix convention `accounts` established.
- `.claude/rules.md` mandates DRF (not Django Templates) for all API work, with Route/Service/Data layer separation — the four read-only audit subagents (`security-reviewer`, `route-reviewer`, `service-reviewer`, `data-reviewer`) will check for this, same as ticket 2.
- "Security: All QuerySets must use `.filter(user=request.user)`" implies `Goal` needs a direct or indirect FK to `User` (`LearningSession` inherits isolation transitively via its FK to `Goal`) — mirrors the data-isolation pattern `accounts.Profile` already established for ticket 2.
- `status` on `Goal` is unspecified in the blueprint beyond "status" — will need a concrete choice (e.g. `CharField` with `choices`) during `/refine`.
- `tags` on `LearningSession` is unspecified in type — ticket 1's `CLAUDE.md` notes the DB is SQLite (no native array field), so this will likely need a `CharField`/`M2M` decision during `/refine`, same category of decision ticket 2 made for `focus_area`.
- Existing throttle/cache infra (`AUTH_PASSWORD_VALIDATORS`, `CACHES` DatabaseCache, `AuthRateThrottle`) is scoped to auth endpoints only — no indication this ticket needs new throttling, but `/refine` should confirm.
