# Refinement: Ticket 3 — Goals & Sessions (CRUD)

Survey of the existing codebase against `plan/ticket-3.md`, via the security-reviewer, route-reviewer, service-reviewer, and data-reviewer subagents. This is the second app in the repo (`accounts`, from ticket 2, is the only precedent) — its conventions (DRF generics, thin views, service-layer functions, `request.user`-scoped querysets, Route/Service/Data separation) are the baseline to extend, not redesign.

## Security review

| File Path | Issue Type | Brief Description |
|---|---|---|
| accounts/views.py (`ProfileView.get_object`) | Authorization pattern to reuse | Scope every retrieve/update/delete view's `get_queryset()` to `request.user` (e.g. `Goal.objects.filter(user=self.request.user)`) so DRF's generic `get_object()` 404s on other users' rows rather than leaking them via IDOR. |
| accounts/serializers.py | Mass-assignment precedent | `user` must never be a writable serializer field — set server-side from `request.user`, never taken from client input, same as `Profile.user` today. |
| new: goals/serializers.py | FK ownership validation (new case) | `LearningSession.goal` is the first client-supplied cross-model FK in this codebase — must validate the referenced `Goal` belongs to `request.user` before attaching a session to it, or a user could attach sessions to another user's goal. |
| config/settings.py | Auth/permission defaults (reuse, no change) | `SessionAuthentication` + `IsAuthenticated` are already project-wide defaults; new views should still declare `permission_classes = [IsAuthenticated]` explicitly, matching `accounts` style. |
| config/settings.py | CSRF (no change, just a constraint) | `SessionAuthentication` enforces CSRF on unsafe methods — session-authenticated write requests need `X-CSRFToken`. Relevant for `/review`'s manual verification pass. |
| accounts/throttles.py | Throttle scope | `AuthRateThrottle` is IP-keyed and scoped to pre-auth abuse (`signup`/`login`) — wrong fit for post-auth CRUD. Decision below: no new throttling this ticket. |
| plan/ticket-3.md | Status filter + isolation ordering | Isolation must be unconditional and filtering layered on top (`.filter(user=request.user).filter(status=...)`), never the reverse. |

## Route review

| File Path | Issue Type | Brief Description |
|---|---|---|
| config/urls.py | URL prefix convention | Mirror `path('api/auth/', include('accounts.urls'))` → `path('api/goals/', include('goals.urls'))`. |
| accounts/urls.py | Naming/structure | Flat, explicit `path()` list with `.as_view()` + `name=`, no routers/viewsets — carry the same style into `goals/urls.py`. |
| accounts/views.py | View-class pattern | DRF generics (not raw `APIView` where a generic fits), explicit `permission_classes` per view even where redundant with the settings default. |
| accounts/services.py | Thin-view pattern | `status` GET-param is read in the view, but the actual filter logic belongs in a `goals/services.py` function, not inlined into `get_queryset()`. |
| requirements.txt | No `django-filter` | Not installed; `status` filter must be hand-rolled (no `filterset_fields`/`DjangoFilterBackend`). |
| n/a | Nesting vs. flat routing | No nested-router precedent exists in this codebase. Decision below: flat routes. |
| config/settings.py | No pagination precedent | First list-type endpoint in the project. Decision below: skip pagination, out of AC scope. |

## Service layer review

| File Path | Issue Type | Brief Description |
|---|---|---|
| accounts/services.py | Function shape to mirror | Plain functions, keyword-only args, never take `request` — e.g. `list_goals_for_user(user, status=None)`, `create_goal(*, user, title, desc, status)`. |
| accounts/services.py / views.py | Exception translation pattern | Custom exceptions raised in service, caught/translated to HTTP status in the view — `goals` app should define its own exceptions rather than importing `accounts`'. |
| accounts/views.py (`ProfileView.get_object`) | "Not found or not yours" → 404, not 403 | Ticket 2's precedent: `.filter(user=...)` naturally excludes other users' rows, so lookups 404 rather than 403. Same pattern applies to Goal/Session detail views. |
| accounts/services.py (`register_user`) | `transaction.atomic()` precedent | Only needed for multi-step writes; single-model Goal/Session create/update don't require it, but any tags M2M + row write together should follow the pattern if tags end up modeled as M2M (not chosen — see data review). |

## Data layer review

| File Path | Issue Type | Brief Description |
|---|---|---|
| accounts/models.py (`Profile.user`) | FK-to-user convention | Use `settings.AUTH_USER_MODEL`, not `django.contrib.auth.models.User` directly, for swappable-user-model safety. |
| accounts/models.py (`FocusArea`) | Choices precedent doesn't fit `status` | `FocusArea` is a shared lookup table (M2M); `Goal.status` is a single per-row attribute — `CharField` + `choices=` (`TextChoices`) fits better than a lookup table. |
| n/a | `tags` field type (no precedent) | SQLite has no native array type. Candidates: delimited `CharField`, `JSONField`, or M2M `Tag` model. Decision below: `JSONField`. |
| n/a | `duration` field type (no precedent) | `PositiveIntegerField` (minutes) vs `DurationField` (timedelta). Decision below: `PositiveIntegerField`. |
| accounts/services.py (`get_profile_for_user`) | Literal AC wording vs. blueprint's field list | AC says "all querysets use `.filter(user=request.user)`", but the blueprint only gives `LearningSession` an FK to `Goal`, not to `User`. Decision below: interpret the AC as the isolation *principle*, satisfied transitively via `goal__user=request.user` — no denormalized `user` FK on `LearningSession`. |
| accounts/models.py (`related_name`) | Naming convention | Plural `related_name` for one-to-many/reverse accessors (`related_name="goals"`, `related_name="sessions"`), matching `focus_area`'s `related_name="profiles"`. |
| n/a | Timestamp convention (undefined until now) | First ticket to need "timestamps" — fixing the convention now: `created_at = DateTimeField(auto_now_add=True)`, `updated_at = DateTimeField(auto_now=True)`. |
| n/a | Indexing | `status` is filtered alongside the mandatory `user` scope — composite `Meta.indexes` on `(user, status)` keeps that combined lookup performant. |

## Scope decisions for `/plan`

1. **`Goal` model**: `user` = `ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="goals")`; `title` = `CharField`; `desc` = `TextField`; `status` = `CharField(choices=<TextChoices>, default=...)`; `created_at`/`updated_at` per the timestamp convention above. Composite index on `(user, status)`.
2. **`LearningSession` model**: `goal` = `ForeignKey(Goal, on_delete=CASCADE, related_name="sessions")`; `date` = `DateField`; `duration` = `PositiveIntegerField` (minutes); `notes` = `TextField`; `tags` = `JSONField(default=list, blank=True)` (list of strings, no fixed set). **No direct `user` FK** — isolation via `goal__user=request.user` (see data-review decision above); this is a deliberate interpretation of the AC, to be called out again at `/review`.
3. **Routes**: new `goals` app, flat explicit paths — `api/goals/`, `api/goals/<pk>/`, `api/sessions/`, `api/sessions/<pk>/` — `LearningSession` filtered flat via `?goal=<id>` query param, not nested URLs. DRF generics (`ListCreateAPIView`, `RetrieveUpdateDestroyAPIView`), `permission_classes = [IsAuthenticated]` explicit on every view. No pagination (out of AC scope), no new throttling (not an abuse-sensitive endpoint class like signup/login).
4. **Service layer**: `goals/services.py` with `create_goal`, `list_goals_for_user(user, status=None)`, `get_goal_for_user(user, pk)`, `update_goal`, `delete_goal`, and parallel `create_session`, `list_sessions_for_goal(user, goal_id=None)`, `get_session_for_user`, `update_session`, `delete_session`. All take primitives/model instances, never `request`. `create_session` validates the referenced `goal` belongs to `user` before creating (FK ownership check, security-review finding).
5. **Serializers**: `user`/`goal`-ownership never client-writable beyond a validated `goal` id; `status` GET-param validated against `Goal`'s choices in the service layer, returning 400 on an unrecognized value (mirrors `SignUpSerializer.validate_focus_area`'s reject-unknown-values pattern) rather than silently ignoring it.
6. **No new dependencies**: no `django-filter`; hand-rolled `status` filter, consistent with `requirements.txt` currently having nothing beyond DRF for API concerns.
