# Changes on `feature/nearest-bus-detection`

- `algorithms/nearest_buses.py`: rank buses by MSE between the user's last 1-3 positions and each bus track
  (user point paired with the bus point closest in time). Tests in `algorithms/test_nearest_buses.py`.
- `backend/bus_detect.py`: polls live bus positions every 10 s (`LIVE_BUSES_URL`), keeps the last 3 per vehicle,
  `POST /api/live/nearest-buses` returns 4 candidates + all live lines. Mounted in `main.py`; pytest dev group.
- `frontend/src/api/vehicle.ts`: real detection instead of the mock (mock stays as a fallback), location buffer
  in memory, `bus-popup` event on `window`, `requestLinePopup()` for manual line choice.
- `frontend/src/App.tsx`: detection runs once after start and on `requestLinePopup()`, not on every move.
- `frontend/vite.config.ts`: `/api` proxy to the backend.
- Assumptions: 4 candidates (1 + 3) to match `VehicleSheet`; `direction` is empty (live feed has none);
  only buses (no trams); feed time is server local time; `uv.lock` was not regenerated (no uv on this machine),
  `uv sync` updates it; `npm run build` was not run (no Node on this machine).
