# Review: Ticket 4 — Resource Library

Branch: `feat/ticket-4-resource-library`

## Acceptance criteria verification (plan/ticket-4.md, as reinterpreted per its "Reinterpretation notice")

| # | Criterion (reinterpreted) | Status | Evidence |
|---|---|---|---|
| 1 | API endpoint to attach a `Resource` to a `Goal` | ✅ Met | `ResourceListCreateView`/`ResourceDetailView` (`/api/resources/`), full CRUD, FK-ownership enforced in both the serializer (scoped `PrimaryKeyRelatedField`) and service layer (`GoalNotOwnedError` in `create_resource` **and** `update_resource`). `ResourceCRUDTest`/`ResourceIsolationTest` cover create/list/retrieve/update/delete, cross-user rejection, and the foreign-vs-nonexistent-goal-id enumeration check. |
| 2 | Goal detail view displays Resources grouped by type | ✅ Met | `GoalDetailSerializer.resources_by_type` (new, detail-view-only), backed by `resources_by_type_for_goal(goal)` in the service layer. `GoalResourcesByTypeTest` covers correct grouping, empty-grouping for a resource-less goal, and that another user's resources never leak in. |

Full suite: `python manage.py test` → 52/52 passing. `python manage.py check` → 0 issues. Live-verified via Playwright against the running dev server (see below) — the browsable API renders correctly for `/api/resources/` and `/api/goals/<pk>/`, and the N+1 fix was independently confirmed by inspecting the actual list vs. detail response bodies.

## Manual verification pass (Playwright, against the running dev server)

Following the same practice that caught a real bug during ticket 3's review, the actual endpoints were driven live: created a Goal, attached a Resource to it via the browsable HTML form (Goal dropdown correctly scoped to the caller's own goals), confirmed `GET /api/goals/<pk>/` includes `resources_by_type` with the resource correctly grouped under `"article"`, and confirmed `GET /api/goals/` (list) and the `POST /api/goals/` create response both correctly *exclude* `resources_by_type` — matching the fix described below.

## Issues found and fixed during this review

The four audit subagents (security, route, service, data) converged strongly on one real, cross-cutting issue, plus two smaller gaps — all fixed before finalizing:

| File Path | Issue Type | Fix Applied |
|---|---|---|
| goals/serializers.py (`GoalSerializer`) | N+1 query / performance regression on an already-shipped endpoint | `resources_by_type` was added directly to the single, shared `GoalSerializer`, used by both `GoalDetailView` (one instance — fine) and `GoalListCreateView.list()` (`many=True`, unpaginated). This meant every goal returned by `GET /api/goals/` triggered its own extra `Resource` query — a real N+1 regression on a previously fine, already-reviewed ticket-3 endpoint, and not something `plan/feature-4-plan.md` called for (the plan only ever mentions the *detail* view). Flagged independently by all three of the security, route, and service reviewers. Fixed by splitting into `GoalSerializer` (base, ticket-3 fields only, used by `GoalListCreateView`) and a new `GoalDetailSerializer(GoalSerializer)` (adds `resources_by_type`, used only by `GoalDetailView`). Covered by two new tests: `test_list_response_excludes_resources_by_type_but_detail_includes_it` and `test_listing_many_goals_with_resources_does_not_scale_query_count` (compares captured query counts for 1 vs. 5 goals-with-resources, asserting no growth). |
| goals/models.py (`Resource`) | Missing ordering — a regression of a bug already fixed once, in ticket 3 | Unlike `Goal`/`LearningSession` (both given `Meta.ordering` after ticket 3's review flagged undefined list ordering as a real bug), `Resource` had no `Meta.ordering` — `GET /api/resources/` returned rows in DB-undefined order. Flagged independently by the security and data reviewers. Added `ordering = ["-created_at"]` (migration `0004_alter_resource_options`). Covered by new `test_list_returns_newest_resource_first`. |
| goals/services.py (`update_resource`) | Defense-in-depth gap — asymmetric with `create_resource` | `create_resource` had the required `GoalNotOwnedError` check from the start (per the confirmed plan), but `update_resource` had no equivalent guard against a `PATCH` reassigning `goal` to another user's goal — currently unreachable via the API (the serializer's scoped `PrimaryKeyRelatedField` already blocks it), but the same defense-in-depth gap ticket 3 had to retrofit for `create_session`, this time on the update path instead of create. Flagged by the security reviewer. Added the same ownership check to `update_resource` (now takes a required `user` keyword arg), wired through `ResourceDetailView.perform_update`, which now also catches `GoalNotOwnedError` → 400. Covered by new `test_update_rejects_reassigning_goal_to_another_users_goal`. |

## Confirmed clean (verified, not repeats of ticket-3 bugs)

- **IDOR/enumeration**: `ResourceSerializer.goal`'s `PrimaryKeyRelatedField` queryset is scoped to the caller's own goals (mirrors `LearningSessionSerializer`), and `create_resource` has the redundant service-layer check *from the start* this time — ticket 3 had to retrofit this after its own review; ticket 4 built it in per the confirmed plan.
- **Browsable-API 500**: `ResourceListCreateView` defines `get_queryset()` separately from its custom `list()` — the exact bug ticket 3's Playwright-driven review pass found and fixed was correctly avoided here from the start. Confirmed both by `test_browsable_api_renders_list_page` and live in the browser.
- **Mass assignment**: `id`/`created_at` are `read_only_fields`; no unintended writable fields.
- **SSRF**: `url` is only stored/serialized, never fetched server-side anywhere in this codebase.
- **`resources_by_type_for_goal`**: takes an already-ownership-checked `Goal` instance, filters strictly by `goal=goal`, returns model instances (not raw dicts from `.values()/.annotate()`) — consistent with this app's return-type convention.

## Route / Service / Data layer summary (confirmed after fixes, no regressions)

- **Route**: final routes (`/api/resources/`, `/api/resources/<pk>/`, flat, `?goal=<id>` filterable) match the confirmed plan exactly, no collisions with `/api/auth/`, `/api/goals/`, `/api/sessions/`. `ResourceListCreateView`/`ResourceDetailView` remain thin, explicit `permission_classes` on both.
- **Service**: all new `Resource` functions (`resources_for_user`, `list_resources_for_user`, `create_resource`, `get_resource_for_user`, `update_resource`, `delete_resource`, `resources_by_type_for_goal`) never take `request`; single-statement writes correctly don't use `transaction.atomic()`.
- **Data**: `Resource` model/migrations match the confirmed plan (FK `CASCADE`, `related_name="resources"`, `URLField(max_length=500)`, `TextChoices` for `type`, composite `(goal, type)` index, now also `ordering`). No raw SQL anywhere.
