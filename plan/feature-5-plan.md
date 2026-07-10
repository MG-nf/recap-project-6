# Feature Plan: Ticket 5 — AI Integration

Based on `plan/ticket-5.md` and `plan/refinement-5.md`. One step per acceptance criterion (as reinterpreted — see `plan/ticket-5.md`'s "Reinterpretation notice": both actions return JSON, not rendered templates).

## Decisions (confirmed with user)

- **Model:** `gpt-4o-mini`, hardcoded for now (not env-configurable — simplest option for a two-endpoint feature; revisit if a future ticket needs to change it without a deploy).
- **Throttling:** none for this ticket, despite the cost-control recommendation from `/refine`'s security review — explicit user call to keep scope minimal; flagged as an accepted, known trade-off, not an oversight.
- **"2-3 steps" enforcement:** soft prompt instruction; truncate to the first 3 server-side if the model returns more, no error on fewer.
- **Timeout & error taxonomy:** 30s client-side timeout on the OpenAI call. Two exceptions: `AIServiceError` (502 — network/timeout/malformed response/rate-limit/quota, all folded together) and `AIConfigurationError` (500 — missing/invalid `OPENAI_API_KEY`).
- **Statelessness:** no new model/migration — purely request/response, per all four refinement reviewers.
- **Client injection:** `goals/ai_client.py::get_client()` factory (raises `AIConfigurationError` if `OPENAI_API_KEY` is empty); service functions take an optional `client=None` kwarg so tests always inject a fake client, never hitting the network.

Extends the existing `goals` app — no new app. Route/Service/Data layers kept separate:
- **Route layer:** `goals/views.py` gains `GenerateSummaryView`/`SuggestNextStepsView` (plain `APIView`, not generics — no CRUD/queryset here); `goals/urls.py` gains `goals/<int:pk>/generate-summary/`, `goals/<int:pk>/suggest-next-steps/`.
- **Service layer:** `goals/services.py` gains `gather_goal_context(goal)` (assembles Goal + sessions + resources into a plain dict, raising `NoSessionDataError` if both are empty), `generate_summary_for_goal(goal, *, client=None)`, `suggest_next_steps_for_goal(goal, *, client=None)`.
- **Data layer:** no changes — reuses existing `Goal`/`LearningSession`/`Resource` models and querysets.
- **Config:** `config/settings.py` gains `OPENAI_API_KEY = env('OPENAI_API_KEY', default='')`; `.env.example` gains a placeholder; `requirements.txt` gains `openai==<pinned version>`.

## Step 1 — AC1: "`.env` used for `OPENAI_API_KEY` (ensure `.env` is in `.gitignore`)"

- **Test:** `goals/tests.py::AIClientConfigTest` — with `OPENAI_API_KEY` unset/empty, `goals.ai_client.get_client()` raises `AIConfigurationError`; with a fake key set (via `override_settings`), `get_client()` returns a client instance without making any network call.
- **Implementation:** `config/settings.py`: `OPENAI_API_KEY = env('OPENAI_API_KEY', default='')` (empty default, no fail-fast at startup — mirrors `SECRET_KEY`'s pattern but fails at call time, not import time, since this only gates two endpoints). `.env.example`: add `OPENAI_API_KEY=` placeholder with a comment that it must stay empty/fake in this file. `requirements.txt`: add `openai==<pinned>`. New `goals/ai_client.py`: `get_client()` reads `settings.OPENAI_API_KEY`, raises `AIConfigurationError` if empty, else returns `openai.OpenAI(api_key=..., timeout=30)`.

## Step 2 — AC2: "Action 'Generate Summary': Sends session history/resources to OpenAI; renders result" (reinterpreted: JSON response)

- **Test:** `goals/tests.py::GenerateSummaryTest` — authenticated `POST /api/goals/<pk>/generate-summary/` for a Goal with sessions/resources, using a fake injected client, returns 200 with a `{"summary": "..."}` body built from the fake client's canned response; a Goal with no sessions and no resources returns 400 (`NoSessionDataError`); a fake client raising a simulated API error returns 502; cross-user Goal returns 404; unauthenticated returns 403.
- **Implementation:** `goals/services.py::gather_goal_context(goal)` (dict of title/desc/status/sessions/resources); `generate_summary_for_goal(goal, *, client=None)` (calls `gather_goal_context`, raises `NoSessionDataError` if empty, else calls `client.chat.completions.create(model="gpt-4o-mini", ...)` wrapped in try/except mapping SDK exceptions to `AIServiceError`, returns the summary text). `goals/views.py::GenerateSummaryView(APIView)`: `get_goal_for_user` + `Http404` (same pattern as `GoalDetailView`), calls the service, catches `NoSessionDataError` → 400, `AIServiceError` → 502, `AIConfigurationError` → 500. `goals/urls.py`: `goals/<int:pk>/generate-summary/`.

## Step 3 — AC3: "Action 'Suggest Next Steps': Sends data; renders 2-3 step list" (reinterpreted: JSON list response)

- **Test:** `goals/tests.py::SuggestNextStepsTest` — authenticated `POST /api/goals/<pk>/suggest-next-steps/` with a fake client returning 4 steps → response truncated to the first 3 (`{"steps": [...]}`, length 3); a fake client returning 2 steps → response has all 2 (no padding/error); empty-Goal → 400; simulated API error → 502; cross-user Goal → 404; unauthenticated → 403.
- **Implementation:** `goals/services.py::suggest_next_steps_for_goal(goal, *, client=None)` — same context-gathering/error-wrapping shape as `generate_summary_for_goal`, parses the model's response into a list, truncates to `[:3]` before returning. `goals/views.py::SuggestNextStepsView(APIView)` — same pattern as `GenerateSummaryView`. `goals/urls.py`: `goals/<int:pk>/suggest-next-steps/`.
