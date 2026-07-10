# Review: Ticket 1 — Project Scaffolding

Branch: `feat/ticket-1-project-scaffolding`

## Acceptance criteria verification (plan/ticket-1.md)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Project initialized and runnable via `python manage.py runserver` | ✅ Met | Pre-existing; `python manage.py check` passes with 0 issues. |
| 2 | Virtual environment configured (or `requirements.txt` present) | ✅ Met | `requirements.txt` added (`asgiref==3.11.1`, `Django==6.0.7`, `sqlparse==0.5.5`, `tzdata==2026.2`). Verified reproducible: fresh scratch venv + `pip install -r requirements.txt` installs cleanly and reports `Django 6.0.7`. |
| 3 | Git repository initialized with `.gitignore` | ✅ Met (literally) — ⚠️ see finding below | Repo already initialized; `.gitignore` now includes `db.sqlite3`, and `git rm --cached db.sqlite3` removed it from the index. |

## Security audit

| File Path | Issue Type | Brief Description of Inconsistency |
|---|---|---|
| db.sqlite3 (via `.git` history, commit `bd349b7`) | **Sensitive Data Exposure (OWASP A02/A05) — unresolved** | `git rm --cached` only stops future tracking. The file is already committed in the repo's very first commit and **confirmed present in `origin/main`'s current tree** (independently verified: `git ls-tree -r origin/main` still lists `db.sqlite3`). It remains permanently recoverable via `git show bd349b7:db.sqlite3` or GitHub's own history/UI. Actually closing this requires a history rewrite (`git filter-repo` or BFG) + force-push, and rotating any credentials/data that were ever seeded into that file. |
| .gitignore | Informational | Adding `db.sqlite3` is correct going forward but should not be read as having closed the historical exposure. |
| requirements.txt | Dependency check | No known-vulnerable pins. `Django==6.0.7` is the current latest patch release (itself a security release per djangoproject.com, 2026-07-07). `asgiref`/`sqlparse`/`tzdata` pins are consistent companions. |
| config/settings.py (pre-existing, untouched this ticket) | Hardcoded secret / insecure config | Noted for completeness, out of scope for ticket 1: `SECRET_KEY` is the insecure `startproject` default and `DEBUG = True`. Compounds risk given the db.sqlite3 history exposure above. Belongs in a future settings-hardening ticket. |

## Route audit

No routing/view code touched or exists beyond `config/urls.py`'s default `admin/` path. Nothing to flag.

## Service layer audit

No service-layer code exists in the repo. Nothing to flag.

## Data layer audit

No models/migrations exist yet. `DATABASES['default']['NAME']` in `config/settings.py` is unaffected by the untracking (still resolves to the on-disk file). Non-blocking note: once `db.sqlite3` is untracked, each developer's local database will diverge over time — no seed/fixture strategy exists yet, worth planning for once models are introduced.

## Open item requiring a decision before merge

The chosen approach (`.gitignore` + `git rm --cached`) satisfies acceptance criterion 3 as literally written, but does **not** resolve the underlying exposure risk that motivated the finding during refinement — the database file is still retrievable from git history on the pushed remote. Options:
1. Merge as-is; open a follow-up ticket for a history rewrite + force-push (lower risk to execute now, since this repo has an active remote and force-pushing rewritten history requires care).
2. Do the history rewrite now, before merging, since `main` itself doesn't have this fix yet and the blast radius of a rewrite is smaller before it spreads further.

This is a call for the ticket owner, not something to decide unilaterally given a history rewrite + force-push is a hard-to-reverse operation on shared remote history.
