# AGENTS.md

This file contains instructions for the AI assistant (Claude) working in this repository.
It is the single source of truth. `CLAUDE.md` only imports this file.
Everything in this repo (files, commits, PRs) is written in English.

## Keep It Simple

- **Do not build overly complicated things.** This is a hackathon POC.
- Prefer the simplest solution that works. Add complexity only when it is really needed.

## Git Rules

- **Only Claude performs commits, pushes, and other git operations.**
  The user does not create commits or push manually — all git history operations
  (commit, push, merge, rebase, tag, etc.) are carried out by the AI assistant.
- **Always make sure the local copy is up to date before starting any work:**
  1. Run `git fetch origin`.
  2. Check that local `main` is not behind `origin/main` (`git status -sb`).
  3. If it is behind, run `git checkout main` and `git pull origin main`.
  4. Only then create a new branch from the updated `main`.
- Also check that the local copy is up to date before committing/pushing on an existing branch.
- **Claude resolves merge conflicts automatically — the user never resolves them manually.**
  This applies in particular to `AGENTS.md`: whenever it conflicts, Claude resolves it on its own,
  keeping the valid rules and knowledge from both sides and removing duplicates or stale entries.

## Pull Requests

- **Every change is introduced through a Pull Request.**
- Whenever we want to add something, we create a new branch and open a Pull Request.
- Nothing is committed directly to `main` — changes land on `main` only via a merged PR.
- PRs are created with the GitHub CLI (`gh pr create`) and need a short title and description.
- **Before every PR, update the "Environment setup (for agents)" section in `README.md`.**
  If the branch adds or changes a dependency, a tool, a command, an env variable or a data download,
  write the exact install steps there (e.g. `uv sync`, `npm install`). If nothing changed, leave it as is.
  A new agent must be able to build the full environment from that section alone.

## Feature Branches

- **Before you create any new branch, run the `deep-planning` skill** (`.claude/skills/deep-planning/SKILL.md`).
  Plan the change with the user first. Create the branch only after the user approves the plan.
  If your tool cannot run skills, read that file and follow its steps.
- **Every feature branch adds its own file under `changes/`**, named after the branch with
  slashes replaced by dashes (e.g. branch `feature/add-map` -> `changes/feature-add-map.md`).
- That file briefly describes the changes made on the branch — a short list of the most
  important points is enough — and is kept up to date as work on the branch progresses.
- **Do not use a single shared `CHANGES.md`.** One file per branch means two branches never
  edit the same file, so these change notes never cause merge conflicts. See `changes/README.md`.

## Project Knowledge

> **Claude: keep this section up to date automatically.**
> Whenever you learn something new about the project (goal, decisions, data sources,
> structure, conventions, team preferences), add it here in the same PR as the related
> change — without waiting to be asked. Update often, keep entries short, and fix or
> remove anything that is no longer true. If there is no related PR, open a small PR
> just for the knowledge update.

### What is this project

- **Name:** WarsawOpenData — a hackathon project based on Warsaw open data.
- **Goal:** a route planner for Warsaw that uses Veturilo (city bikes) at every stage of a trip
  together with public transport, which is hard to do today. Further goals: create new city data
  automatically (anonymised), inclusivity (adjust the pace for walking / cycling / stroller),
  and later "own bike + public transport".
- **POC use case:** (1) start = user's location or typed, (2) destination, (3) get n connection
  options that use Veturilo at any stage.
- **Planned features:** Veturilo rental integration, anonymised data for the city, intermediate
  stops, search priorities (max transfers, excluded areas, preferred modes, safety / roadworks,
  scenic, calories), "Discover" tourist routes, own bike, e-scooters, travel profile.
- **Jury criteria (design for them):** inclusivity / accessibility / diversity, scalability to
  other cities, safety, privacy, evidence-based, technical correctness, business model.
- **Time frame:** 24h hackathon, so keep everything simple.
- **Status:** the frontend UI exists (mock routing); backend, routing and data are empty.

### Tech stack

- Frontend: React + TypeScript + Vite
- Map: Leaflet + OpenStreetMap
- Backend: Python + FastAPI
- Database: PostgreSQL + PostGIS (SQLite is enough for the POC)
- Routing: OpenTripPlanner (supports GTFS, GBFS and OSM)
- Deployment: Docker

### Folder structure

- `frontend/` — React + TypeScript + Vite app
- `ui/` — UI feature work; `ui/concept-art/` holds concept graphics
- `backend/` — FastAPI app
- `algorithms/` — algorithms (mandatory folder)
- `db/` — database files and setup
- `routing/` — OpenTripPlanner config
- `data/` — datasets, one subfolder per data type: `gtfs/`, `gbfs/`, `osm/`, `geojson/`

### Frontend (`frontend/`)

- Stack: React 18, Vite 5, TypeScript, Material UI v6 (+ icons), Leaflet 1.9 with `react-leaflet` 4.
  Node on the dev machine is 18.18, so stay on these versions (newer Vite needs Node 20+).
- Screens, one flow: map with the user's location and start / destination fields on top ->
  list of connection options (with preview on the map) -> chosen route (clean route on the map,
  summary, steps). State lives in `src/App.tsx` (`step`: search / options / route).
- **Routing is a mock.** `src/api/routes.ts` (`fetchRouteOptions`) is the only seam to the backend.
  Replace its body with a call to FastAPI / OpenTripPlanner returning `RouteOption[]`
  (types in `src/types.ts`). Costs and speeds in the mock are rough estimates.
- Place search: Nominatim (`src/api/geocode.ts`), limited to Warsaw, debounced; it has a usage
  limit of about 1 request per second.
- Theme: all colours in `src/theme.ts` (light + dark; toggle on the map, defaults to the system
  setting). Colours and icons of transport modes: `src/modes.tsx`.
- Two map looks, switched with the layers button on the map (saved in localStorage, `src/mapVariant.tsx`):
  - **v1** (default): plain OpenStreetMap raster tiles; dark mode is a CSS filter (`.tiles-dark` in `src/index.css`).
  - **v2**: flat pastel vector map. Vector tiles from OpenFreeMap (no key) drawn by MapLibre GL inside Leaflet
    (`@maplibre/maplibre-gl-leaflet`, loaded on demand). The style is ours: `src/map/styleV2.ts` (palettes for
    light + dark, more labels when zoomed in). Round lavender buttons and markers live in `src/components/MapView.tsx`.
  - CARTO basemaps now return "API KEY REQUIRED", so do not use them. OpenFreeMap has no SLA; there is no fallback to v1.
- Layout is mobile first; from 600 px (`sm`) the panels sit on the left side.
- Design references (user's screenshots): ride-choice list (selected card outlined), dark map with
  a clean route and round stop markers, light map with a bottom sheet.
- Run: `npm install`, `npm run dev` (http://localhost:5173), `npm run build` (type-check + build).

### Decisions and notes

- Texts shown in the app are in Polish (users are in Warsaw); code, comments and docs are in English.
- The user is the UI person on the team; other people work on pathfinding, data and the backend.
- Local tooling quirks: `~/.npm` can be root-owned, so use `npm i --cache <some dir>`;
  `gh` is in `/opt/homebrew/bin` and `npm` in `/usr/local/bin` (add them to `PATH` in shell calls).
- In the Vite dev server, editing a file re-runs effects (hot reload), which resets the UI step.
- The browser pane has no geolocation, so the start must be typed when testing.

- API keys live only in `.env`, which is git-ignored. Never commit `.env` or paste a key into a file, commit or chat.
- `ACCESS.md` lists the keys (`PORTAL_KEY`, `WAW_API_KEY`, `PLK_KEY`), how to get them and how to send them.
- Empty folders are kept in git with `.gitkeep`.
- Docker files (`docker-compose.yml`, `Dockerfile`) are not added yet.
- The user writes in Polish; replies to the user are in Polish, repo content is in English.
- The Cursor workspace root is the parent folder `hackathon`, and this repo lives in
  its subfolder `WarsawOpenData`. The repo's instruction file is `AGENTS.md`, because
  Cursor reads it (a plain `CLAUDE.md` may not be loaded).
- Change notes live in `changes/` (one file per branch), not in a single shared
  `CHANGES.md`, so parallel branches do not create merge conflicts in change notes.
- `README.md` has an "Environment setup (for agents)" section: how to install the full environment
  (keys, frontend with npm, backend with uv). It is updated in every PR that changes setup.
