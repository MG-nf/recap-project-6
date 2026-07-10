# Review: Ticket 5 — AI Integration

Branch: `feat/ticket-5-ai-integration`

## Acceptance criteria verification (plan/ticket-5.md, as reinterpreted per its "Reinterpretation notice")

| # | Criterion (reinterpreted) | Status | Evidence |
|---|---|---|---|
| 1 | `.env` used for `OPENAI_API_KEY` (ensure `.env` is in `.gitignore`) | ✅ Met | `config/settings.py`: `OPENAI_API_KEY = env('OPENAI_API_KEY', default='')` (empty default, fails at request time not startup). `.env.example` has a placeholder-only entry. `.gitignore`'s existing `.env*`/`!.env.example` pattern already covers it. `AIClientConfigTest` covers both the missing-key and configured-key paths without any network call. |
| 2 | "Generate Summary": sends session history/resources to OpenAI, returns result as JSON | ✅ Met | `POST /api/goals/<pk>/generate-summary/` → `GenerateSummaryView` → `generate_summary_for_goal`. `GenerateSummaryTest` covers success, empty-goal 400, cross-user 404, unauthenticated 403, upstream-error 502, and (after fixes below) malformed-response 502 and no-leak. |
| 3 | "Suggest Next Steps": sends data, returns a 2-3 step JSON list | ✅ Met | `POST /api/goals/<pk>/suggest-next-steps/` → `SuggestNextStepsView` → `suggest_next_steps_for_goal`, truncates to 3, no error on fewer. `SuggestNextStepsTest` covers truncation, fewer-than-3, empty-goal, cross-user, unauthenticated, upstream error. |

Full suite: `python manage.py test` → 70/70 passing (through the fixes below). `python manage.py check` → 0 issues. No test in this suite makes a real network call — every AI-path test patches `goals.services.get_client`; the one test that calls the real `get_client()` (`AIClientConfigTest.test_get_client_returns_client_when_key_set`) only constructs the `openai.OpenAI` client object, which performs no I/O until a method is actually invoked.

## Issues found and fixed during this review

All four audit subagents (security, route, service, data) converged on the same two real, unambiguous bugs, plus one dead-code cleanup — all fixed before finalizing:

| File Path | Issue Type | Fix Applied |
|---|---|---|
| goals/services.py (`_complete`) | Information disclosure via error message, with no server-side visibility as a substitute | `AIServiceError` was built from `f"OpenAI request failed: {exc}"` — the raw SDK/network exception's string form — and both views returned it verbatim in the 502 response body to the client. This could leak upstream error bodies or SDK/library internals, and since nothing was logged anywhere, this exception text was the *only* record of the failure at all. Fixed: added a module logger (`logging.getLogger(__name__)`), `logger.exception(...)` now captures the full detail server-side, and `AIServiceError` carries a fixed, generic message ("The AI service is temporarily unavailable.") returned to the client instead of `str(exc)`. Covered by new `test_upstream_error_message_is_not_leaked_to_client`. |
| goals/services.py (`gather_goal_context`, `_context_to_prompt`) | Unbounded prompt size / cost — explicitly recommended by `/refine`'s security review, not implemented | Neither the number of sessions/resources pulled per goal nor individual field lengths were capped — a goal with hundreds of sessions or very long `notes` fields would produce an arbitrarily large (and arbitrarily expensive) prompt on a single request, on top of the separately-accepted absence of rate limiting. Fixed: `MAX_ITEMS_PER_GOAL = 20` caps sessions/resources pulled (both already ordered newest-first via `Meta.ordering` from tickets 3/4, so this keeps the most *recent* activity), `MAX_NOTE_LENGTH = 500` truncates each session's `notes` field. Covered by new `GatherGoalContextTest` (asserts both caps directly, without needing a real or fake OpenAI call). |
| goals/services.py (`_complete`) | Genuine gap: malformed API response would crash as unhandled 500, not the intended 502 | `response.choices[0].message.content` sat **outside** the `try/except`, which only wrapped the `client.chat.completions.create(...)` call itself. An empty `choices` list or `content=None` (both real possibilities for content-filtered/malformed completions) raised an uncaught `IndexError`/`AttributeError` — the same class of "unhandled 500 instead of a controlled error" bug found in tickets 3 and 4's reviews, just in a new location. Fixed: moved the content extraction inside the `try` block, and added an explicit empty-content check that also raises `AIServiceError`. Covered by new `test_malformed_response_with_no_choices_returns_502_not_500` and `test_empty_completion_content_returns_502_not_500`. |
| goals/services.py (`_complete`) | Dead/misleading code | `except AIConfigurationError: raise` was unreachable — `get_client()` (the only source of that exception) runs before the `try:` block begins, so nothing inside the `try` could ever raise it. Harmless (both views already catch `AIConfigurationError` independently, since it propagates through `_complete`/`generate_summary_for_goal`/`suggest_next_steps_for_goal` untouched either way), but misleading about where the exception is actually handled. Removed the dead clause and the now-unused `AIConfigurationError` import from `services.py` (views.py already imports it directly from `ai_client.py`, which is the only place it needs to be caught). |

## Confirmed clean (verified, not repeats of prior-ticket bugs)

- **Data isolation**: both new views scope to `request.user`'s own Goals via `get_goal_for_user`, returning 404 (not a leak) for another user's goal — identical pattern to every other Goal-touching view.
- **Client injection / test-safety**: `client=None` threading through `generate_summary_for_goal`/`suggest_next_steps_for_goal` → `_complete` is correct with no timing bugs; confirmed no test path can reach the real network.
- **Routing**: final URLs match the confirmed plan exactly, no collision with the existing `/api/goals/<pk>/` detail route (Django's fully-anchored `path()` patterns resolve unambiguously regardless of list order).
- **Exception coverage**: `NoSessionDataError` (400), `AIConfigurationError` (500), `AIServiceError` (502) are all now genuinely caught in both views with no path to an unhandled 500 (closing the same bug class flagged in tickets 3/4, this time confirmed correct after the `_complete` fix above).
- **Statelessness**: no new model/migration — confirmed by the data reviewer; only the four pre-existing `goals` migrations exist.
- **Dependency pin**: `openai==2.45.0` exactly matches the installed version (`pip show openai`).
- **No SSRF**: `Resource.url` values are sent as text content in the prompt, never fetched server-side.

## Route / Service / Data layer summary (confirmed after fixes, no regressions)

- **Route**: `GenerateSummaryView`/`SuggestNextStepsView` are thin plain `APIView`s (no CRUD/queryset fit), `permission_classes` explicit, ownership/404 pattern identical to `GoalDetailView.get_object()`.
- **Service**: new functions never take `request`; `gather_goal_context` raises `NoSessionDataError` *before* any paid API call is attempted for an empty goal; step-parsing regex correctly handles numbered/bulleted/plain LLM output shapes.
- **Data**: no new models/migrations (confirmed stateless scope); `gather_goal_context` is a single-Goal, per-request operation (no N+1/loop concern, unlike ticket 4's `resources_by_type` bug); ORM instances are fully converted to plain dicts before reaching prompt-building.
