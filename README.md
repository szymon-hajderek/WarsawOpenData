# WarsawOpenData

Route planner for Warsaw.

> **Status:** early idea. There is no code yet.

## Planned features

- **Multi-stop routes.** Plan one trip through many places, with many means of transport.
- **Online route planning.** Change the route while the user travels.
- **Live delays.** Use real-time vehicle data to find the fastest route now.

## Data

- [Warsaw city API portal](https://api.um.warszawa.pl/)

## Environment setup (for agents)

Follow these steps to get a working environment. Run them from the repo root.
Keep this section current: every PR that adds a dependency or a tool updates it.

1. **Keys.** Copy `.env.example` to `.env` and fill in the keys. See `ACCESS.md`. Never commit `.env`.
2. **Frontend** (`frontend/`). Needs Node 18.18 or newer 18.x.
   - `cd frontend && npm install` (if `~/.npm` is root-owned: `npm install --cache <some dir>`)
   - `npm run dev` starts the app at http://localhost:5173
   - `npm run build` type-checks and builds
3. **Backend** (`backend/`, Python + FastAPI, managed with [uv](https://docs.astral.sh/uv/)).
   Not set up yet: there is no `pyproject.toml`. When it exists:
   - install uv: `brew install uv` (or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
   - `cd backend && uv sync` installs Python and all dependencies
   - `uv run fastapi dev` starts the API
4. **Routing, database, Docker.** Not set up yet (OpenTripPlanner, PostgreSQL + PostGIS, Docker).
