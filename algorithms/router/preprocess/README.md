# Street matrix preprocess

For **every ordered pair** of points (GTFS boarding points + Veturilo stations) and for each of three
modes (**walk**, **bike**, **accessible**), this step finds the cheapest street path on the OSM graph.
For each pair it stores three parts of the trip:

- `walk_m`: metres walked: footways, access to the graph, a **pushed bike**, the walk down to a metro platform;
- `bike_m`: metres ridden on a bike (0 in walk and accessible);
- `wait_s`: seconds that do not depend on speed: signals, crossings and **elevators (60 s each)**.

Travel time = `walk_m / walk speed + bike_m / bike speed + wait_s`. The search minimises this with the default
speeds (walk 1.3 m/s, bike 4.2 m/s, accessible 1.3 m/s); for another profile put its own speeds in the same
formula (it is then the time of the same path).

Python (`backend/`) prepares the graph. The C++ program in this folder runs the all-pairs Dijkstra.

## Deliverable of a run

All files are in `data/derived/street/` (git-ignored, about 2.4 GB):

| File | What it is |
|---|---|
| `points.csv` | One row per point: `index,id,kind,lat,lon,snap_walk_m,snap_bike_m,entrances`. `index` is the row / column in the matrices. `id` is the GTFS stop id (`ztm:700901`, `ztm:7014M:P1`, `pkp:…`, `wkd:…`) or the Veturilo id (`vet:…`). `kind` is `stop` or `veturilo`. `snap_*_m` is the distance to the nearest usable graph node. `entrances` is the number of metro entrances (0 for other points). |
| `walk.bin`, `bike.bin`, `accessible.bin` | **The result.** Little-endian `float32`, shape `(3, N, N)`, row-major. From point `i` to point `j`: `[0][i][j]` = `walk_m`, `[1][i][j]` = `bike_m`, `[2][i][j]` = `wait_s`. Self pairs = 0. `NaN` = no path or no data (a point more than 1000 m from the graph). |
| `graph_<mode>.bin` | Input of the C++ program (see below). An intermediate file that is kept so a run can be repeated. |
| `meta.json` | Per mode: number of points, far points, seconds, file size. Also the thread count. |

Reading the result in C++: `mmap` / `fread` the file into a `float[3][N][N]`. In numpy:
`np.memmap(path, np.float32, "r", shape=(3, N, N))`.

## Code map

| File | Role |
|---|---|
| `backend/sources/osm.py` | OSM -> street graph per mode (edge rules, waits, bike pushing, elevators), the main component, `points_graph()` = the graph + virtual nodes for points, returned as a `StreetGraph`. `route()` = one path between two coordinates in scipy (API). |
| `algorithms/street_model.py` | Pure cost-model functions used by `osm.py`: signal junctions, waits, joining points (`access_edges`). |
| `algorithms/street_graph.py` | `StreetGraph` (the graph handed to C++) and its file format, `save()`. |
| `backend/preprocess_street.py` | Orchestration: points -> `points_graph` -> `graph_<mode>.bin` -> C++ -> `<mode>.bin`. |
| `algorithms/router/preprocess/street_matrix.cpp` | The search only: all-pairs Dijkstra, `--route` paths and the `--serve` HTTP server (cpp-httplib, fetched by CMake). |
| `algorithms/test_street_model.py` | Unit tests of the cost model and of the C++ program against a small scipy oracle. |

The graph is built only in Python and searched only in C++. The one other search is `osm.route()`,
for a path between two arbitrary coordinates (the C++ program only knows the points of a graph file).

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

You need a C++23 compiler (GCC 14+ or Clang 19+, for `<print>`) and CMake 3.20+. The first CMake configure
downloads cpp-httplib v0.61.0 (one header) for the server.

```sh
cmake -S algorithms/router/preprocess -B algorithms/router/preprocess/build -DCMAKE_BUILD_TYPE=Release
cmake --build algorithms/router/preprocess/build
cd backend && uv run python preprocess_street.py            # all modes; or: walk / bike / accessible
```

`preprocess_street.py` builds `points.csv` and `graph_<mode>.bin`, runs the C++ program and writes
`meta.json`. The program can also be run by hand:

```sh
algorithms/router/preprocess/build/street_matrix data/derived/street/graph_walk.bin data/derived/street/walk.bin [--threads N]
```

`--graph-only` writes only `points.csv` and `graph_<mode>.bin` (about 10 s), enough for path queries.

### Paths (`--route`)

The matrix stores no paths. To get the path of one or more pairs (points by their `points.csv` index):

```sh
algorithms/router/preprocess/build/street_matrix data/derived/street/graph_accessible.bin --route 6639 6632 [--route I J ...]
```

The output is one JSON line per route on stdout:

```json
{"from":6639,"to":6632,"seconds":215.7,"walk_m":202.4,"bike_m":0.0,"wait_s":60.0,
 "path":[[21.01019,52.23106],[21.01045,52.23126],...],"elevators":[[21.01045,52.23126]],"metro_entrances":[[21.01045,52.23126]]}
```

- `seconds` = the cost with the default speeds; `walk_m`, `bike_m`, `wait_s` as in the matrix.
- `path`: `[lon, lat]` with 5 decimals (about 1 m), from the point to the point, repeated points dropped. Ready for a map.
- `elevators`: where the path boards an elevator (an OSM elevator, or the elevator assumed at a metro entrance).
- `metro_entrances`: the street end of the segment between a metro platform and its entrance.
- `{"from":I,"to":J,"error":"no path"}` when there is no path.

Path recording is only on in this mode, so the matrix run does not pay for it.

### Server (`--serve`)

To query paths without loading the graphs for every call, run the program as a small local HTTP server.
It loads `graph_<mode>.bin` of every mode found in the folder once and keeps them in memory:

```sh
algorithms/router/preprocess/build/street_matrix --serve data/derived/street [--port 8090] [--threads 4]
curl "http://127.0.0.1:8090/route?mode=accessible&from=6639&to=6632"
curl "http://127.0.0.1:8090/health"        # {"modes":["accessible","bike","walk"],"points":7494}
```

- `GET /route?mode=<walk|bike|accessible>&from=I&to=J` (point indices from `points.csv`) returns the same JSON as
  `--route`. A bad mode or index returns `400`; no path returns `404`. Both have an `error` field.
- The search stops as soon as the target is reached: a transfer between nearby stops takes about 1 ms, a random
  pair across the city about 0.4 s.
- It listens on `127.0.0.1` only. Each worker thread keeps one search buffer per mode (about 75 MB), so
  `--threads` sets the memory too. The three graphs take about 800 MB.
- After a new `preprocess_street.py` run, restart the server to load the new graphs.

## Graph file (`graph_<mode>.bin`)

Little-endian. P = points, n = graph nodes incl. 2 virtual nodes per point, m = directed edges.

| Field | Type | Count | Meaning |
|---|---|---|---|
| magic | `char` | 4 | `SMG3` |
| n, m, p | `uint32` | 3 | sizes |
| offset | `uint32` | n + 1 | CSR: the edges of node `u` are `offset[u] .. offset[u+1]` |
| target | `uint32` | m | edge target node |
| cost | `float64` | m | seconds with the default speeds: `walk / walk speed + bike / bike speed + wait` |
| walk | `float32` | m | metres walked |
| bike | `float32` | m | metres ridden |
| wait | `float32` | m | seconds (signals, crossings, elevators) |
| flags | `uint8` | m | 1 = elevator, 2 = pushed bike, 4 = a point's access segment, 8 = metro entrance segment |
| out_node | `uint32` | p | virtual out node of each point |
| in_node | `uint32` | p | virtual in node of each point |
| active | `uint8` | p | 1 = point is on the graph (≤ 1000 m), 0 = its row and column are `NaN` |
| lon, lat | `float32` | n, n | node coordinates (a point's virtual nodes get the point's position) |

## Checks

- `cd backend && uv run pytest ../algorithms` runs the Python unit tests: junctions, islands, oneway,
  access, a metro platform with many entrances. It also checks the C++ matrix and `--route` against a small
  scipy oracle (skipped if the program is not built).
- `cd backend && uv run python ../algorithms/router/preprocess/check_pairs.py` runs 100 stop-level pairs
  (`Grójecka 02 → Centrum 03`, 20 pairs of posts of the same stop, 79 random pairs 0.2–5 km apart).
  For walk and bike it compares the C++ matrix with `osm.route()`, and the GTFS stop position with
  the OSM platform node of the same post (`ref` = ZTM stop id). Output: `check_pairs.csv`.
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
