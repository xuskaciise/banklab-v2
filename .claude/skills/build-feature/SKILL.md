---
name: build-feature
description: Build the next BankLab ROADMAP item end to end — pick it, plan in Somali, delegate backend/frontend to agents, review, verify, open the PR and tick the roadmap. Use when the user says "build the next feature", "continue", or names a ROADMAP number.
---

# Build the next ROADMAP feature

1. **Pick:** open `docs/ROADMAP.md`; take the item the user named, otherwise
   the first `[ ]` row whose `Needs` are all `[x]`. If a needed item is not
   done, say so and stop.
2. **Plan (Somali):** read that item's section in `docs/CONCEPT.md` and the
   relevant `docs/design/` file. Present a short plan in Somali: models, rules,
   endpoints, screens, tests, anything unclear. Wait for approval.
3. **Branch:** `git switch -c feat/<roadmap-no>-<slug>` from an up-to-date `main`.
   Mark the row `[~] feat/...` in ROADMAP.md.
4. **Backend:** run the `backend-dev` agent with the ROADMAP row and the
   approved plan. Read its summary, not the whole diff.
5. **Frontend:** if the item has screens, run the `frontend-dev` agent with the
   endpoint list from step 4.
6. **Review:** if the item touches money, ledger, tills, permissions or
   session scoping, run `ledger-reviewer`; fix real findings (via the same
   agent that wrote the code), then re-run it once.
7. **Verify:** run `test-runner`; then open the app in the built-in browser and
   walk through the main flow once as the target role.
8. **Finish:** tick the row `[x]` in ROADMAP.md, commit, and — after the user
   says yes — push and open the PR. Never push to `main`.
9. **Report (Somali):** what was built, how it was checked, what is left, and
   the next ROADMAP item. Suggest a fresh session for that next item.
