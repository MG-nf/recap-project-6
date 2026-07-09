---
name: process-ticket
description: pipeline for ticket processing
---

1. Run /init-ticket. Update WORKFLOW_STATE.md with the ticket ID, State: initialized and and the current time.
2. Run /refine. Set state in WORKFLOW_STATE.md to refined. Update LastUpdated to the current time.
3. Run /plan. Set state in WORKFLOW_STATE.md to planned. Update LastUpdated to the current time.
4. Run /implement. Set state in WORKFLOW_STATE.md to implemented. Update LastUpdated to the current time.
5. Run /review. Set state in WORKFLOW_STATE.md to reviewed. Update LastUpdated to the current time.
6. STOP AND REPORT the plan/review-[ticket id].md. Update the state to done AFTER I approved the review.
