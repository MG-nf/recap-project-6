# Refinement: Ticket 5 — AI Integration

Survey of the existing codebase against `plan/ticket-5.md`, via the security-reviewer, route-reviewer, service-reviewer, and data-reviewer subagents. This is the first ticket with an external network dependency (OpenAI) and the first with a real per-request cost — no prior ticket sets precedent for outbound API calls, so more of this refinement is genuinely new design than in tickets 2-4.

## Security review

| File Path | Issue Type | Brief Description |
|---|---|---|
| config/settings.py | API key handling | `SECRET_KEY`'s hard fail-fast check is disproportionate for `OPENAI_API_KEY` — a missing key only breaks two endpoints, not the whole app. Use `env('OPENAI_API_KEY', default='')` (empty, not a fake placeholder) and fail at request time when an AI endpoint is actually hit, not at Django startup. |
| .env.example | Placeholder discipline | Add `OPENAI_API_KEY=` (empty) or an obviously-fake value — never a real key — since this is the one `.env*` variant that isn't gitignored. |
| new AI service function | Prompt injection — low risk, contained | User fully controls all input text (Goal/Session/Resource fields), but the LLM's only output channel is a JSON response back to that same authenticated user — no downstream execution, no other users see it. No input sanitization/output validation needed for injection specifically; do cap total prompt size to bound token cost. |
| config/settings.py (REST_FRAMEWORK) | Cost control — missing throttle scope | `DEFAULT_THROTTLE_RATES` only has `signup`/`login` (IP-keyed, pre-auth abuse). These are the first endpoints where every request costs real money — need a new throttle scope, keyed by `request.user` (not IP, since these are always authenticated) via a standard `ScopedRateThrottle`, not the existing IP-keyed `AuthRateThrottle`. |
| goals/views.py | Data isolation (reuse, no change) | Must reuse `get_goal_for_user(request.user, pk)` + `Http404`-on-`DoesNotExist`, exactly like `GoalDetailView.get_object()` — mandatory, not optional. |
| n/a | SSRF | None — all data flows outbound only to the fixed, trusted OpenAI endpoint; `Resource.url` values are sent as text content, never fetched server-side. |

## Route review

| File Path | Issue Type | Brief Description |
|---|---|---|
| goals/urls.py | Routing convention | No existing "action" route precedent (every route so far is CRUD). Recommend flat paths under the Goal detail path: `goals/<int:pk>/generate-summary/`, `goals/<int:pk>/suggest-next-steps/` — hyphenated, matching REST convention over snake_case. |
| goals/views.py | View pattern | No DRF generic fits (no queryset/serializer CRUD) — follow the plain `APIView` pattern `accounts/views.py` already uses for `SignUpView`/`LoginView`/`LogoutView`. |
| goals/views.py | Ownership enforcement (reuse) | Same `get_goal_for_user` + `Http404` pattern as every other Goal-touching view. |
| goals/services.py | Error-handling gap (new territory) | No existing exception type for external-API failure — needs a new taxonomy (see service review), translated to HTTP status in the view, same spirit as `GoalNotOwnedError`/`InvalidStatusError`. |
| goals/views.py | Latency/timeout | First-ever request that blocks on outbound network I/O. Service layer should set an explicit client-side timeout so a hung OpenAI call doesn't hang a WSGI worker indefinitely; view should map a timeout exception to a specific status rather than a generic 500. |

## Service layer review

| File Path | Issue Type | Brief Description |
|---|---|---|
| goals/services.py | Function shape | `generate_summary_for_goal(goal, *, client=None)` / `suggest_next_steps_for_goal(goal, *, client=None)` — `client` defaults to `None`, function calls a factory only if none supplied, giving tests a direct injection point. |
| goals/ai_client.py (new) | Client instantiation boundary | Thin wrapper module with one `get_client()` reading `OPENAI_API_KEY` via `env()`, returning `openai.OpenAI(api_key=...)`. Gives tests one obvious patch target or lets them pass a fake client directly — no interface/abstraction layer needed for two endpoints. |
| goals/services.py | Prompt/data assembly | Data assembly (pulling `goal.title`/`desc`/`sessions`/`resources` into a plain-text/dict context) stays in `services.py` as business logic; a separate module for fixed instruction/template strings is reasonable, but not for pulling model data. |
| goals/services.py | Exception design | `NoSessionDataError` (empty Goal, mirrors `InvalidStatusError` → 400), `AIServiceError` (network/timeout/malformed response → 502), possibly split rate-limit/quota → 503, and a distinct config/auth error (bad/missing key → 500, since 502/503 wrongly implies "retry later" for a misconfiguration). |
| goals/services.py | "2-3 steps" enforcement | Treat as a soft prompt instruction; at most a cheap server-side truncate-to-3 safety net, not a hard validation error on 1 or 4 items. |
| goals/tests.py | Test-safety (critical) | Every test must use a fake/mock client via the `client=` kwarg or by patching `goals.ai_client.get_client` — never construct a real `openai.OpenAI()` in a test path. |

## Data layer review

| File Path | Issue Type | Brief Description |
|---|---|---|
| goals/models.py | Data-gathering scope | Everything needed already exists (`Goal.title/desc/status`, `goal.sessions.all()`, `goal.resources.all()`) — no new model/field needed for input. |
| goals/models.py | Persistence scope | No field to store generated summaries/next-steps exists, and the ACs only require returning JSON — this is stateless request/response, no new migration. Flag explicitly rather than silently deciding, since a future ticket might want caching/history. |
| goals/services.py | Empty-data edge case | A Goal with zero sessions AND zero resources needs an early return (specific error/message) rather than sending a near-empty, low-value prompt to a paid API. |
| goals/services.py | Missing assembly function | Needs a new function mapping `Goal` + its querysets into a plain-data payload before it reaches the OpenAI-calling code — mirrors `resources_by_type_for_goal`'s pattern of shaping data before it leaves the service layer. |
| requirements.txt | Dependency | Add `openai==<pinned-version>`, manifest-only change. |
| n/a | Indexes | None needed — no new query/filter/sort dimension introduced. |

## Scope decisions for `/plan`

1. **Routes**: `goals/<int:pk>/generate-summary/`, `goals/<int:pk>/suggest-next-steps/` as plain `APIView`s (not generics), reusing `get_goal_for_user` for ownership.
2. **Client injection**: new `goals/ai_client.py::get_client()` factory; service functions take an optional `client=None` kwarg for test injection. No real network call ever happens in `manage.py test`.
3. **Exception taxonomy**: `NoSessionDataError` (400), `AIServiceError` (502, network/timeout/malformed response), `AIConfigurationError` (500, missing/invalid key) — needs confirming with you at `/plan`, including whether rate-limit/quota gets its own 503 or folds into `AIServiceError`.
4. **Cost control**: new throttle scope (e.g. `ai_generate`), `request.user`-keyed via `ScopedRateThrottle` — the actual rate needs confirming with you at `/plan`.
5. **Statelessness**: no new model/migration — purely request/response. Confirmed by all reviewers as the correct scope for this ticket.
6. **"2-3 steps"**: soft prompt instruction, optional truncate-to-3 safety net, no hard validation — needs confirming with you at `/plan`.
7. **Open decision for `/plan`**: exact throttle rate, and whether to add a client-side request timeout value (e.g. 30s) now or treat as a later hardening pass.
