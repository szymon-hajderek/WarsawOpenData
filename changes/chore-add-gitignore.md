# chore/add-gitignore

- Add a root `.gitignore`: `.env` and `.env.*` (not `.env.example`), OS and editor files,
  Python and Node artifacts, large downloaded data (`*.zip`, `*.pb`, `*.osm.pbf` under `data/`).
- Track `.env.example` (variable names only).
- Add `ACCESS.md`: which API keys exist, where to get them, how to send them. No key values.
- `AGENTS.md`: two Project Knowledge lines about keys and `.env`.
