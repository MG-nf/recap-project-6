---
name: init-ticket
description: analyzes ticket, defines requirements
---

1. Execute the next steps ONLY if the state in WORKFLOW_STATE.md is "idle" or "done".
2. IF no ticket id is given, select a ticket from the "ready" column of the project board. Ask the user if work on this ticket should start.
3. ELSE check if the ticket with the given id actually exists on the GitHub Project Board for this project.
4. Generate plan/ticket-[ticket id].md with the requirements regarding that ticket.
5. Sanitize the ticket title (e.g., "Setup API" to "setup-api").
6. Execute: git checkout -b feat/ticket-[ticket id]-[sanitized ticket title].
7. Update WORKFLOW_STATE.md with the new branch name.
