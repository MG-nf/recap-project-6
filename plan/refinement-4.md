# Refinement: Ticket 4 — Resource Library

Survey of the existing codebase against `plan/ticket-4.md`, via the security-reviewer, route-reviewer, service-reviewer, and data-reviewer subagents. `Resource` is a child-of-`Goal` model, closely analogous to `LearningSession` (ticket 3) — that app's conventions are the baseline to extend, not redesign.

## Security review

| File Path | Issue Type | Brief Description |
|---|---|---|
| goals/serializers.py (`LearningSessionSerializer.__init__`) | IDOR / FK-scoping precedent to reuse | Scopes the `goal` `PrimaryKeyRelatedField`'s queryset to `Goal.objects.filter(user=request.user)`, so a foreign goal id and a nonexistent one return the same generic error. `ResourceSerializer.goal` must do the identical scoping — without it, a user could attach a `Resource` to another user's `Goal`, or enumerate other users' valid goal ids. |
| goals/services.py (`create_session`) | Defense-in-depth ownership check, required from the start this time | `create_session` also re-checks `goal.user_id != user.id` and raises `GoalNotOwnedError`, added as a fix *after* ticket 3's review found the serializer-only version left a gap for future non-serializer callers. `create_resource` should build both checks in from day one. |
| goals/services.py (`sessions_for_user`) | Transitive isolation precedent | No direct `user` FK on `LearningSession`; isolation via `.filter(goal__user=user)`. `Resource` should mirror this exactly — every read/update/delete path must route through a `resources_for_user(user)` helper, never `Resource.objects.all()`/unscoped `.get(pk=...)`. |
| goals/views.py (`GoalDetailView.get_object`) | 404-not-403 precedent | `Goal.DoesNotExist` → `Http404`, no existence leak. Any parent-goal lookup in the Resource-attach flow should reuse this exact pattern. |
| config/settings.py | Auth/permission baseline (reuse, no change) | No object-level permission class exists anywhere in this project; ownership is enforced entirely via queryset scoping + `get_object()` overrides — keep `Resource` views consistent with that, no new permission class needed. No new throttle scope needed either (not an abuse-sensitive endpoint class). |
| Resource.url (new field) | SSRF / open-redirect — confirmed out of scope | No server-side fetch of any stored URL exists anywhere in this codebase (grepped, none found) — this ticket only stores/serializes the URL. `URLField`'s built-in validator already restricts to http/https/ftp/ftps schemes (blocks `javascript:` payloads). No extra validation needed now; flag for a *future* ticket if link-preview/fetch is ever added. |

## Route review

| File Path | Issue Type | Brief Description |
|---|---|---|
| goals/urls.py | Route placement | No nested-router precedent anywhere in this repo (ticket 3 explicitly chose flat over nested for the same reason). `Resource` should get a flat `/api/resources/` list+create, filterable via `?goal=<id>` — mirroring `/api/sessions/?goal=<id>` — not `/api/goals/<id>/resources/`. |
| goals/views.py (`GoalDetailView`/`GoalSerializer`) | AC2 requires touching shipped ticket-3 code | "Goal detail view displays Resources grouped by type" can't be satisfied by a standalone resources endpoint alone — it means `GoalSerializer` needs a `resources_by_type` field. This is a deliberate, necessary modification to already-reviewed ticket-3 code, not scope creep — called out explicitly so `/plan`/`/review` don't flag it as unexpected. |
| goals/services.py | Grouping placement | Grouping logic should be a plain service function operating on model instances (not inline `itertools.groupby` in the serializer, not ORM `.values()/.annotate()` which would return dicts instead of model instances, breaking this app's return-type convention), called from a `GoalSerializer.SerializerMethodField`. |
| config/settings.py, config/urls.py | App placement | `Resource` FKs tightly to `Goal` the same way `LearningSession` does — belongs in the existing `goals` app (new migration, e.g. `0003_resource...`), not a new `resources` app. No `INSTALLED_APPS`/`config/urls.py` change needed; just a new `path("resources/", ...)` in `goals/urls.py`. |

## Service layer review

| File Path | Issue Type | Brief Description |
|---|---|---|
| goals/services.py | Function shape to mirror | `resources_for_user(user)`, `list_resources_for_user(user, goal_id=None)` (raising `InvalidGoalIdError` on non-numeric `goal_id`, same as `list_sessions_for_user`), `create_resource(*, user, goal, title, url, type)`, `get_resource_for_user(user, pk)`, `update_resource(resource, **fields)`, `delete_resource(resource)` — no `request` anywhere. |
| goals/services.py (`create_resource`) | Ownership check, built in from the start | `if goal.user_id != user.id: raise GoalNotOwnedError(...)`, paired with the serializer-level scoping — both layers this time, per the explicit lesson from ticket 3's review. |
| goals/services.py / goals/serializers.py | Grouping implementation | Plain dict-building over an ordered `Resource` queryset (e.g. `Resource.objects.filter(goal=goal).order_by("type")` → `dict[str, list[Resource]]`), not ORM aggregation — keeps the service layer returning model instances, consistent with every existing function. |

## Data layer review

| File Path | Issue Type | Brief Description |
|---|---|---|
| goals/models.py (`LearningSession.goal`) | FK/isolation convention | `Resource.goal = ForeignKey(Goal, on_delete=CASCADE, related_name="resources")`, no direct `user` FK, isolation via `goal__user`. |
| goals/models.py (`Goal.status`) | Field-type precedent for `type` | `CharField` + `TextChoices`, same as `Goal.status`. Value set unconfirmed — same open decision ticket 3 had for `status`, needs confirming with you at `/plan`. |
| n/a | `url` field | `models.URLField()` is the right type; default `max_length=200` may be too short for real-world URLs (tracking params) — consider raising to e.g. 500. |
| goals/models.py (`Goal.Meta.indexes`) | Indexing | Composite index on `(goal, type)` mirrors `Goal`'s `(user, status)` index, matching this ticket's recurring "resources for one goal, grouped by type" query. |
| n/a | Ordering / `created_at` | Blueprint doesn't list timestamps for `Resource`, but grouping/display likely wants a stable order. If grouping is a plain dict-build (not `itertools.groupby`), strict `Meta.ordering` isn't required for correctness — but a `created_at` for stable display order within each type group is still worth adding, consistent with `Goal`'s timestamp convention. |
| goals/migrations/ | Migration placement | New migration in `goals/migrations/` (e.g. `0003_resource...`) depending on `0002_...`, co-located with `Goal`/`LearningSession` — no new app, no dependency conflicts expected. |

## Scope decisions for `/plan`

1. **App/model placement**: `Resource` added to the existing `goals` app (new migration), not a new app — confirmed by all four reviewers independently.
2. **Routes**: flat `/api/resources/`, `/api/resources/<pk>/`, filterable via `?goal=<id>` — no nesting, matching ticket 3's precedent.
3. **AC2 mechanism**: `GoalSerializer` gets a new `resources_by_type` `SerializerMethodField`, backed by a plain service function — this deliberately touches already-shipped ticket-3 code (`goals/serializers.py`), which is necessary and expected, not scope creep.
4. **Isolation**: no direct `user` FK on `Resource`; `.filter(goal__user=user)` everywhere, exactly like `LearningSession`.
5. **Defense-in-depth ownership check**: both the serializer-level scoped `PrimaryKeyRelatedField` AND a service-layer `GoalNotOwnedError` check in `create_resource`, built in from the start (not retrofitted, per the explicit lesson from ticket 3's review).
6. **Open decisions requiring your input at `/plan`**: the actual `Resource.type` choices value set (blueprint only says "type"), and whether `URLField`'s `max_length` should be raised from the Django default of 200.
