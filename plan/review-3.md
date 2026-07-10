# Review: Ticket 3 — Goals & Sessions (CRUD)

Branch: `feat/ticket-3-goals-sessions-crud`

## Acceptance criteria verification (plan/ticket-3.md)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Django Migrations created and applied | ✅ Met | `goals/migrations/0001_initial.py` (Goal, LearningSession) + `0002_alter_goal_options_alter_learningsession_options_and_more.py` (ordering + duration validator, added during this review). `python manage.py migrate` applies cleanly. |
| 2 | CRUD implemented for Goal and LearningSession | ✅ Met | `GoalListCreateView`/`GoalDetailView`/`LearningSessionListCreateView`/`LearningSessionDetailView` (`goals/views.py`). `GoalCRUDTest`/`LearningSessionCRUDTest` cover create/list/retrieve/update/delete end-to-end. |
| 3 | Filtering: Goals list view supports `status` filter (GET parameter) | ✅ Met | `GoalListCreateView.list()` validates `?status=` against `Goal.Status.values`, 400 on unknown value. `GoalFilterTest` covers filtered/omitted/invalid cases. |
| 4 | Security: All QuerySets use `.filter(user=request.user)` | ✅ Met | Every `Goal` lookup filters by `user`; every `LearningSession` lookup filters transitively via `goal__user` (no direct `user` FK on `LearningSession`, per the confirmed plan). `GoalIsolationTest`/`LearningSessionIsolationTest` confirm cross-user access 404s, unauthenticated access 403s. |

Full suite: `python manage.py test` → 34/34 passing (through the manual browser pass below). `python manage.py check` → 0 issues.

## Manual verification pass (Playwright, against the running dev server)

After the subagent audits, the four endpoints were driven live through Django REST Framework's browsable-API HTML interface (not just the JSON test client) to confirm real request/response behavior end-to-end: signup, login, logout, Goal create/list/filter, Session create/list/filter, and cross-user isolation with a second real account. This surfaced one additional real bug the subagent audits and the `APITestCase` JSON-client tests both missed:

| File Path | Issue Type | Fix Applied |
|---|---|---|
| goals/views.py (`GoalListCreateView`, `LearningSessionListCreateView`) | Unhandled exception (500) on the browsable-API HTML path only | Both views override `list()` for their JSON responses but never defined `get_queryset()`. DRF's `BrowsableAPIRenderer` calls `view.get_queryset()` directly (for its filter-form/OPTIONS metadata) independently of `list()` — hitting the generic base class's assertion that `queryset` must be set, producing a 500 with a full debug traceback the moment `/api/goals/` or `/api/sessions/` was opened in a browser. Every `APITestCase` test used the JSON renderer (`format="json"`), which never exercises this code path, so 32/32 passing tests gave no signal. Added a `get_queryset()` to each view returning the base user-scoped queryset (`goals_for_user`/`sessions_for_user`), used only by the browsable renderer; the custom `list()` methods still serve actual GET responses. Added `test_browsable_api_renders_list_page` to both `GoalCRUDTest` and `LearningSessionCRUDTest` (requests with `HTTP_ACCEPT="text/html"`) so this class of bug is now caught by the automated suite too, not just manual browsing. |

Also re-confirmed live, matching the subagent findings: the `goal` field's browsable HTML dropdown only ever lists the current user's own goals (confirms the IDOR-enumeration fix applies to the HTML form path, not just raw JSON); a raw POST with another user's goal id returns the same generic `"Invalid pk \"1\" - object does not exist."` 400 regardless of whether that id exists at all; `?status=`/`?goal=` invalid values both return 400, not 500; cross-user `GET`/detail access returns 404; unauthenticated access returns 403.

## Issues found and fixed during the subagent-audit review

The four audit subagents (security, route, service, data) surfaced two real, unambiguous bugs — both fixed before finalizing:

| File Path | Issue Type | Fix Applied |
|---|---|---|
| goals/views.py (`LearningSessionListCreateView.list`), goals/services.py (`list_sessions_for_user`) | Unhandled exception (500) on invalid input | `?goal=<value>` was passed straight into `.filter(goal_id=goal_id)` with no validation — a non-numeric value raised an uncaught `ValueError` (500, with a debug traceback since `DEBUG` defaults to `True`), the same class of bug the `status` filter was correctly guarded against. Independently flagged by the security, route, and service reviewers. Added `InvalidGoalIdError`, raised from `list_sessions_for_user` when `goal_id` isn't parseable as an int, caught in the view and returned as 400. Covered by new `test_invalid_goal_query_param_returns_400`. |
| goals/serializers.py (`LearningSessionSerializer.goal`) | IDOR enumeration via distinguishable error messages | The `goal` field used DRF's default unscoped `PrimaryKeyRelatedField(queryset=Goal.objects.all())`, with ownership checked afterward in `validate_goal`. This let a caller distinguish "exists but isn't yours" from "doesn't exist," enumerating valid `Goal` ids belonging to other users even though attaching to them was already blocked. Scoped the field's `queryset` to `Goal.objects.filter(user=request.user)` in `__init__` (via serializer `context`), so a foreign-but-existing id and a nonexistent id now return the identical generic `does_not_exist` error. Covered by new `test_foreign_and_nonexistent_goal_ids_give_the_same_error` (asserts identical error `.code`, not just status). |

Two related findings were fixed alongside the above rather than accepted, since they were cheap and directly strengthened the same area:

| File Path | Issue Type | Fix Applied |
|---|---|---|
| goals/services.py (`create_session`), goals/views.py | Route/Service layering deviation | `plan/feature-3-plan.md` documents goal-ownership validation as living in `create_session` (service layer); the initial implementation only checked it in the serializer, so a future direct caller of `create_session` (management command, admin action, etc.) would have had no guard. Added a `GoalNotOwnedError` check inside `create_session` itself (in addition to the serializer-level queryset scoping above, which is defense-in-depth against the same class of bug at a different layer). View catches `GoalNotOwnedError` and returns 400. |
| goals/models.py (`LearningSession.duration`) | Loose model constraint | `PositiveIntegerField` permitted `0`, not a meaningful session duration. Added `validators=[MinValueValidator(1)]`; DRF's `ModelSerializer` picks this up automatically, enforcing it at the API layer. Covered by new `test_rejects_zero_duration`. |
| goals/serializers.py (`LearningSessionSerializer.tags`) | Missing input validation | `tags` accepted any JSON value (dicts, numbers, nested structures), not the "free-form list of strings" decided in `plan/feature-3-plan.md`. Added `validate_tags` rejecting anything that isn't a list of strings. Covered by new `test_rejects_non_list_tags`. |
| goals/models.py (`Goal`, `LearningSession`) | Undefined list ordering | Neither model declared `Meta.ordering`, so list-endpoint row order was undefined at the DB level. Added `ordering = ["-created_at"]` on `Goal` and `["-date"]` on `LearningSession` (new migration `0002_...`). |

## Remaining items — flagged, accepted as-is (not fixed, and not expected to be)

| Item | Why it's accepted rather than fixed |
|---|---|
| **No pagination on list endpoints** | Explicitly decided out of scope in `plan/feature-3-plan.md` ("no AC requires it") when the plan was confirmed with you. The security reviewer re-flagged the unbounded-response-size angle as a availability concern for accounts with very large goal/session counts — worth a follow-up ticket if this project's usage pattern changes, but not a regression introduced by this ticket, and not something to silently add scope for now. |
| **No new throttling on Goal/Session CRUD endpoints** | Same call as `plan/refinement-3.md`'s security review: `AuthRateThrottle` is IP-keyed and scoped to pre-auth abuse (signup/login); these are post-auth CRUD endpoints, a different abuse class with no throttle requirement in the ticket's ACs. |

## Route / Service / Data layer summary (confirmed after fixes, no regressions)

- **Route:** `goals/urls.py`/`views.py` remain thin and delegate to the service layer; every view has explicit `permission_classes`; final routes (`/api/goals/`, `/api/goals/<pk>/`, `/api/sessions/`, `/api/sessions/<pk>/`) are flat, as decided, and don't collide with `/api/auth/*` or each other. One route-layer wiring inconsistency in the original plan text itself (config/urls.py's `include()` prefix) was caught and corrected during implementation, before this review — noted here since the route reviewer independently confirmed the final routes are correct despite that plan-text slip.
- **Service:** `goals/services.py` functions (`create_goal`, `list_goals_for_user`, `get_goal_for_user`, `update_goal`, `delete_goal`, `create_session`, `list_sessions_for_user`, `get_session_for_user`, `update_session`, `delete_session`) never take `request` — confirmed by both the service and route reviewers. Single-statement writes correctly don't use `transaction.atomic()` (no multi-step writes exist in this app, unlike `accounts::register_user`).
- **Data:** No insecure SQL (pure ORM). `Goal`/`LearningSession` models and `0001_initial.py`/`0002_...` migrations match the confirmed plan exactly (field types, `on_delete=CASCADE`, composite `(user, status)` index, `related_name` conventions consistent with `accounts`). The deliberate omission of a direct `user` FK on `LearningSession` (isolation via `goal__user`) doesn't cost any required query an index — both `goal_id` and `Goal.user_id` are auto-indexed FKs.
