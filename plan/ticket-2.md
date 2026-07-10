# Ticket 2: Authentication & Profile

**GitHub Issue:** [#2](https://github.com/MG-nf/recap-project-6/issues/2)
**Project Board Status (at intake):** Ready

## Blueprint

Use `django.contrib.auth`. Extend `AbstractUser` for the `Profile` model (or `OneToOneField` to `User`).

## Acceptance Criteria

- [ ] `Profile` model with fields: `name`, `cohort`, `focus_area` (ManyToManyField/ArrayField).
- [ ] Auth flow: Sign-up, Login, Logout functional.
- [ ] Data Isolation: User `Profile` views must restrict access to `request.user` data only.

## Current-state notes (from repo inspection)

- No Django apps exist yet — this is the first app to be scaffolded (via `python manage.py startapp`), per `CLAUDE.md`'s architecture guidance.
- `INSTALLED_APPS` in `config/settings.py` currently only has Django's built-in contrib apps (`admin`, `auth`, `contenttypes`, `sessions`, `messages`, `staticfiles`) — `django.contrib.auth` is already installed and available to build on.
- `.claude/rules.md` mandates Django REST Framework (not Django Templates) for API work, with Route/Service/Data layers kept separate once this app is built — `djangorestframework` is not yet in `INSTALLED_APPS` or `requirements.txt` and will need to be added.
- No `requirements.txt` entry for DRF yet (ticket 1 only pinned `asgiref`, `Django`, `sqlparse`, `tzdata`).
