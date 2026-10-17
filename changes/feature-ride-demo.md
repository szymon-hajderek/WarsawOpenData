# feature/ride-demo

Demo of a simulated ride: pick a ride, watch the synthetic user travel it in the app.

- Demo tab in the frontend (shown only when the backend runs in simulation mode): a ready scenario or any route
  (start, destination, hour), a route option, GPS error 10 / 30 / 50 m, then play / pause, speed 1x / 10x / 60x, time slider,
  the user's real position and the phone's GPS dot on the map, and the "which vehicle am I in?" window fed by the simulated detection.
- Backend: `GET /api/sim/scenarios` and `POST /api/sim/ride` (computes the whole ride with `journey.travel`, returns the timeline;
  the frontend plays it back). Documented in `data/API.md`.
- `integration/journey.py` moved to `backend/sim/journey.py` so the server can use it; `travel()` takes an optional `nearest`
  function (no HTTP call needed) and also returns the detections.
- `./demo.sh [scenario]` starts backend (simulation mode) and frontend.
- Test: `integration/gtfs/test_ride_api.py`; Vitest for `sampleRide`.

Assumptions: the "Jadę tą linią" button in the demo window does nothing; the route engine reads the real clock, so the demo sends
the simulated date and hour as `when`; the demo does not change the route engine.
