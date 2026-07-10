# Feature Plan: Ticket 4 — Resource Library

Based on `plan/ticket-4.md` and `plan/refinement-4.md`. One step per acceptance criterion (as reinterpreted for this DRF-only project — see `plan/ticket-4.md`'s "Reinterpretation notice").

## Decisions (confirmed with user)

- **Resource.type choices:** `article` / `video` / `repo` / `doc` (`TextChoices`, no default — required on create).
- **AC2 mechanism:** `GoalSerializer` (from ticket 3) gets a new `resources_by_type` `SerializerMethodField`. This is a deliberate, necessary modification of already-shipped ticket-3 code, not scope creep.
- **Resource.url:** `URLField(max_length=500)` — raised from Django's default of 200 to fit longer real-world URLs.
- **App/model placement:** `Resource` added to the existing `goals` app (new migration), not a new app — `Resource` FKs tightly to `Goal`, same reasoning as `LearningSession` in ticket 3.
- **Routes:** flat `/api/resources/`, `/api/resources/<pk>/`, filterable via `?goal=<id>` — no nesting, matching ticket 3's precedent.
- **Isolation:** no direct `user` FK on `Resource` — `.filter(goal__user=user)` everywhere, exactly like `LearningSession`.
- **Ownership check:** both the serializer-level scoped `PrimaryKeyRelatedField` (on `ResourceSerializer.goal`) AND a service-layer `GoalNotOwnedError` check in `create_resource`, built in from the start this time (ticket 3 had to retrofit this after its review).
- **Grouping implementation:** plain dict-building over an ordered `Resource` queryset in the service layer (not ORM `.values()/.annotate()`, which would return dicts instead of model instances and break this app's return-type convention).
- **Timestamps:** `created_at = DateTimeField(auto_now_add=True)` added to `Resource` for stable ordering within each type group (blueprint doesn't list it, but ticket 3 already established the timestamp convention and grouped display wants a stable order).

Extends the existing `goals` app — no new app, no `INSTALLED_APPS`/`config/urls.py` change (just a new `path("resources/", ...)` in `goals/urls.py`). Route/Service/Data layers kept separate, mirroring `LearningSession`:
- **Route layer:** `goals/views.py` gains `ResourceListCreateView`/`ResourceDetailView`; `goals/urls.py` gains the `resources/` paths.
- **Service layer:** `goals/services.py` gains `resources_for_user`, `list_resources_for_user(user, goal_id=None)`, `create_resource`, `get_resource_for_user`, `update_resource`, `delete_resource`, and `resources_by_type_for_goal(goal)`.
- **Data layer:** `goals/models.py` gains `Resource`; `goals/serializers.py` gains `ResourceSerializer` and a `resources_by_type` field on `GoalSerializer`.

## Step 1 — AC1: "Goal detail page includes a form to attach Resource" (reinterpreted: API endpoint to create a Resource attached to a Goal)

- **Test:** `goals/tests.py::ResourceCRUDTest` — authenticated `POST /api/resources/` with a `goal` id owned by the caller creates a `Resource` and returns 201; `GET /api/resources/` lists the caller's resources; `GET /api/resources/?goal=<id>` filters to one goal's resources (non-numeric `goal` → 400, mirroring `list_sessions_for_user`'s `InvalidGoalIdError`); `GET/PATCH/DELETE /api/resources/<pk>/` retrieve/update/delete a resource; attempting to attach a `Resource` to another user's `goal` returns 400 with the same generic "does not exist" error whether the goal is foreign-but-real or nonexistent (mirrors `LearningSessionCRUDTest.test_foreign_and_nonexistent_goal_ids_give_the_same_error`); unauthenticated requests return 403; cross-user retrieve/update/delete of another user's resource returns 404.
- **Implementation:** `goals/models.py::Resource(goal=ForeignKey(Goal, on_delete=CASCADE, related_name="resources"), title=CharField, url=URLField(max_length=500), type=CharField(choices=Type.choices), created_at=DateTimeField(auto_now_add=True))` with `Meta.indexes = [Index(fields=["goal", "type"])]`; migration `goals/migrations/0003_resource...`. `goals/serializers.py::ResourceSerializer` (`goal` field's queryset scoped to the caller's own goals via `context["request"]`, same `__init__` pattern as `LearningSessionSerializer`). `goals/services.py`: `resources_for_user(user)`, `list_resources_for_user(user, goal_id=None)` (raises `InvalidGoalIdError`), `create_resource(*, user, goal, title, url, type)` (raises `GoalNotOwnedError` if `goal.user_id != user.id`), `get_resource_for_user(user, pk)`, `update_resource(resource, **fields)`, `delete_resource(resource)`. `goals/views.py`: `ResourceListCreateView`/`ResourceDetailView` (DRF generics, `permission_classes = [IsAuthenticated]`, same `get_queryset()`/`list()`/`get_object()`/`perform_create()`/`perform_update()`/`perform_destroy()` split as `LearningSessionListCreateView`/`LearningSessionDetailView`). `goals/urls.py`: `resources/`, `resources/<int:pk>/`.

## Step 2 — AC2: "Goal detail view displays Resources grouped by type"

- **Test:** `goals/tests.py::GoalResourcesByTypeTest` — `GET /api/goals/<pk>/` (existing `GoalDetailView` from ticket 3) response includes a `resources_by_type` field shaped as `{"article": [...], "video": [...], ...}`, containing only that goal's resources (not another goal's, not another user's), grouped correctly across multiple types; a goal with no resources yet returns `resources_by_type: {}` rather than erroring.
- **Implementation:** `goals/services.py::resources_by_type_for_goal(goal)` — builds a `dict[str, list[Resource]]` from `Resource.objects.filter(goal=goal).order_by("type", "-created_at")`, no `user`/`request` argument needed (the `Goal` instance reaching this function is already ownership-checked by `GoalDetailView.get_object()`). `goals/serializers.py::GoalSerializer` gains `resources_by_type = SerializerMethodField()` calling `resources_by_type_for_goal(obj)` and serializing each group's resources via `ResourceSerializer(many=True)`.
