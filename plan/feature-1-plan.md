# Feature Plan: Ticket 1 — Project Scaffolding

Based on `plan/ticket-1.md` and `plan/refinement-1.md`. One step per acceptance criterion.

## Decisions (confirmed with user)

- `requirements.txt` will be the full `pip freeze` output (`asgiref==3.11.1`, `Django==6.0.7`, `sqlparse==0.5.5`, `tzdata==2026.2`) rather than just `Django==6.0.7`, since the active venv is already clean and this is the real reproducible dependency closure.
- `db.sqlite3` will be added to `.gitignore` **and** untracked via `git rm --cached db.sqlite3`, not left as a tracked file, to actually close the exposure risk security-reviewer flagged (not just prevent it going forward).

## Step 1 — AC1: "Project initialized and runnable via `python manage.py runserver`"

Already satisfied by existing scaffolding (`manage.py`, `config/` package). No code change needed.

- **Test:** Run `python manage.py check` (no errors) and `python manage.py runserver` (starts without exceptions, serves the default Django landing page). This is a verification step, not new code — no automated test to write since there's no app logic yet.

## Step 2 — AC2: "Virtual environment configured (or `requirements.txt` present)"

- **Test:** After creating `requirements.txt`, verify reproducibility: in a scratch venv, `pip install -r requirements.txt` succeeds and `python -m django --version` reports `6.0.7`.
- **Implementation:** Create `requirements.txt` at repo root with the pinned versions listed above.

## Step 3 — AC3: "Git repository initialized with `.gitignore`"

Git init and a base `.gitignore` already exist; the gap is that `db.sqlite3` is tracked despite being project-state, not source.

- **Test:** After the change, `git ls-files | grep db.sqlite3` returns nothing (untracked), and `git status` shows `db.sqlite3` as ignored, not as a pending deletion.
- **Implementation:**
  1. Add `db.sqlite3` to `.gitignore`.
  2. Run `git rm --cached db.sqlite3` to remove it from the index while keeping the file on disk.
