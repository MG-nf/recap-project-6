# Ticket 5: AI Integration

**GitHub Issue:** [#5](https://github.com/MG-nf/recap-project-6/issues/5)
**Project Board Status (at intake):** Ready

## Blueprint

Integrate `openai` Python SDK. Configuration via `django-environ`.

## Acceptance Criteria

- [ ] `.env` used for `OPENAI_API_KEY` (ensure `.env` is in `.gitignore`).
- [ ] Action "Generate Summary": Sends session history/resources to OpenAI; renders result.
- [ ] Action "Suggest Next Steps": Sends data; renders 2-3 step list.

## Reinterpretation notice (rule conflict)

Same situation as ticket 4: the blueprint's language ("renders result," "renders ... list") is template-flavored, but this project is DRF-only (no Django Templates) per `.claude/rules.md` rule 3 and the precedent set by every prior ticket. Reinterpreted as:

- **AC2** ("Generate Summary... renders result") → a DRF endpoint (e.g. `POST /api/goals/<pk>/generate-summary/`) that sends that Goal's `LearningSession`/`Resource` data to the OpenAI API and returns the summary text as JSON.
- **AC3** ("Suggest Next Steps... renders 2-3 step list") → a DRF endpoint returning a JSON list of 2-3 suggested next steps, same input shape.

## Current-state notes (from repo inspection)

- `openai` is not yet in `requirements.txt` or installed — this ticket adds the project's first external, paid third-party API dependency and its first outbound network call (every prior ticket only talked to the local SQLite DB).
- `.env`/`.env.example` + `django-environ` are already wired (`config/settings.py` reads `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS` this way) — `OPENAI_API_KEY` should follow the identical `env('OPENAI_API_KEY', default=...)` pattern, added to `.env.example` (placeholder only) and documented, never committed as a real key.
- Data to send: `goals` app (tickets 3/4) already has `Goal` (with its `LearningSession`s and `Resource`s via `related_name="sessions"`/`related_name="resources"`) — "session history/resources" maps directly to a `Goal`'s existing related querysets; no new models needed for the input side.
- **Cost/test-safety concern (needs a decision at `/refine`/`/plan`):** calling the real OpenAI API from the automated test suite would cost money, require network access, and be flaky/slow — every test in this project so far runs fully offline against SQLite. The service-layer OpenAI client call should be mockable/injectable so `manage.py test` never makes a real network request; this needs to be an explicit design decision, not an afterthought.
- Route/Service/Data separation still applies: an `openai`-calling function belongs in a service layer (e.g. `goals/services.py` or a new module), never called directly from a view, mirroring every prior ticket's pattern.
- No existing precedent in this codebase for calling an external HTTP API — this is the first ticket where a service function's "write" is a network call, not a DB write, so `/plan` needs to decide error-handling behavior (API timeouts, rate limits, invalid/missing API key) since there's no established pattern to copy from `accounts`/`goals`.
