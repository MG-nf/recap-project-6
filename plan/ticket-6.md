# Ticket 6: Dashboard, UI, & Reporting

**GitHub Issue:** [#6](https://github.com/MG-nf/recap-project-6/issues/6)
**Project Board Status (at intake):** Ready
**Note:** this ticket's scope changed materially after tickets 2-5 were already built as a pure DRF API — re-read from GitHub fresh at intake per explicit instruction, not reused from an earlier (smaller, annotate/aggregate-only) version seen in an earlier board listing.

## Blueprint

- Dashboard Logic: Use `QuerySet.annotate()` and `aggregate()` for all reporting calculations.
- **Frontend Exception:** This ticket is explicitly authorized to generate Django templates (`.html`) and associated static assets for the Dashboard UI and to complete the UI for all previously implemented features where a user interface is appropriate.
- UI Structure: The dashboard must be visually integrated into the navigation system, serving as a primary view for users. All other implemented features (Goals, Sessions, Resources) must be fully wrapped in a consistent, user-facing template structure.
- Reporting: Render session hours and goal counts as simple tables or bars within the dashboard template.

## Acceptance Criteria

- [ ] Dashboard provides a visual overview of goal counts grouped by status.
- [ ] Dashboard displays calculated reporting, including total duration hours per tag and per week.
- [ ] Full UI Coverage: Every feature implemented in the project (Goals, Sessions, Resources) has a functional, intuitive template associated with it.
- [ ] Navigation is maintained, allowing intuitive movement between the Dashboard, Goals, Sessions, and Resources.
- [ ] The overall UI is functional, accessible, and follows the unified navigation structure.

## Rule override notice (explicit, not a reinterpretation this time)

Every prior ticket (2, 4, 5) hit template-flavored blueprint language and reinterpreted it as DRF/JSON per `.claude/rules.md` rule 3 ("Use Django REST Framework for all API development. Do not use Django Templates"). **This ticket is different: it explicitly authorizes Django Templates**, by name, as a stated exception to that rule. This is the correct reading, not a reinterpretation to resist — the "Frontend Exception" blueprint line exists specifically to unblock this ticket. `TEMPLATES`/`APP_DIRS=True` have been present in `config/settings.py` since `startproject` (ticket 1) and were simply unused until now.

## Current-state notes (from repo inspection)

- **Zero templates or static assets exist anywhere in the repo** (`**/templates/**` and `**/static/**` both return nothing) — this is a from-scratch frontend build, not an extension of existing template work.
- Every existing view (`accounts/views.py`, `goals/views.py`) is DRF-only (`APIView`/generics returning JSON). This ticket needs new template-rendering views; the existing JSON API views/tests (tickets 2-5) should stay untouched and continue working, since nothing in this ticket's ACs asks to remove or replace the API.
- **Scale**: this is the largest ticket so far by a wide margin — a full CRUD UI for Goals, Sessions, and Resources, plus a Dashboard with two distinct aggregation reports, plus site-wide navigation, plus accessibility. Tickets 2-5 each shipped one model/feature; this ticket UI-wraps four.
- **Auth gap (not listed in the ACs, but a practical blocker)**: `accounts` only has JSON endpoints (`POST /api/auth/signup/`, `/login/`, `/logout/`) — there is no HTML login form anywhere. Since every Goal/Session/Resource/Dashboard view requires `IsAuthenticated`/a logged-in session, a browser user has no way to reach the new template UI without first authenticating via a raw JSON POST (e.g. curl, or the DRF browsable API's raw-data form) — not "intuitive movement," per AC5. This needs an explicit decision at `/refine`/`/plan`: add template-based login/logout (and maybe signup) views, or treat browser-based auth as out of scope for this ticket.
- **Tag-based aggregation constraint**: `LearningSession.tags` is a `JSONField` (list of free-form strings, per ticket 3's decision) — SQLite has no native JSON-array-unnesting aggregation, so "total duration hours per tag" cannot be a single `annotate()`/`aggregate()` call across the tags array the way "goal counts by status" can (`Goal.objects.values('status').annotate(count=Count('id'))` works cleanly). This needs a concrete implementation approach decided at `/plan` (e.g., Python-side aggregation after fetching sessions, since the blueprint's "use annotate/aggregate" instruction fits the status-count report cleanly but not the free-form-tag report as directly).
- Existing service-layer conventions (`goals/services.py`: plain functions, no `request` coupling) and Route/Service/Data separation still apply — template *views* are a new kind of route layer, but reporting/aggregation logic belongs in the service layer, same as every prior ticket.
- No CSS framework/static-asset tooling exists yet (no Bootstrap, Tailwind, webpack, etc.) — `/plan` needs to decide styling approach (plain CSS is the lowest-dependency option, consistent with this project's minimal-dependency history to date).
