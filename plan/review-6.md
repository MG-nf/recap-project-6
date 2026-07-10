# Review: Ticket 6 — Dashboard, UI, & Reporting

Branch: `feat/ticket-6-dashboard-ui-reporting`

By far the largest ticket to date — the project's first server-rendered HTML, a new `dashboard` app, ~16 routes, ~15 templates, and its own auth flow.

## Acceptance criteria verification (plan/ticket-6.md)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Dashboard provides a visual overview of goal counts grouped by status | ✅ Met | `goal_counts_by_status(user)` (ORM `annotate`/`aggregate`, per the blueprint), rendered in `templates/dashboard/index.html`. `DashboardGoalStatusTest` covers correct counts, zero-count statuses, and per-user isolation. |
| 2 | Dashboard displays total duration hours per tag and per week | ✅ Met | `duration_by_tag_for_goal(goal)` (per-goal breakdown, confirmed decision, with an explicit "Untagged" bucket) and `duration_by_week_for_user(user)` (`TruncWeek`+`Sum`, dashboard-wide). `DashboardReportingTest` covers both, plus per-user isolation. |
| 3 | Full UI Coverage: Goals/Sessions/Resources each have a functional template | ✅ Met | Full CRUD templates for all three (Goals: list/detail/create/edit/delete; Sessions/Resources: list/create/edit/delete). `GoalTemplateViewsTest`/`SessionTemplateViewsTest`/`ResourceTemplateViewsTest` cover create→list→edit→delete round-trips and cross-user isolation for all three. |
| 4 | Navigation between Dashboard/Goals/Sessions/Resources | ✅ Met | `templates/base.html`'s nav bar, extended by every page, all links via `{% url 'dashboard:...' %}`. `NavigationTest` confirms links present when authenticated, login-only when not. |
| 5 | UI is functional, accessible, unified navigation | ✅ Met | Semantic HTML (labeled form fields, single `<h1>` per page, real `<a>`/`<button>` elements), plain authored CSS with visible focus states and dark-mode support, no external dependencies. `AccessibilityTest` covers label/heading structure. Manually verified end-to-end via Playwright against the running dev server (see below). |

Full suite: `python manage.py test` → 98/98 passing (through the fixes below). `python manage.py check` → 0 issues.

## Manual verification pass (Playwright, against the running dev server)

Logged in, created a Goal, logged a Learning Session against it with multiple tags, confirmed the Dashboard's three reports updated correctly in real time (status counts, week total, per-goal tag breakdown with correct per-tag totals), confirmed logout via the nav button, and confirmed unauthenticated access to a Goal detail page redirects to `/login/?next=...`. This is where the `next`-redirect bug below was actually caught — the JSON-based/template-rendering unit tests wouldn't have exercised the full browser redirect chain the same way.

## Issues found and fixed

### Found during implementation (via manual Playwright testing, before the formal review)

| File Path | Issue Type | Fix Applied |
|---|---|---|
| dashboard/views.py (`login_view`) | Broken "return to where you came from" behavior | `@login_required` appends `?next=<original_path>` when redirecting an unauthenticated visitor to login, but `login_view` ignored it entirely, always redirecting to the Dashboard post-login — losing the user's original destination and undermining "intuitive movement" (AC4/AC5). Fixed with `_safe_next_url()`, validated via `django.utils.http.url_has_allowed_host_and_scheme` (guarding against open-redirect via a malicious `?next=`), with the value threaded through the login form as a hidden field so it survives the POST. Covered by `test_login_redirects_back_to_originally_requested_page`, `test_login_ignores_unsafe_next_url`, and (added during the formal review below) `test_login_ignores_scheme_relative_next_url`. |

### Found during the formal subagent review

All four audits (security, route, service, data) converged on one real cross-cutting issue, plus two smaller ones — all fixed before finalizing:

| File Path | Issue Type | Fix Applied |
|---|---|---|
| goals/services.py (`update_session`) | IDOR defense-in-depth gap — asymmetric with `update_resource` | `update_resource` got a `user=`/`GoalNotOwnedError` ownership check in ticket 4's review after ticket 3 shipped `update_session` without one. This ticket's `session_edit` template view exposed the same gap ticket 4 already fixed for resources — currently not exploitable (both `LearningSessionForm`'s and `LearningSessionSerializer`'s `goal` field are already scoped to the caller's own goals), but a single point of failure rather than defense-in-depth, and affects the *existing* DRF `LearningSessionDetailView` too, not just the new template view. Independently flagged by both the security and service reviewers. Fixed: `update_session` now takes a required `user=` keyword and raises `GoalNotOwnedError` on mismatch, mirroring `update_resource` exactly; both call sites (`goals/views.py::LearningSessionDetailView.perform_update` and `dashboard/views.py::session_edit`) updated to pass `user=` and catch the exception. Covered by new `test_update_rejects_reassigning_goal_to_another_users_goal` (DRF, `goals/tests.py`) and `test_update_rejects_reassigning_session_to_another_users_goal` (template, `dashboard/tests.py`). |
| dashboard/views.py (`goal_detail`) | Route/Service separation violation | Passed `goal.sessions.all()` (a raw ORM relation-manager call) directly into the template, bypassing `goals/services.py` — the only view in the file to do so; every other listing goes through a service function. Fixed to call `list_sessions_for_user(request.user, goal_id=goal.pk)` instead, consistent with the rest of the file. |
| config/urls.py | Plan-text deviation (non-functional) | `plan/feature-6-plan.md` specified `include('dashboard.urls', namespace='dashboard')`; the code omitted the explicit `namespace` kwarg, relying on Django's implicit default from `dashboard/urls.py`'s `app_name = "dashboard"` (which works correctly, but the route reviewer flagged the mismatch). Added the explicit `namespace='dashboard'` kwarg for clarity and plan-conformance — no behavior change. |

## Accepted, not fixed (flagged, deliberate)

| Item | Why it's accepted rather than fixed |
|---|---|
| **`accounts`/`goals` URLconfs have no `app_name`/namespace** | Their bare URL names (`login`, `goal-list`, `session-list`, etc.) collide with `dashboard`'s namespaced equivalents — a bare `{% url 'login' %}` or `reverse('goal-list')` anywhere would silently resolve to the wrong (JSON API, not template) view instead of raising `NoReverseMatch`. Currently **latent, not triggered** — every dashboard template already correctly uses the `dashboard:` prefix, and `accounts`/`goals` have zero templates of their own to trigger it. Properly closing this would mean adding namespaces to two already-shipped, already-reviewed apps and updating every `reverse()`/`reverse_lazy()` call across their existing test suites (dozens of call sites in `accounts/tests.py`/`goals/tests.py` from tickets 2-4) — a broad, mechanical change with real regression risk for a currently-inert defensive improvement. Flagging for a future ticket rather than a large, risky refactor bundled into this one. |
| **N+1 query for per-goal tag breakdowns** | `dashboard/views.py::index` calls `duration_by_tag_for_goal(goal)` once per goal in a Python loop (one query per goal, not batched). Consistent with this project's already-accepted "no `LearningSession` index yet" performance trade-off (tickets 3/4) — not a correctness issue, and premature to optimize at this project's expected per-user goal count. |

## Route / Service / Data layer summary (confirmed after fixes, no regressions)

- **Route**: all ~16 routes match the confirmed URL-name list, no collisions with `/api/*`/`/admin/`. Every data-touching view is `@login_required`; every detail/edit/delete view uses the established `get_*_for_user` + `Http404` pattern; every delete/logout view only acts on POST; list views correctly catch `InvalidStatusError`/`InvalidGoalIdError` rather than leaking a 500 — the same "unhandled exception" bug class from tickets 3/4 was checked for specifically and not found (other than the `update_session` gap, now fixed).
- **Service**: the three new reporting functions never take `request`, correctly scope through `goals_for_user`/`sessions_for_user`, and the "Untagged" bucketing/status zero-filling both behave as confirmed. `LearningSessionForm.clean_tags` correctly normalizes comma-separated input to a stripped list.
- **Data**: no new models/migrations (confirmed stateless, matching ticket 5's precedent). Form field constraints (`max_length`, `min_value`) all match their corresponding model fields. No raw SQL anywhere. `ModelChoiceField` querysets in `dashboard/forms.py` correctly scope the `goal` field to the caller's own goals, closing the same IDOR-enumeration class of bug tickets 3/4 fixed for the DRF serializers.
