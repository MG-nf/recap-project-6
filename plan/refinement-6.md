# Refinement: Ticket 6 — Dashboard, UI, & Reporting

Survey of the existing codebase against `plan/ticket-6.md`, via the security-reviewer, route-reviewer, service-reviewer, and data-reviewer subagents. This is the project's first-ever server-rendered HTML (every prior ticket was pure DRF/JSON) and by far the largest ticket to date — full CRUD templates for Goals/Sessions/Resources plus a Dashboard, plus navigation, plus (implicitly) browser-based auth.

## Security review

| File Path | Issue Type | Brief Description |
|---|---|---|
| repo-wide | XSS precedent | Zero existing `\|safe`/`mark_safe`/`autoescape off` anywhere — nothing to copy incorrectly. New templates must rely on Django's default auto-escaping for all user-controlled fields (`Goal.title/desc`, `LearningSession.notes`, `Resource.title/url`), never disable it. |
| goals/models.py (`Resource.url`) | href injection | `URLField` already restricts schemes (ticket 4) — defense in depth, not a reason to skip escaping when rendered as `<a href="{{ resource.url }}">`. |
| config/settings.py (MIDDLEWARE) | CSRF — dual mechanism | `CsrfViewMiddleware` is active; any new Django `<form>` needs `{% csrf_token %}`. This is separate from DRF `SessionAuthentication`'s CSRF enforcement (ticket 2) — `/plan` must pick, per view, whether template pages POST to Django form views (needs `{% csrf_token %}`) or call the existing `/api/...` endpoints via `fetch` (needs `X-CSRFToken` header) — not both inconsistently. |
| accounts/services.py (`authenticate_user`) | Auth gap — reusable, safe precedent | Already returns a generic `InvalidCredentialsError` regardless of whether the username exists (no enumeration) and is `request`-decoupled — directly reusable from a template login view; already-established session-fixation protection (`login()` rotates the session key) carries over for free if reused. |
| goals/services.py | Data isolation (mandatory, unchanged) | Every new template view (Dashboard, Goal/Session/Resource list/detail/create/edit/delete) must route through the existing `goals_for_user`/`get_goal_for_user`/etc. — a template view calling `Goal.objects.get(pk=pk)` directly would be the same class of IDOR bug as an API view would have. |
| config/settings.py (`STATIC_URL`) | Static-files config gap | Only `STATIC_URL` is set — no `STATICFILES_DIRS`/`STATIC_ROOT` exist. Needs a decision (see route review), not a security issue on its own (no file uploads exist). |

## Route review

| File Path | Issue Type | Brief Description |
|---|---|---|
| config/urls.py | App placement | Both existing `include()`s are scoped under `/api/`. Recommend a **new dedicated app** (e.g. `dashboard`) for the template layer rather than extending `accounts`/`goals` — `goals/views.py` already holds 8 DRF view classes; adding ~15-20 template views there would roughly triple its surface and mix two different route "shapes" in one file. |
| goals/services.py | View pattern | Service functions are plain functions (`get_goal_for_user(user, pk)`), not model managers/querysets — Django's generic CBVs (`ListView`/`CreateView`/etc.) assume direct ORM/model-form access and would fight this. Recommend **function-based template views** calling the existing service functions directly, wrapped in try/except mirroring `goals/views.py`'s existing exception-handling style — not generic CBVs. |
| accounts/views.py | Auth gap | No HTML login form exists anywhere. A template view calling `authenticate_user` + `django.contrib.auth.login(request, user)` (same pattern the DRF `LoginView` already uses) stays consistent with this app's conventions — needs an explicit decision on scope (see below) and which app owns the template. |
| config/settings.py (TEMPLATES, STATIC_URL) | Navigation / shared base template | `TEMPLATES[0]['DIRS']` is empty; `APP_DIRS=True`. A shared `base.html` needs either a top-level `templates/` dir (registered in `DIRS`) or living in the new app's `templates/` dir loaded via `APP_DIRS`. Top-level avoids inter-app load-order coupling since `accounts`, `goals`, and the new app would all need to `{% extends %}` from it — recommended. Static assets (`STATICFILES_DIRS`) should follow the same top-level-vs-per-app decision, kept consistent with the template choice. |
| goals/urls.py | Collision check | No collision risk confirmed — new root-level template paths (`/dashboard/`, `/goals/`, `/goals/<pk>/edit/`) are a distinct prefix from everything under `/api/`. |

## Service layer review

| File Path | Issue Type | Brief Description |
|---|---|---|
| goals/services.py | Goal-counts-by-status | No existing function. `status` is a plain DB column — fits a clean `Goal.objects.filter(user=user).values('status').annotate(count=Count('id'))`, matching the blueprint's explicit "use annotate/aggregate" instruction (unlike `resources_by_type_for_goal`'s Python-loop precedent, which shouldn't be copied here). |
| goals/models.py (`LearningSession.tags`) | Duration-by-tag constraint | `JSONField`, free-form list — SQLite can't unnest a JSON array in `annotate()`/`aggregate()`. Needs Python-side aggregation over a `sessions_for_user(user)`-scoped fetch (`.values('duration', 'tags')`), summing per tag in Python. This is a necessity here, not a style choice. |
| goals/services.py | Open question — tag-aggregation scope | Neither the blueprint nor the AC says whether "duration per tag" is per-goal or user-wide across all goals. Needs a `/plan` decision. |
| goals/models.py (`LearningSession.date`) | Duration-by-week | Real `DateField` — `django.db.models.functions.TruncWeek` should work cleanly with `.annotate(week=TruncWeek('date')).values('week').annotate(total=Sum('duration'))` on SQLite, no Python fallback needed (unlike tags). |
| goals/services.py | Template-view reuse | Existing CRUD functions (`list_goals_for_user`, `create_goal`, `get_goal_for_user`, `update_goal`, `delete_goal`, and the session/resource equivalents) are already framework-agnostic — callable identically from Django form-backed template views as from the existing DRF views. No new service-layer entry points needed for CRUD; only the presentation layer (form vs. serializer) differs. |
| goals/views.py | Exception handling in template views | Existing exceptions (`GoalNotOwnedError`, `Goal.DoesNotExist`, etc.) can be reused, translated to `Http404`/redirect-with-message instead of JSON — no new service-layer exception types needed. |

## Data layer review

| File Path | Issue Type | Brief Description |
|---|---|---|
| goals/models.py (`Goal.Meta.indexes`) | Indexing — sufficient | Existing `(user, status)` index already covers the goal-counts-by-status query (filter + group-by). No new index/migration needed. |
| goals/models.py (`LearningSession`) | Indexing — judgment call | No `Meta.indexes` exists on `LearningSession` at all. A `TruncWeek` group-by via `goal__user=user` will join+scan without a covering index — likely premature given this project's expected per-user scale (same judgment ticket 3/4 already made elsewhere). `/plan` should record this as a deliberate, documented deferral, not a silent gap. |
| goals/models.py (`tags`) | Zero-tag sessions | `tags` defaults to `[]` and is valid empty — a session with no tags contributes to no per-tag bucket under a naive tally, silently under-representing total logged duration. Needs a `/plan` decision: explicit "untagged" bucket vs. documented omission. |
| goals/services.py | Per-user scoping (mandatory, unchanged) | Both new reports must build on `goals_for_user(user)`/`sessions_for_user(user)`, not a fresh unscoped query — no cross-user leakage in either report. |
| goals/services.py | Return-type mapping | `.values('status').annotate(...)` returns plain dicts, unlike every existing service function (model instances or dict-of-model-instance-lists). No existing convention covers this — `/plan` should pick a consistent shape (plain dict is simplest, no need to introduce a dataclass/namedtuple for two reports) before it reaches template context. |
| goals/migrations | Schema scope | No new model/migration needed — this ticket is stateless from a schema perspective, same as ticket 5. |

## Scope decisions for `/plan`

1. **App placement**: new dedicated `dashboard` app (not extending `accounts`/`goals`) — confirmed by route + service reviewers independently.
2. **URL namespace**: root-level paths (`/dashboard/`, `/goals/`, `/goals/<pk>/edit/`, etc.), separate `include()` from `/api/` — no collision risk.
3. **View pattern**: function-based template views calling existing service functions directly (not Django's generic CBVs, which don't fit this project's service-function data-access pattern).
4. **Base template/static layout**: top-level `templates/`/`static/` directories (registered in `TEMPLATES[0]['DIRS']`/`STATICFILES_DIRS`) rather than per-app, to avoid inter-app load-order coupling since multiple apps' templates need to extend a shared `base.html`.
5. **CSRF strategy**: template pages use Django forms + `{% csrf_token %}` (not fetch calls to the existing JSON API) — keeps one consistent mechanism per view type rather than mixing both.
6. **Open decisions requiring your input at `/plan`**:
   - **Auth gap**: should this ticket add template-based login/logout (and possibly signup)? Not explicitly listed in the ACs, but every new page requires `IsAuthenticated`/a session, so without it the UI is unreachable from a browser — "intuitive movement" (AC5) arguably requires it.
   - **Duration-by-tag scope**: per-goal or dashboard-wide across all of a user's goals?
   - **Untagged sessions**: show as an explicit "untagged" bucket in the tag report, or omit silently?
   - **Styling approach**: plain authored CSS (no framework/CDN dependency, consistent with this project's minimal-dependency history) vs. a lightweight CSS framework.
