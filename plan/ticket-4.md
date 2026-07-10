# Ticket 4: Resource Library

**GitHub Issue:** [#4](https://github.com/MG-nf/recap-project-6/issues/4)
**Project Board Status (at intake):** Ready

## Blueprint

Model `Resource` (ForeignKey to `Goal`, title, url, type). Use Django ModelForms for input.

## Acceptance Criteria

- [ ] Goal detail page includes a form to attach `Resource`.
- [ ] Goal detail view displays `Resources` grouped by `type`.

## Reinterpretation notice (rule conflict)

The blueprint's language ("Goal detail **page**," "form to attach," "Django **ModelForms**") is template-flavored, but `.claude/rules.md` rule 3 mandates DRF (not Django Templates) for all API work once it has started — which tickets 2 and 3 already did, establishing this project as a pure DRF API with no template rendering anywhere. Per that rule and this project's established precedent (ticket 2 similarly reinterpreted the blueprint's "Extend `AbstractUser`" suggestion as `OneToOneField(User)` to fit the actual current-state constraints), this ticket's ACs are reinterpreted as:

- **AC1** ("Goal detail page includes a form to attach Resource") → the existing `GoalDetailView` (`/api/goals/<pk>/`, from ticket 3) response includes attachable `Resource`s, and a DRF endpoint accepts `POST` to create a `Resource` FK'd to that `Goal` — i.e. an API affordance to attach a resource, not an HTML form.
- **AC2** ("Goal detail view displays Resources grouped by type") → the `Goal` detail response includes its resources grouped by `type` (e.g. a `resources_by_type` field, or a dedicated nested structure), not a template-rendered page.
- **ModelForms** → replaced with a DRF `ModelSerializer`, consistent with `accounts`/`goals`.

## Current-state notes (from repo inspection)

- `goals` app (ticket 3) already provides `Goal` (with `user` FK, `title`, `desc`, `status`, timestamps) and `LearningSession` (FK to `Goal`), full CRUD under `/api/goals/`/`/api/sessions/`, DRF generics, Route/Service/Data layers separated, session auth + `IsAuthenticated` project-wide defaults (`config/settings.py`).
- No `Resource` model exists yet. This ticket needs either a new Django app (e.g. `resources`) or an addition to the existing `goals` app, since `Resource` FKs directly to `Goal` — `/refine` should weigh both (new app keeps `goals` from growing unbounded vs. same app avoids a cross-app FK/import for a tightly-coupled child model, mirroring how `LearningSession` lives alongside `Goal` in the same app rather than a separate one).
- Data isolation precedent (`.filter(user=request.user)` for `Goal`, `.filter(goal__user=request.user)` for `LearningSession`) extends naturally to `Resource`: `.filter(goal__user=request.user)`, mirroring `LearningSession`'s transitive-isolation pattern from ticket 3 — no direct `user` FK on `Resource` expected, for the same reasons ticket 3 decided against one on `LearningSession`.
- `type` on `Resource` is unspecified beyond "type" in the blueprint — likely a `CharField` with `choices` (e.g. `article`/`video`/`book`/`course`/`other`), same category of decision ticket 3 made for `Goal.status`; `/refine`/`/plan` should confirm the actual value set with you.
- `url` field: Django's `URLField` is the obvious fit (matches Django's own built-in field for this exact purpose); no ambiguity expected here unlike `status`/`type`/tags-style fields in prior tickets.
- "Grouped by type" (AC2) is a response-shaping concern, not a new isolation/security concern — likely implemented either as a query-time `values`/`annotate` grouping in the service layer, or as a plain Python `itertools.groupby`/dict-building step over an ordered queryset; `/plan` should pick one, consistent with `goals/services.py`'s existing patterns (plain functions, no `request` coupling).
