# docs/cpp-live-updates

- Recorded the C++ split: the engine builds its own graph when it starts. Python does not send the graph.
- After startup, `update_state` carries only live data and values derived from it (positions, Veturilo availability, alerts, delays). `query_routes` still asks C++ for routes.
- The wire format is still undefined, and nothing calls `update_state` yet.
