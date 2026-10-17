# Changes on `refactor/changes-fragments`

- Replace the single shared `CHANGES.md` with a `changes/` folder: one file per branch.
- Migrate every existing section from `CHANGES.md` into its own `changes/<branch>.md` file.
- `AGENTS.md`: update the "Feature Branches" rule to require a per-branch `changes/<branch>.md` file instead of editing a shared `CHANGES.md`.
- Goal: two branches never edit the same change-notes file, so these notes stop causing merge conflicts.
- `AGENTS.md`: add a rule that Claude resolves merge conflicts automatically (never the user), especially in `AGENTS.md`.
