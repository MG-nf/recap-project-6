# Feature Plan: Ticket 2 — Authentication & Profile

Based on `plan/ticket-2.md` and `plan/refinement-2.md`. One step per acceptance criterion.

## Decisions (confirmed with user)

- **User relation:** `Profile` uses `OneToOneField(User)` — no `AUTH_USER_MODEL` change.
- **Auth mechanism:** DRF `SessionAuthentication` + Django's built-in `login()`/`logout()`, CSRF-protected.
- **focus_area:** Fixed/seeded `FocusArea(name)` lookup model, seeded via data migration (e.g. Frontend, Backend, Data, DevOps, Mobile), `Profile.focus_area` is `ManyToManyField(FocusArea)`.
- **Sign-up flow:** Combined — one endpoint creates `User` + `Profile` (with `focus_area`) in a single request.

New app: `accounts` (via `python manage.py startapp accounts`), registered in `INSTALLED_APPS` alongside `rest_framework`. Route/Service/Data layers kept separate per `.claude/rules.md` rule 3:
- **Route layer:** `accounts/views.py` (DRF views) + `accounts/urls.py` — thin, parse Request → call service → return Response.
- **Service layer:** `accounts/services.py` — pure business logic (create user+profile, no direct request/DB coupling beyond calling the data layer).
- **Data layer:** `accounts/models.py` (`Profile`, `FocusArea`) + `accounts/serializers.py`.

`config/settings.py` additions: `rest_framework` and `accounts` in `INSTALLED_APPS`; `REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES': [...SessionAuthentication...], 'DEFAULT_PERMISSION_CLASSES': [...IsAuthenticated...]}`. `requirements.txt` gets `djangorestframework` pinned.

`config/urls.py` gets `path('api/auth/', include('accounts.urls'))`.

## Step 1 — AC1: "Profile model with fields: name, cohort, focus_area"

- **Test:** `accounts/tests.py::ProfileModelTest` — creating a `Profile` linked to a `User` with `name`, `cohort`, and one or more `FocusArea` entries persists and reloads correctly; `Profile.objects.get(user=some_user)` returns the right instance.
- **Implementation:** `python manage.py startapp accounts`; add `rest_framework`/`accounts` to `INSTALLED_APPS`; define `FocusArea(name)` and `Profile(user=OneToOneField(User), name=CharField, cohort=CharField, focus_area=ManyToManyField(FocusArea))` in `accounts/models.py`; migration for both models plus a data migration seeding the fixed `FocusArea` list.

## Step 2 — AC2: "Auth flow: Sign-up, Login, Logout functional"

- **Test:** `accounts/tests.py::AuthFlowTest` — `POST /api/auth/signup/` with username/password/name/cohort/focus_area creates a `User`+`Profile` and returns 201; `POST /api/auth/login/` with valid credentials returns 200 and establishes a session (subsequent authenticated request succeeds); invalid credentials return 400/401; `POST /api/auth/logout/` while authenticated ends the session (subsequent request is unauthenticated).
- **Implementation:** `accounts/services.py` (`register_user`, calling Django's `create_user` + `Profile.objects.create` in one transaction); `accounts/serializers.py` (`SignUpSerializer`, `LoginSerializer`); `accounts/views.py` (`SignUpView`, `LoginView` using `django.contrib.auth.login()`, `LogoutView` using `django.contrib.auth.logout()`); `accounts/urls.py` wiring `signup/`, `login/`, `logout/`; `REST_FRAMEWORK` settings block in `config/settings.py`; `djangorestframework` added to `requirements.txt` and `INSTALLED_APPS`; `include()` added to `config/urls.py`.

## Step 3 — AC3: "Data Isolation: User Profile views must restrict access to request.user data only"

- **Test:** `accounts/tests.py::ProfileIsolationTest` — authenticated user A requesting their own profile (`GET /api/auth/profile/`) gets their data; there is no endpoint/parameter that lets user A fetch user B's profile; unauthenticated request to the profile endpoint returns 401/403.
- **Implementation:** `accounts/views.py::ProfileView` (DRF `RetrieveUpdateAPIView` or similar) with `permission_classes = [IsAuthenticated]` and `get_object`/`get_queryset` returning only `Profile.objects.get(user=self.request.user)` — never accepting a profile ID from the client.
