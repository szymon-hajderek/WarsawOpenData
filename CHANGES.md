# Changes on `feature/update-claude-md`

- `CLAUDE.md`: added a "Keep It Simple" rule.
- `CLAUDE.md`: Claude must check that the local copy is up to date (`git fetch`, pull `main`) before starting work.
- `CLAUDE.md`: PRs are created with `gh pr create`.
- `CLAUDE.md`: new "Project Knowledge" section (about the project, stack, folder structure, decisions) that Claude updates automatically whenever it learns something new.

# Changes on `add-deep-planning-skill`

- Add the `deep-planning` skill in `.claude/skills/deep-planning/SKILL.md`.
- The skill starts when the user describes a new feature.
- Phase 1: plan mode, many rounds of up to 4 questions, the plan file is updated after each round.
- Phase 2: after the plan is approved, the agent does not ask questions, except for destructive or outward-facing actions.

# Changes on `add-readme`

- Add `README.md`: project name, tagline, status note, 3 planned features, 1 data source.
