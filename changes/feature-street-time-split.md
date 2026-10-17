# feature/street-time-split

Follow-up of `feature/street-paths` (PR #57); this branch starts from it.

- Every street path splits into `walk_m` (walked: footways, access segments, a pushed bike, metro stairs),
  `bike_m` (ridden) and `wait_s` (signals, crossings, elevators). Time = walk_m / walk speed + bike_m / bike speed
  + wait_s, so walking and riding scale with a profile's own speeds; waits stay fixed.
- Pushing a bike is now walked distance, not extra wait.
- An elevator costs 60 s in every mode. Metro entrance <-> platform is a 150 m walk (was a fixed 120 s wait);
  modes without steps (bike, accessible) also pay the elevator assumed at every entrance.
- Matrices `<mode>.bin` are `(3, N, N)`: walk_m, bike_m, wait_s. Graph file `SMG3` (walk, bike, wait per edge).
  `street_matrix --route` prints `walk_m`, `bike_m`, `wait_s`; `/api/osm/route` adds `walk_m`, `bike_m`.
- Assumptions: 150 m for the metro stairs (about 2 min at 1.3 m/s); the path is optimal for the default speeds.
- Route server: `street_matrix --serve data/derived/street [--port 8090]` keeps the graphs of all modes in memory and
  answers `GET /route?mode=&from=&to=` (same JSON as `--route`) and `GET /health`. Built on cpp-httplib (one header,
  fetched by CMake). The search stops at the target and resets only the nodes it touched (~1 ms for nearby stops).
