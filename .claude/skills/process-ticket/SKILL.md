---
name: process-ticket
description: pipeline for ticket processing
---

1. Run /init-ticket. Update WORKFLOW_STATE.md with the ticket ID, State: initialized and and the current time.
2. On the GitHub Project board, move the ticket to the "In progress" column.
3. Run /refine. Set state in WORKFLOW_STATE.md to refined. Update LastUpdated to the current time.
4. Run /plan. Set state in WORKFLOW_STATE.md to planned. Update LastUpdated to the current time.
5. Run /implement. Set state in WORKFLOW_STATE.md to implemented. Update LastUpdated to the current time.
6. Run /review. Set state in WORKFLOW_STATE.md to reviewed. Update LastUpdated to the current time.
7. STOP AND REPORT the plan/review-[ticket id].md.
8. On the GitHub Project board, move the ticket to the "In review" column.
9. Execute the following steps ONLY after I approved the review:
10. Update the state in WORKFLOW_STATE.md to done
11. Execute: git add . && git commit -m "feat([ticket id]): complete implementation".
12. Execute: git push (publish the feature branch)
13. Execute: git checkout main.
14. Execute: git pull.
15. Execute: git merge feat/ticket-[ticket id]-[sanitized ticket title].
16. Execute: git push (publish the main branch)
17. On the GitHub Project board, move the ticket to the "Done" column.
