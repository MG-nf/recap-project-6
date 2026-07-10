# Feature Plan: Ticket 3 — Goals & Sessions (CRUD)

Based on `plan/ticket-3.md` and `plan/refinement-3.md`. One step per acceptance criterion.

## Decisions (confirmed with user)

- **Goal.status choices:** `planned` / `in-progress` / `done` (`TextChoices`, default `planned`).
- **LearningSession.tags:** `JSONField(default=list, blank=True)` — free-form list of strings, no fixed lookup table.
- **LearningSession isolation:** no denormalized `user` FK — isolation enforced transitively via `goal__user=request.user`, since the blueprint only gives `LearningSession` an FK to `Goal`.
- **Routes:** flat, not nested — `/api/sessions/?goal=<id>`, matching `accounts/urls.py`'s router-free style.
- **duration:** `PositiveIntegerField` (minutes), per refinement — simpler for aggregation/serialization than `DurationField`, no user-facing ambiguity to confirm.
- **Pagination / new throttling:** out of scope — no AC requires it, and CRUD endpoints aren't the abuse-sensitive class `AuthRateThrottle` targets.

New app: `goals` (via `python manage.py startapp goals`), registered in `INSTALLED_APPS`. Route/Service/Data layers kept separate per `.claude/rules.md` rule 3, mirroring `accounts`:
- **Route layer:** `goals/views.py` (DRF generics) + `goals/urls.py` — thin, parse Request → call service → Response.
- **Service layer:** `goals/services.py` — `create_goal`, `list_goals_for_user(user, status=None)`, `get_goal_for_user(user, pk)`, `update_goal`, `delete_goal`; `create_session` (validates the referenced `goal` belongs to `user`), `list_sessions_for_user(user, goal_id=None)`, `get_session_for_user(user, pk)`, `update_session`, `delete_session`. All take primitives/model instances, never `request`.
- **Data layer:** `goals/models.py` (`Goal`, `LearningSession`) + `goals/serializers.py`.

`config/settings.py`: `goals` added to `INSTALLED_APPS`. `config/urls.py` gets `path('api/goals/', include('goals.urls'))`.

## Step 1 — AC1: "Django Migrations created and applied"

- **Test:** `goals/tests.py::GoalModelTest` / `LearningSessionModelTest` — creating a `Goal` (linked to a `User`, with `title`/`desc`/`status`/timestamps) and a `LearningSession` (linked to that `Goal`, with `date`/`duration`/`notes`/`tags`) persists and reloads correctly via the ORM; `created_at`/`updated_at` are set automatically; default `status` is `planned`.
- **Implementation:** `python manage.py startapp goals`; add `goals` to `INSTALLED_APPS`; define in `goals/models.py`:
  - `Goal(user=ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="goals"), title=CharField, desc=TextField, status=CharField(choices=Status, default=Status.PLANNED), created_at=DateTimeField(auto_now_add=True), updated_at=DateTimeField(auto_now=True))` with `Meta.indexes = [models.Index(fields=["user", "status"])]`.
  - `LearningSession(goal=ForeignKey(Goal, on_delete=CASCADE, related_name="sessions"), date=DateField, duration=PositiveIntegerField, notes=TextField, tags=JSONField(default=list, blank=True))`.
  - `python manage.py makemigrations goals && python manage.py migrate`.

## Step 2 — AC2: "CRUD implemented for Goal and LearningSession"

- **Test:** `goals/tests.py::GoalCRUDTest` / `LearningSessionCRUDTest` — authenticated `POST /api/goals/` creates a Goal and returns 201; `GET /api/goals/` lists the caller's goals; `GET /api/goals/<pk>/` retrieves one; `PATCH`/`PUT /api/goals/<pk>/` updates it; `DELETE /api/goals/<pk>/` removes it. Same shape for `LearningSession` under `/api/sessions/`, with `create_session` rejecting (400) a `goal` id that doesn't belong to the caller. Unauthenticated requests to any endpoint return 401/403.
- **Implementation:** `goals/serializers.py` (`GoalSerializer`, `LearningSessionSerializer` — `user`/ownership never client-writable; `LearningSessionSerializer.goal` validated against the caller's own goals); `goals/services.py` (functions listed above); `goals/views.py` (`GoalListCreateView`/`GoalDetailView` as `ListCreateAPIView`/`RetrieveUpdateDestroyAPIView`, same for `LearningSession`), each with explicit `permission_classes = [IsAuthenticated]`; `goals/urls.py` wiring `goals/`, `goals/<int:pk>/`, `sessions/`, `sessions/<int:pk>/`; `include()` added to `config/urls.py`.

## Step 3 — AC3: "Filtering: Goals list view supports status filter (GET parameter)"

- **Test:** `goals/tests.py::GoalFilterTest` — `GET /api/goals/?status=done` returns only the caller's `done` goals; an unrecognized `status` value returns 400 with a validation message (mirrors `SignUpSerializer.validate_focus_area`'s reject-unknown-values pattern); omitting `status` returns all of the caller's goals regardless of state.
- **Implementation:** `GoalListCreateView.get()` reads `request.query_params.get('status')` and passes it to `list_goals_for_user(user, status=status)`; the service validates `status` against `Goal.Status.values` (raising a `ValidationError`/custom exception on an unknown value, translated to 400 in the view) before filtering.

## Step 4 — AC4: "Security: All QuerySets must use .filter(user=request.user)"

- **Test:** `goals/tests.py::GoalIsolationTest` / `LearningSessionIsolationTest` — user A creates a Goal and a Session; user B's `GET`/`PATCH`/`DELETE` against A's `Goal`/`LearningSession` pk returns 404 (not a 500 or a data leak); user B's list endpoints never include A's rows; unauthenticated requests to any goals/sessions endpoint return 401/403.
- **Implementation:** every service lookup/list function filters by `user` (`Goal.objects.filter(user=user, ...)`) or transitively (`LearningSession.objects.filter(goal__user=user, ...)`) — never an unscoped `.objects.all()`/`.objects.get(pk=...)`. Detail views' `get_object()`/service `get_*_for_user` raise `DoesNotExist` on an out-of-scope pk, caught in the view and returned as 404, mirroring `accounts/views.py::ProfileView.get_object`.
