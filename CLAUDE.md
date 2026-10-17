# CLAUDE.md

This file contains instructions for the AI assistant (Claude) working in this repository.

## Git Rules

- **Only Claude performs commits, pushes, and other git operations.**
  The user does not create commits or push manually — all git history operations
  (commit, push, merge, rebase, tag, etc.) are carried out by the AI assistant.

## Pull Requests

- **Every change is introduced through a Pull Request.**
- Whenever we want to add something, we create a new branch and open a Pull Request.
- Nothing is committed directly to `main` — changes land on `main` only via a merged PR.

## Feature Branches

- **Every new branch created for a feature must contain a `CHANGES.md` file.**
- The `CHANGES.md` file briefly describes the changes made on that branch.
- The description should be concise — a short list of the most important changes / points is enough.
- The `CHANGES.md` file is kept up to date as work on the branch progresses.
