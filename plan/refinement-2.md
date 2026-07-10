# Refinement: Ticket 2 — Authentication & Profile

Survey of the existing codebase against `plan/ticket-2.md`, via the security-reviewer, route-reviewer, service-reviewer, and data-reviewer subagents. No app code exists yet — this will be the first Django app in the repo.

## Security review

| File Path | Issue Type | Brief Description of Inconsistency |
|---|---|---|
| config/settings.py | Hardcoded secret | `SECRET_KEY` is the insecure `startproject` default — should move to an env var before real auth/sessions go live, since it signs session cookies. |
| config/settings.py | Insecure debug config | `DEBUG = True`, `ALLOWED_HOSTS = []` — pre-existing, but higher-stakes now that real auth/sessions are being added. |
| config/settings.py | Missing DRF auth config | No `djangorestframework` in `INSTALLED_APPS`, no `REST_FRAMEWORK` dict. Must pick `DEFAULT_AUTHENTICATION_CLASSES` and set `DEFAULT_PERMISSION_CLASSES` so new endpoints aren't accidentally `AllowAny`. |
| config/settings.py | Missing session/cookie hardening | No explicit `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`/`SESSION_COOKIE_SAMESITE` — Django defaults only. |
| config/urls.py | Missing auth/API routes | No app registered, no auth/profile routes exist. CSRF should be enforced via DRF's `SessionAuthentication`, not `csrf_exempt`. |
| Profile model (not yet created) | Data isolation / authz design | Should use `OneToOneField(User)` (not `AbstractUser`, since no `AUTH_USER_MODEL` override exists) with `permission_classes = [IsAuthenticated]` and querysets filtered by `request.user` on every profile view. |

Password hashing (PBKDF2 default) is untouched and fine. No SQLi/XSS/path-traversal surface exists yet — re-check at `/review` once serializers/views exist, especially for cross-user data leakage in serializer fields.

## Route review

Only entry point today is `admin/` in `config/urls.py` — no custom routes, no `include()` usage to mirror. For `/plan`: new app needs `rest_framework` + itself added to `INSTALLED_APPS`, an `include()` entry in `config/urls.py`, and its own `urls.py` keeping routes thin (Request → service layer → Response) with explicit error handling for expected failures (invalid credentials, duplicate username) rather than leaking 500s.

## Service layer review

No service-layer code exists anywhere (first app). Pattern must be established fresh — routes/views should stay thin and delegate to a service module per `.claude/rules.md` rule 3.

## Data layer review

No models/migrations exist yet. Key constraint: **`ArrayField` is Postgres-only and unusable on this project's SQLite backend** — `focus_area` must be modeled as `ManyToManyField` to a small lookup model (e.g. `FocusArea(name)`), not `ArrayField`. No `AUTH_USER_MODEL` override exists, so `OneToOneField(User)` is the lower-risk path vs. swapping in a custom user model this late.

## Scope decision for `/plan`

Ticket 2's three acceptance criteria translate into:
1. **Profile model** — `OneToOneField(User)`, fields `name` (CharField), `cohort` (CharField), `focus_area` (`ManyToManyField` to new `FocusArea` model).
2. **Auth flow** — sign-up, login, logout as DRF endpoints under a new `accounts` app, wired into `config/urls.py` via `include()`. Requires adding `djangorestframework` to `INSTALLED_APPS` and `requirements.txt`, plus a `REST_FRAMEWORK` settings block (session auth + `IsAuthenticated` default).
3. **Data isolation** — profile views/viewsets must filter querysets by `request.user` and require authentication.

Pre-existing `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS` hardening remains out of scope for this ticket (same call as ticket 1), but session-cookie hardening (`SESSION_COOKIE_SAMESITE` etc.) is in-scope this time since this ticket is what introduces real sessions — to be decided in `/plan`.
