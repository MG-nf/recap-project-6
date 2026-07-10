# Review: Ticket 2 — Authentication & Profile

Branch: `feat/ticket-2-authentication-profile`

## Acceptance criteria verification (plan/ticket-2.md)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `Profile` model with fields: `name`, `cohort`, `focus_area` | ✅ Met | `accounts/models.py` — `Profile(user, name, cohort, focus_area=M2M(FocusArea))`. `ProfileModelTest` verifies creation/reload with focus areas. |
| 2 | Auth flow: Sign-up, Login, Logout functional | ✅ Met | `AuthFlowTest` (now 6 tests incl. weak-password/duplicate-username regressions) covers signup, login, invalid login, logout end-to-end. |
| 3 | Data Isolation: Profile views restricted to `request.user` | ✅ Met | `ProfileIsolationTest` confirms user A never sees user B's data; unauthenticated request gets 403. |

Full suite: `python manage.py test` → 14/14 passing (through third pass, see below). `python manage.py check` → 0 issues.

## Third review pass — both remaining open items implemented, then re-reviewed

Per your instruction, the two items deferred at the end of the second pass were implemented, and all four audit subagents ran again:

- **Env-based settings:** `config/settings.py` now reads `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS` via `django-environ` (`environ.Env()` + `read_env(BASE_DIR / '.env')`), falling back to the original `startproject` defaults when no `.env` exists so local dev is unaffected. New `.env.example` documents the three vars; `.gitignore` got a `!.env.example` negation so the example isn't swept up by the `.env*` pattern.
- **Shared throttle cache:** Added `CACHES` using `django.core.cache.backends.db.DatabaseCache` (backed by `db.sqlite3`) instead of the default per-process `LocMemCache`, chosen over Redis/Memcached since this project has no other external services and that would be real infrastructure scope creep. Ran `python manage.py createcachetable` once; documented as a required one-time setup step in `CLAUDE.md`.

The re-review caught real gaps in what was just added, fixed before finalizing:

| File Path | Issue Type | Fix Applied |
|---|---|---|
| config/settings.py | Silent insecure-production fallback | `SECRET_KEY`/`DEBUG` both fall back to insecure local-dev defaults with no enforcement if the corresponding env var is simply absent in a real deployment — nothing but a comment guarded against it. Added a fail-fast check: `if not DEBUG and SECRET_KEY.startswith('django-insecure-'): raise ImproperlyConfigured(...)`. Verified it actually fires (`DEBUG=False python manage.py check` → `ImproperlyConfigured` as expected) and that normal local dev (`DEBUG` defaulting `True`) is unaffected. |
| config/settings.py (`DATABASES`) | SQLite write-contention risk (new, caused by the cache addition) | `DatabaseCache` writes throttle counters into the same `db.sqlite3` file every business-data write also uses — under concurrent/multi-worker load this trades "counters fragment per process" for "cache writes and business writes contend for the same SQLite writer lock" (`database is locked` errors). Mitigated with `DATABASES['default']['OPTIONS'] = {'init_command': 'PRAGMA journal_mode=wal;', 'timeout': 20}` — WAL mode lets readers proceed concurrently with the one writer, and the longer busy-timeout makes transient contention retry instead of immediately erroring. Confirmed Django 6.0.7's sqlite3 backend supports both options directly. |
| CLAUDE.md | Stale documentation | Line 14 still described `SECRET_KEY` as a hardcoded insecure default with no env-var override, contradicting the new wiring. Updated to describe the actual `django-environ` behavior and the fail-fast guard. |

### Remaining items — flagged, accepted as-is (not fixed, and not expected to be)

| Item | Why it's accepted rather than fixed |
|---|---|
| **`createcachetable` has no enforcement** | The cache table is intentionally *not* a Django migration (matches Django's own documented pattern for `DatabaseCache`) — it's a one-time manual step. A fresh clone that only runs `migrate` will hit `OperationalError: no such table` on the first throttled request rather than a clear setup error. Building automated enforcement (a migration-time check, a custom system check) is more tooling than a single-developer project (per `.claude/rules.md` Workflow Constraints) currently needs; mitigated today by documenting the step in `CLAUDE.md`. |
| **`DEBUG`/`ALLOWED_HOSTS` independently toggleable** | Setting `DEBUG=False` without also setting `ALLOWED_HOSTS` makes every route 400 with `DisallowedHost` before any view runs. This is standard Django behavior (not introduced by this ticket) and is exactly what Django's own `manage.py check --deploy` flags (`security.W020`) — the standard mitigation is running that command before deploying, not custom cross-validation code. |
| **Shared-IP throttle trade-off, `LocMemCache`→`DatabaseCache` doesn't change this** | Unchanged from the second pass — keying purely by IP means one abusive client behind a NAT/shared IP can exhaust the bucket for everyone on it. Accepted trade-off for fixing the identity-bypass bug. |
| **`register_user`'s `IntegrityError` → always `UsernameTakenError`** | Unchanged from the second pass — minor, no current false-positive path since `Profile` has no unique constraints beyond the FK. |
| **`throttle_scope` / settings-key magic-string coupling** | Unchanged from the second pass — low severity, no current mismatch. |
| **`ProfileView`'s PUT/PATCH path bypasses the service layer** | Unchanged from the second pass — not currently reachable since `focus_area` is read-only and `name`/`cohort` updates have no business logic to encapsulate yet. |

## Second review pass — items 1–3 from "Open items" below were implemented, then re-reviewed

Per your instruction, session/cookie hardening, rate limiting, and username validation were added, and all four audit subagents ran again against the result:

- **Session/cookie hardening:** `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`, `CSRF_COOKIE_SAMESITE = 'Lax'`, `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE = not DEBUG` (tied to `DEBUG` so local HTTP dev keeps working; becomes `True` once `DEBUG = False`).
- **Rate limiting:** `accounts/throttles.py::AuthRateThrottle` (custom `ScopedRateThrottle` subclass), applied to `SignUpView`/`LoginView`, rates `signup: 5/hour`, `login: 10/min` in `config/settings.py`.
- **Username validation:** `SignUpSerializer.username` now uses Django's `UnicodeUsernameValidator` + `max_length=150`.

The re-review caught two more real bugs in what was just added, both fixed and covered by new tests before finalizing:

| File Path | Issue Type | Fix Applied |
|---|---|---|
| accounts/services.py, accounts/views.py | Throttle identity bug (new) | The obvious approach — stock `ScopedRateThrottle` — keys its cache by `request.user.pk` once a session is authenticated. Since `SignUpView` auto-logs the caller in on success, and a client could already be authenticated when hitting `/login/`, every subsequent request got a *fresh, unthrottled* per-user bucket instead of accumulating against the shared per-IP bucket — silently defeating the throttle for exactly the abuse (mass signups / credential stuffing) it's meant to stop. Fixed with `accounts/throttles.py::AuthRateThrottle`, which always keys on client IP via `get_ident()`, never on `request.user`. Covered by `ThrottleTest`. |
| config/settings.py | Throttle spoofing gap (new) | `get_ident()` trusts a client-supplied `X-Forwarded-For` header whenever `NUM_PROXIES` isn't set (the default), so a client could send a different `X-Forwarded-For` per request and get a fresh bucket every time — undermining the IP-keying fix above. Added `'NUM_PROXIES': 0` to `REST_FRAMEWORK` settings (correct since this project has no reverse proxy in front). Covered by new `test_spoofed_forwarded_for_header_does_not_bypass_throttle`. |
| accounts/services.py | Incomplete password validation (new) | `validate_password(password)` was called with no `user=` argument, before the `User` row existed — `UserAttributeSimilarityValidator` silently no-ops without a user to compare against, so a password like `bob12345` for username `bob` wasn't rejected despite that validator being configured. Fixed: `validate_password(password, user=User(username=username))`. Covered by new `test_signup_rejects_password_similar_to_username`. |

### Remaining items from this pass — flagged, not fixed (judgment calls, not unambiguous fixes)

| Item | Why it wasn't just fixed |
|---|---|
| **`LocMemCache` is per-process** | No `CACHES` setting is configured, so throttle counters live in Django's default per-process cache. A single dev-server process is fine, but any multi-worker deployment (gunicorn `--workers N`, multiple containers) fragments the counter per process, effectively multiplying the advertised rate limits, and counters reset on every restart. Fixing this means adding a shared cache backend (Redis/Memcached) — real infrastructure scope beyond this ticket, same category as the `db.sqlite3` history question from ticket 1. |
| **Shared-IP availability trade-off** | Keying the throttle purely by IP means one abusive client behind a NAT/corporate proxy/campus network can exhaust the bucket for every legitimate user on that IP during the throttle window. This is the correct trade-off for the identity-bypass bug it fixes, but is a real residual risk worth knowing about, not something to "fix" without changing the whole approach (e.g. per-account + per-IP dual throttling). |
| **`register_user`'s `IntegrityError` → always `UsernameTakenError`** | If a future constraint on `Profile` (not just `User.username`) ever raised `IntegrityError`, the route layer would still report a misleading "username already exists" 400. Minor, no current false-positive path since `Profile` has no unique constraints yet beyond the FK. |
| **`throttle_scope` / settings-key magic-string coupling** | `'signup'`/`'login'` appear as literals in both `accounts/views.py` and `config/settings.py` with nothing enforcing they match; a typo would silently disable throttling rather than error. Low severity, no current mismatch. |

## Issues found and fixed during the first review pass

The four audit subagents (security, route, service, data) surfaced several real issues. The following were fixed before finalizing, since they were unambiguous and matched this project's own stated rules (`.claude/rules.md` rule 3, and the already-configured `AUTH_PASSWORD_VALIDATORS`):

| File Path | Issue Type | Fix Applied |
|---|---|---|
| accounts/services.py | Password handling gap | `register_user()` was calling `create_user()` directly, silently bypassing `AUTH_PASSWORD_VALIDATORS` — a password like `"12345678"` would have been accepted. Added `validate_password()` call before user creation; `SignUpView` now returns 400 with validator messages. Covered by new `test_signup_rejects_weak_password`. |
| accounts/services.py, accounts/views.py | Request/Service coupling (rule 3 violation) | `authenticate_user()` took a Django `request` param and forwarded it into `authenticate()`, coupling the service layer to the route layer. Removed the parameter — `authenticate()` doesn't require it for the default backend. |
| accounts/views.py (ProfileView) | Route/Service/Data separation violation | `ProfileView.get_object()` queried the `Profile` model directly from the view, bypassing the service layer (independently flagged by both the route and service reviewers). Added `get_profile_for_user()` to `accounts/services.py`; view now calls it and translates `Profile.DoesNotExist` into a clean 404. |
| accounts/views.py (SignUpView) | Missing error handling | No `try/except` around `register_user()` — a concurrent duplicate-username race would have 500'd instead of returning a clean 400. Added `UsernameTakenError` (raised from `register_user()` on `IntegrityError`) and a matching `except` clause in `SignUpView`, mirroring the pattern `LoginView` already used for `InvalidCredentialsError`. Covered by new `test_signup_rejects_duplicate_username`. |
| accounts/views.py (LogoutView) | Inconsistent authorization declaration | Every other view declared `permission_classes` explicitly; `LogoutView` silently relied on the global default. Added `permission_classes = [IsAuthenticated]` explicitly for consistency/defense-in-depth. |

## Route / Service / Data layer summary (confirmed through third pass, no regressions)

- **Route:** `accounts/urls.py`/`views.py` remain thin and delegate to the service layer; every view has explicit `permission_classes`; `config/urls.py`'s `include()` has no path conflicts with `admin/`. New throttle wiring (`throttle_classes`/`throttle_scope`) is sound and DRF-native — no manual try/except needed for it.
- **Service:** `accounts/services.py` contains `register_user`, `authenticate_user`, `get_profile_for_user` — no request-object coupling, confirmed by both the service and route reviewers on this pass. Direct ORM calls inside these functions are expected given this project's data layer is `models.py` + `serializers.py` (no separate DAO), per `plan/feature-2-plan.md`. Minor note: `ProfileView`'s PUT/PATCH path (inherited from `RetrieveUpdateAPIView`) still saves directly via the serializer rather than through a service function — the read path was fixed, the write path wasn't. Not currently reachable in practice since `focus_area` is read-only and `name`/`cohort` updates have no business logic to encapsulate yet.
- **Data:** No insecure SQL (pure ORM). `register_user`'s multi-step write is correctly wrapped in `transaction.atomic()`, and the `except IntegrityError` sits outside the `with` block — verified this doesn't risk `TransactionManagementError`. Migrations (`0001_initial`, `0002_seed_focus_areas`) have correct dependencies and the data migration is reversible. Minor note: `ProfileSerializer.focus_area` is read-only, so it can't be updated via `PATCH /api/auth/profile/` yet — out of scope for AC1–AC3, worth a follow-up ticket if editing focus areas post-signup is needed.
