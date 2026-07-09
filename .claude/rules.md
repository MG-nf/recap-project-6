# Global Rules for Project Development

1. **GitHub Interaction:** All interactions with GitHub issues or project boards MUST be performed using the `gh` CLI. Do not attempt to use browser-based or web-scraping methods to fetch ticket data.
2. **State Machine Integrity:** Always check `WORKFLOW_STATE.md` before performing any task. Do not execute a skill if the state does not match the prerequisite requirements.
3. **Django Standards:** Use Django REST Framework for all API development. Do not use Django Templates. Ensure all logic adheres to the [Route/Service/Data] layer separation.
4. **Reporting:** When reporting issues or status, always use a table format with the columns: [File Path], [Issue Type], [Brief Description].

# Workflow Constraints

1. **No Pull Requests:** As a single-developer project, we perform direct merges from feature branches to `main`. Do not suggest or initiate `gh pr create` workflows.
2. **Branch Persistence:** We do not delete feature branches after merging. All feature branches must remain in the repository for historical record.
3. **Merge Process:** Use `git merge` locally to integrate features, followed by a `git push origin main` to update the remote repository.