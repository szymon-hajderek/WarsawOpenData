# Street router

The street router of the project: walk, bike and accessible paths on the OSM graph of Warsaw.

- **Python (`backend/`) prepares the data:** download and clip OSM, build the walk / bike / accessible graphs
  with the cost model (numpy), and write them as `graph_<mode>.bin`.
- **The C++ program `street_router` (this folder) does every search.** It answers point-to-point routes between
  any two coordinates (`serve`, HTTP, the graphs stay in memory) and builds the all-pairs matrices between stops
  (`matrix`). The backend starts the server and calls it through `backend/street_router.py`.

Every path has three parts:

- `walk_m`: metres walked: footways, access to the graph, a **pushed bike**, the walk down to a metro platform;
- `bike_m`: metres ridden on a bike (0 in walk and accessible);
- `wait_s`: seconds that do not depend on speed: signals, crossings and **elevators (60 s each)**.

Travel time = `walk_m / walk speed + bike_m / bike speed + wait_s`. The router minimises exactly this, with the
speeds of the query (`speeds` in `POST /route`) or the mode's defaults (walk 1.3 m/s, bike 4.2 m/s, accessible
1.3 m/s). The matrices use the defaults.

## Files

All files are in `data/derived/street/` (git-ignored, about 2.4 GB):

| File | What it is |
|---|---|
| `points.csv` | One row per point: `index,id,kind,lat,lon,snap_walk_m,snap_bike_m,entrances`. `index` is the row / column in the matrices. `id` is the GTFS stop id (`ztm:700901`, `ztm:7014M:P1`, `pkp:…`, `wkd:…`) or the Veturilo id (`vet:…`). `kind` is `stop` or `veturilo`. `snap_*_m` is the distance to the nearest usable graph node. `entrances` is the number of metro entrances (0 for other points). |
| `walk.bin`, `bike.bin`, `accessible.bin` | **The result.** Little-endian `float32`, shape `(3, N, N)`, row-major. From point `i` to point `j`: `[0][i][j]` = `walk_m`, `[1][i][j]` = `bike_m`, `[2][i][j]` = `wait_s`. Self pairs = 0. `NaN` = no path or no data (a point more than 1000 m from the graph). |
| `graph_<mode>.bin` | The graph the router loads (format below). The backend rewrites it when it is older than the OSM cache or the GTFS zips. |
| `meta.json` | Per mode: number of points, far points, seconds, file size. Also the thread count. |

Reading the result in C++: `mmap` / `fread` the file into a `float[3][N][N]`. In numpy:
`np.memmap(path, np.float32, "r", shape=(3, N, N))`.

## Code map

| File | Role |
|---|---|
| `backend/sources/osm.py` | Data side: download + clip OSM, parse into `osm_graph.npz` (rebuilt when the `.pbf` is newer), the edges of each mode (rules, waits, bike pushing, elevators), the main component, and `points_graph()` = a mode's graph as a `StreetGraph`. `/api/osm/route` relays to the router. |
| `algorithms/street_model.py` | Pure cost-model functions used by `osm.py`: signal junctions, waits, joining points (`access_edges`). |
| `algorithms/street_graph.py` | `StreetGraph` and its file format (`save()`). |
| `backend/preprocess_street.py` | Writes `points.csv` + `graph_<mode>.bin` (`--graph-only`, `write_graphs()`), and runs `street_router matrix`. |
| `backend/street_router.py` | Python client: `route(a, b, mode, **options)`, plus `start()` / `stop()` of the server (used by `main.py`). |
| `algorithms/router/graph.hpp` | Loads a graph file; `Speeds::cost()` = the edge cost for the query's speeds. |
| `algorithms/router/snap.hpp` | Joins a coordinate to the graph (a 100 m grid over usable nodes; the rule of `osm.access`). |
| `algorithms/router/search.hpp` | Dijkstra from seeds to targets (point to point) or to every node (matrix); path recording. |
| `algorithms/router/main.cpp` | `matrix`, `route`, `serve` (cpp-httplib + nlohmann/json, fetched by CMake). |
| `algorithms/test_street_model.py` | Tests of the cost model, and of `street_router` (matrix, coordinate routes, the server) against a scipy oracle. |

## Modes

| Mode | Graph | Speed | Notes |
|---|---|---|---|
| `walk` | footways, paths, streets with foot access, steps | 1.3 m/s | symmetric for points outside signal junctions |
| `bike` | **riding** (`bike_m`): ways with bike access, oneway respected; **pushing** (`walk_m`): the `accessible` walk graph wherever riding is not allowed (against a oneway, footways, elevators) | 4.2 m/s riding, 1.3 m/s pushing | riding wins when both are possible on the same segment. No steps: a bike takes elevators. |
| `accessible` | the walk graph **without steps** (also no escalators), **plus elevators** (`highway=elevator` ways) | 1.3 m/s | for a wheelchair or a stroller. Kerbs, surface and slope are not modelled. |

## How a path is chosen

- **Map.** `osm.download()` fetches Geofabrik `mazowieckie` (300 MB) once. `osm._clip()` keeps what we use
  inside the ZTM area (`config.BBOX`): nodes and ways tagged `highway`, `crossing`, `railway`,
  `public_transport` or `entrance`, plus the nodes of those ways. The result, `data/osm/warsaw_ztm.osm.pbf`
  (31 MB), builds the graph in about 17 s.
- **Graph.** Every OSM way node is a vertex and every segment between two consecutive nodes is an edge
  (`osm._Handler`). Per mode, parallel edges are merged (the shortest is kept).
- **An edge is walked or ridden** and may have a wait. Its cost = `walk / walk speed + bike / bike speed + wait`;
  Dijkstra minimises this expected time. `walk_m`, `bike_m` and `wait_s` are the sums along the chosen path.
- **Waits** are average delays, paid when a node is entered:

  | Node | walk | bike | accessible |
  |---|---|---|---|
  | signal crossing (`crossing=traffic_signals`) | 27.2 s | 27.2 s | 27.2 s |
  | plain crossing | 2 s | 0 s | 2 s |
  | road signal (`highway=traffic_signals`) | 0 s | 20 s | 0 s |
  | elevator (`highway=elevator` node or way) | 60 s | 60 s | 60 s |

  Signals use the HCM formula `(C − g)² / 2C` with a 90 s cycle; OSM has no signal timings for Warsaw.
  Signal nodes closer than 30 m to each other (by path) form one **junction**, and so do the nodes
  between them (e.g. a traffic island). Entering a junction pays its largest wait once; moving inside it is free.
  Code: `algorithms/street_model.py` (`junctions`, `edge_wait`).
- **Joining a point to the graph.** A point connects to up to 6 nearest usable nodes, at most 30 m
  farther than the nearest one. Each point has a virtual *out* node (edges to those nodes) and a virtual
  *in* node (edges from them). This makes it a multi-source Dijkstra with start costs, and no path can
  pass through another point. These access segments are walked (`walk_m`), also on a bike.
- **Usable nodes = the main component.** Points join only nodes of the largest strongly connected component
  of the mode, so every point can reach every other one and back. Paths still use the whole graph.
  What is left out are islands that are not connected to the rest at all: closed estates, unconnected
  paths and, in `accessible`, places reachable only by steps. That is 1.2% of the nodes for walk,
  1.9% for accessible and 1.8% for bike. A point whose nearest node is on an island joins the main
  component a bit farther away (at most about 50 m); that distance is in `walk_m`.
- **Metro.** A metro platform (`ztm:…M:P1`) does not join the graph at its own position, because it is
  underground. Instead it joins through **all entrances of its station** (GTFS `location_type=2`,
  e.g. `7014M:E1…E9`), and Dijkstra picks the best one. Going between an entrance and the platform is a
  **150 m walk** (`walk_m`; stairs, corridors; about 2 min). Every entrance is assumed to have an elevator:
  modes without steps (`accessible`, `bike`) also pay 60 s for it (`wait_s`). 251 of the 253 GTFS entrances match an OSM
  `railway=subway_entrance` within 30 m. Most Warsaw metro platforms are island platforms (`ref=1;2`),
  so the travel direction does not change the access.
- **Only the default speeds are optimal.** For other speeds, `walk_m / v_walk + bike_m / v_bike + wait_s`
  is the time of the same path. A different path could be a bit faster.

Known gaps: a pedestrian crosses a road only where OSM connects the two sidewalks. Waits are averages
(no signal timing data, no green wave). An L-shaped walk across two legs of one junction pays once.
A metro transfer inside one station (Świętokrzyska M1 ↔ M2) goes out and in again (2 × 150 m walked).

## Build and run

You need a C++23 compiler (GCC 14+ or Clang 19+, for `<print>`) and CMake 3.20+. The first configure downloads
cpp-httplib v0.61.0 and nlohmann/json v3.12.0 (single headers).

```sh
cmake -S algorithms/router -B algorithms/router/build -DCMAKE_BUILD_TYPE=Release
cmake --build algorithms/router/build
```

**With the backend** nothing else is needed. At startup (`backend/main.py`, warm-up thread) `street_router.start()`
rewrites the graph files if they are stale (~30 s), starts `street_router serve data/derived/street --port 8090`
(log: `data/derived/street/router.log`) and waits for `/health`. While that runs, `/api/osm` and `/api/routes`
answer 503. It is stopped with the backend. Environment: `ROUTER_URL` = use a router that runs elsewhere (nothing
is started); `ROUTER_PORT` = port of the started one (default 8090).

**By hand:**

```sh
cd backend && uv run python preprocess_street.py --graph-only        # graph files only (~30 s)
algorithms/router/build/street_router serve data/derived/street       # [--port 8090] [--threads 4]
algorithms/router/build/street_router route data/derived/street/graph_walk.bin 52.2297,21.0122 52.2196,20.9652
cd backend && uv run python preprocess_street.py                     # graphs + the three matrices (~18 min, 16 threads)
```

### `POST /route`

```sh
curl -s localhost:8090/route -d '{"from": [52.2297, 21.0122], "to": [52.2196, 20.9652], "mode": "walk"}'
```

Body (JSON):

| Key | Meaning |
|---|---|
| `from`, `to` | `[lat, lon]` |
| `mode` | `walk`, `bike` or `accessible` (the modes `/health` lists) |
| `speeds` | optional `{"walk": m/s, "bike": m/s}`: the path is optimal for these speeds (default: the mode's) |
| anything else | **501** `{"error": "not implemented", "unimplemented": [keys]}`: callers can relay options as they come; the router says which ones it does not support yet |

Answer:

```json
{"seconds": 2870.5, "walk_m": 3634.9, "bike_m": 0.0, "wait_s": 74.4, "snap_m": [7.0, 4.5],
 "path": [[21.0122, 52.2297], [21.01228, 52.22966], "..."], "elevators": [], "steps": [[21.01139, 52.22944], "..."]}
```

- `path`: `[lon, lat]`, 5 decimals (about 1 m), from `from` to `to`. `elevators`: where the path boards one.
  `steps`: where a flight of steps starts (only in walk mode; the other modes have no steps).
- `snap_m`: distance from each point to its nearest usable graph node.
- Errors: `400` bad body / unknown mode / bad speeds, `422` a point is more than 1000 m from the graph, `404` no path.
- A coordinate joins up to 6 nearest usable nodes, at most 30 m farther than the nearest. The access segment is
  walked, and entering the graph pays the node's entry wait (a signal junction). This is the same rule as the
  stops in the matrix, so the same coordinates give the same result.
- Speed: ~1 ms between nearby points, ~0.4 s across the city (the search stops at the target).

`GET /health` → `{"modes": {"walk": {"nodes": …, "edges": …}, …}}`.

## Graph file (`graph_<mode>.bin`)

Little-endian, written by `StreetGraph.save()`. P = fixed points (stops, Veturilo; used by `matrix`), n = graph
nodes incl. 2 virtual nodes per fixed point, m = directed edges.

| Field | Type | Count | Meaning |
|---|---|---|---|
| magic | `char` | 4 | `SMG4` |
| n, m, p, access_k | `uint32` | 4 | sizes; access_k = how many nodes a coordinate joins (6) |
| walk_speed, bike_speed, access_extra_m, max_snap_m | `float32` | 4 | the mode's default speeds (m/s); +30 m; 1000 m |
| offset | `uint32` | n + 1 | CSR: the edges of node `u` are `offset[u] .. offset[u+1]` |
| target | `uint32` | m | edge target node |
| walk, bike, wait | `float32` | m each | metres walked, metres ridden, seconds of wait |
| flags | `uint8` | m | 1 = elevator, 2 = pushed bike, 4 = a point's access segment, 8 = metro entrance segment, 16 = steps |
| out_node, in_node | `uint32` | p each | virtual nodes of each fixed point |
| active | `uint8` | p | 1 = point is on the graph (≤ 1000 m), 0 = its row and column are `NaN` |
| lon, lat | `float64` | n each | node coordinates (a fixed point's virtual nodes get the point's position) |
| usable | `uint8` | n | 1 = a coordinate may join here (the mode's largest strongly connected component) |
| entry_wait | `float32` | n | seconds paid when the graph is entered at this node |

## Checks

- `cd backend && uv run pytest ../algorithms` runs the Python unit tests: junctions, islands, oneway,
  access, a metro platform with many entrances. It also checks `street_router` against a scipy oracle: the matrix,
  routes between coordinates (snapping like Python), query speeds, and the server's answers (400 / 422 / 501).
- `cd backend && uv run python ../algorithms/router/check_pairs.py` runs 100 stop-level pairs
  (`Grójecka 02 → Centrum 03`, 20 pairs of posts of the same stop, 79 random pairs 0.2–5 km apart).
  For walk and bike it compares the server's coordinate route with the matrix value of the same stops, and the GTFS
  stop position with the OSM platform node of the same post (`ref` = ZTM stop id). Output: `check_pairs.csv`.
- `uv run python report.py` adds section 5 to `data/REPORT.md`: sizes, medians, a check against
  `osm.route()`, the detour factor and symmetry.

## Last run

2026-10-17, map `warsaw_ztm.osm.pbf` (1 847 096 nodes, 2 092 772 segments), GTFS of that day, 16 threads.

| Mode | Points | Graph nodes (incl. virtual) | Directed edges | C++ time | File |
|---|---|---|---|---|---|
| walk | 7 494 | 1 862 084 | 4 125 134 | 347 s | 674 MB |
| bike | 7 494 | 1 862 084 | 4 233 311 | 427 s | 674 MB |
| accessible | 7 494 | 1 862 084 | 4 097 508 | 328 s | 674 MB |

- Far points (> 1000 m from the graph): 0. Unreachable pairs: 0.
- Server: about 800 MB with the three graphs loaded; ~1 ms for a transfer between nearby stops, ~0.4 s for a
  random pair across the city.
- Examples:
  - Grójecka 01 → 02 (walk): 108.6 m walked + 27.2 s (signal) = 1.8 min.
  - Metro Centrum → Centrum 03: walk 202.4 m (52 m + 150 m stairs) = 2.6 min; accessible the same + 60 s elevator = 3.6 min.
  - Bike, point 5140 → 6000: 261.7 m walked (access, pushing) + 9 346.4 m ridden + 217.8 s waits = 44.1 min.
- Checked before the walk / bike / wait split (same paths): 100-pair check C++ = `osm.route()` within 0.05 m / 0.05 s;
  walk and accessible symmetric (A → B = B → A); accessible vs walk distance ≤ +5% for 95.8% of pairs > 300 m.
