---
name: deep-planning
description: Use when the user describes a new feature or a change and the work needs a plan. Enters plan mode and interviews the user in many rounds of questions, until every part of the change is clear. Stops asking once planning ends.
---

# Deep planning

## Phase 1: Planning (ask as much as you can)

1. Call `EnterPlanMode`. Stay in plan mode for the whole phase.
2. Read the repository first. Do not ask what the code already answers.
3. Write a first draft of the plan to the plan file. Mark each gap as `OPEN`.
4. Ask questions with `AskUserQuestion`. Send up to 4 questions per round.
   Put your recommended option first.
5. After each round, update the plan file. Move answered items out of `OPEN`.
   Add the new `OPEN` items that the answers created.
6. Repeat steps 4 and 5. Plan for many rounds, not one or two.
   An answer usually opens 1 to 3 new questions: follow each of them.
7. Do not stop at "enough". Stop only when both conditions hold:
   - `OPEN` is empty, and
   - you asked the user in a last round whether anything is missing, and the user said no.

Cover these areas, one by one. Do not skip an area. Write "not applicable" in the plan if it does not apply.
- goal and the problem the feature solves
- users and use cases
- scope: what is in, what is out
- behavior of each changed element, including edge cases and errors
- data: sources, formats, volume, quality
- interfaces, files, and modules that change
- compatibility and migration
- tests and acceptance criteria
- risks, dependencies, order of work
- branch, PR, and `CHANGES.md` (see `CLAUDE.md`)

Rules for questions:
- One question covers one decision.
- Ask about a detail even if it looks minor. A wrong guess costs more than a question.
- Do not repeat a question the user already answered.
- Finish each round with a short summary of what changed in the plan.

## Phase 2: After the plan (do not ask)

1. Call `ExitPlanMode` when the user approves the plan.
2. After approval, do not ask clarifying questions. Questions here stop automatic loops.
3. Decide small open points yourself. Use the plan, the code, and sensible defaults.
4. Write each such decision as an assumption in `CHANGES.md` or the PR description.
5. Ask the user only in these cases:
   - the action is destructive or cannot be undone (delete data, force push, overwrite);
   - the action reaches outside the repository (publish, send, pay);
   - the plan and the code contradict each other, and no default is safe.
